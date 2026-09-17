# -*- coding: utf-8 -*-
"""One service must be able to answer both the pages and the API.

Every free hosting plan allows a single service, so the container serves the
built frontend itself rather than relying on a separate static host. Two
things can quietly undo that:

  - the static mount is added before the routers, and a catch-all for "/"
    starts swallowing /api/v1 requests;
  - the mount stops being conditional, and a checkout without a built
    frontend fails at import instead of falling back to the API-only root.

Both would be found at deploy time rather than here.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP).as_posix()}/single.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


class SingleServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_the_api_is_reachable_alongside_the_pages(self):
        """A static mount at / must not shadow the routers."""
        # Unauthenticated, so 401 is the expected answer: what matters is
        # that the request reached the router rather than the file server.
        for path, expected in (
            ("/health", 200),
            ("/api/v1/hospitals", 401),
            ("/api/v1/auth/me", 401),
            ("/openapi.json", 200),
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    expected, self.client.get(path).status_code)

    def test_an_unknown_api_path_is_not_answered_with_a_page(self):
        """Otherwise a typo in a route returns HTML and a 200."""
        response = self.client.get("/api/v1/does-not-exist")
        self.assertEqual(404, response.status_code)
        self.assertNotIn("text/html", response.headers.get("content-type", ""))

    def test_the_root_answers_whether_or_not_a_build_is_present(self):
        response = self.client.get("/")
        self.assertEqual(200, response.status_code)

        built = (FRONTEND / "dist" / "index.html").exists()
        source = (FRONTEND / "index.html").exists()
        if built or source:
            self.assertIn("text/html", response.headers["content-type"])
        else:
            self.assertEqual(
                "SasthoSetu API Running", response.json()["message"])

    def test_the_build_output_is_preferred_over_the_source_pages(self):
        """The built copy carries the API address; the source does not."""
        from app import main

        self.assertTrue(
            str(main._PAGES).endswith("dist")
            or not (FRONTEND / "dist" / "index.html").exists(),
            "a built frontend exists but the unstamped source is being "
            "served, so the pages would not know where the API is",
        )


class FrontendBuildTests(unittest.TestCase):
    def test_the_build_stamps_every_page_with_a_relative_api_base(self):
        """A single service shares an origin, so the path form is correct.

        Run against a copy rather than the working tree: building in place
        would delete and recreate frontend/dist underneath a developer who
        is serving it, and leave the tree changed after a test run.
        """
        import subprocess
        import sys

        workspace = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(ROOT / "scripts", workspace / "scripts")
            shutil.copytree(
                FRONTEND, workspace / "frontend",
                ignore=shutil.ignore_patterns("dist"),
            )

            result = subprocess.run(
                [sys.executable, "scripts/build_frontend.py"],
                cwd=workspace,
                env=dict(os.environ, API_BASE_URL="/api/v1"),
                capture_output=True, text=True,
            )
            self.assertEqual(
                0, result.returncode,
                f"the frontend build failed: {result.stderr}")

            pages = sorted((workspace / "frontend" / "dist").glob("*.html"))
            self.assertGreater(len(pages), 15)
            for page in pages:
                with self.subTest(page=page.name):
                    self.assertIn(
                        '<meta name="api-base" content="/api/v1">',
                        page.read_text(encoding="utf-8"),
                    )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
