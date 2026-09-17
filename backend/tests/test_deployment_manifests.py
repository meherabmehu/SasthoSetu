# -*- coding: utf-8 -*-
"""The deployment manifests must stay consistent with the application.

Three ways a deployment breaks without anything in the code looking wrong:

  - the root requirements.txt, which decides the serverless bundle, drifts
    from backend/requirements.txt and pins a different version of something
    the application imports;
  - a package the application imports at runtime is left out of it;
  - the trained models the serverless function cannot rebuild stop being
    committed, so the AI endpoints answer 503 on a fresh deployment.

None of these fail locally, where the full environment is installed and the
models were built by hand. They fail after a deploy, which is the worst place
to find out.
"""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_REQS = ROOT / "backend" / "requirements.txt"
DEPLOY_REQS = ROOT / "requirements.txt"
ARTIFACTS = ROOT / "backend" / "app" / "ai" / "artifacts"
APP = ROOT / "backend" / "app"

# Needed to build the datasets, never imported by the application. Leaving
# them out of the deployment bundle is the point, not an oversight.
PIPELINE_ONLY = {"pyarrow", "openpyxl", "pypdf"}

# Import name -> distribution name, where they differ.
DISTRIBUTION = {
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "jose": "python-jose",
    "dotenv": "python-dotenv",
    "multipart": "python-multipart",
    "psycopg2": "psycopg2-binary",
    "sqlalchemy": "SQLAlchemy",
    "yaml": "PyYAML",
}

STDLIB_OR_LOCAL = {"app", "__future__"}


def parse(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[name.strip().lower()] = version.strip()
    return pins


def top_level_imports(root: Path) -> set[str]:
    found: set[str] = set()
    for source in root.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
    return found


class DeploymentManifestTests(unittest.TestCase):
    def test_the_two_requirement_files_agree_on_versions(self):
        backend = parse(BACKEND_REQS)
        deploy = parse(DEPLOY_REQS)

        for name, version in deploy.items():
            with self.subTest(package=name):
                self.assertIn(
                    name, backend,
                    f"{name} is in the deployment list but not in "
                    "backend/requirements.txt",
                )
                self.assertEqual(
                    backend[name], version,
                    f"{name} is pinned to {version} for deployment but "
                    f"{backend[name]} for development",
                )

    def test_only_pipeline_packages_are_left_out_of_the_bundle(self):
        backend = parse(BACKEND_REQS)
        deploy = parse(DEPLOY_REQS)

        missing = set(backend) - set(deploy)
        self.assertEqual(
            PIPELINE_ONLY, missing,
            "the deployment bundle should omit exactly the data-pipeline "
            f"packages; it omits {sorted(missing)}",
        )

    def test_everything_the_application_imports_is_in_the_bundle(self):
        deploy = parse(DEPLOY_REQS)
        imported = top_level_imports(APP)

        import sys
        for name in sorted(imported):
            if name in STDLIB_OR_LOCAL or name in sys.stdlib_module_names:
                continue
            distribution = DISTRIBUTION.get(name, name).lower()
            with self.subTest(module=name):
                self.assertIn(
                    distribution, deploy,
                    f"backend/app imports {name} but {distribution} is not "
                    "in the deployment requirements",
                )

    def test_the_text_models_are_committed(self):
        """A serverless function has no start-up in which to train them."""
        import subprocess

        for name in ("triage_model.joblib", "surge_model.joblib"):
            with self.subTest(artifact=name):
                path = ARTIFACTS / name
                self.assertTrue(
                    path.exists(),
                    f"{name} is missing; run python ml/prepare_all.py",
                )
                tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch",
                     str(path.relative_to(ROOT))],
                    cwd=ROOT, capture_output=True,
                )
                self.assertEqual(
                    0, tracked.returncode,
                    f"{name} is not tracked by git, so it will not reach a "
                    "serverless deployment",
                )

    def test_the_committed_models_match_the_pinned_scikit_learn(self):
        """A model pickled by another version may silently misbehave.

        scikit-learn does not promise that an estimator pickled by one
        version loads correctly into another; it warns and carries on. Since
        the artifacts are committed from a developer's machine and the
        deployment installs the pinned version, the two drift apart the
        moment someone retrains without matching the pin. The warning would
        appear in the deployment log, where nobody is looking, and the
        predictions it qualifies are triage levels.
        """
        import warnings

        import joblib
        from sklearn.exceptions import InconsistentVersionWarning

        for name in ("triage_model.joblib", "surge_model.joblib"):
            with self.subTest(artifact=name):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    joblib.load(ARTIFACTS / name)

                mismatched = [
                    str(w.message) for w in caught
                    if issubclass(w.category, InconsistentVersionWarning)
                ]
                self.assertEqual(
                    [], mismatched,
                    f"{name} was pickled by a different scikit-learn than "
                    "the one pinned in requirements. Retrain it in an "
                    "environment built from backend/requirements.txt:\n"
                    "  pip install -r backend/requirements.txt\n"
                    "  python ml/prepare_all.py",
                )

    def test_the_vercel_entrypoint_exposes_the_application(self):
        entry = ROOT / "api" / "index.py"
        self.assertTrue(entry.exists(), "api/index.py is missing")
        tree = ast.parse(entry.read_text(encoding="utf-8"))
        names = {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        self.assertIn(
            "app", names,
            "api/index.py must import app for the platform to serve it",
        )

    def test_vercel_routes_the_api_and_serves_the_built_pages(self):
        config = json.loads(
            (ROOT / "vercel.json").read_text(encoding="utf-8"))

        self.assertEqual("frontend/dist", config.get("outputDirectory"))

        destinations = {
            rule["source"]: rule["destination"]
            for rule in config.get("rewrites", [])
        }
        self.assertIn(
            "/api/(.*)", destinations,
            "requests to /api must reach the function",
        )
        self.assertEqual("/api/index", destinations["/api/(.*)"])


if __name__ == "__main__":
    unittest.main()
