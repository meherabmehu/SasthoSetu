"""Exercise real range/resume transport against a local public-file fixture."""
import hashlib
import http.server
import importlib
import io
import json
import re
import shutil
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

ML = Path(__file__).resolve().parents[2] / "ml"
sys.path.insert(0, str(ML))
downloader = importlib.import_module("download_ranges")


@unittest.skipUnless(shutil.which("curl.exe") or shutil.which("curl"), "curl not installed")
class DatasetDownloadTests(unittest.TestCase):
    def test_resume_ranges_reassembles_exact_source_and_records_hash(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("fixture.bin", b"public dataset fixture\n" * 110000)
        blob = buffer.getvalue()
        requested = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                start, end = map(int, re.fullmatch(r"bytes=(\d+)-(\d+)", self.headers["Range"]).groups())
                requested.append((start, end))
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(blob)}")
                self.send_header("Content-Length", str(end - start + 1))
                self.end_headers()
                self.wfile.write(blob[start:end + 1])

            def log_message(self, *_args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / "fixture.zip"
                partial = output.with_name(output.name + ".part")
                partial.write_bytes(blob[:1024**2 + 123])
                downloader.download(f"http://127.0.0.1:{server.server_port}/fixture.zip", output,
                                    workers=2, chunk_mb=1)
                self.assertEqual(blob, output.read_bytes())
                self.assertNotIn((0, 1024**2 - 1), requested, "complete prefix should be reused")
                self.assertFalse(partial.exists())
                self.assertFalse(list(output.with_name(output.name + ".chunks").glob("*.chunk")))
                provenance = json.loads(output.with_name(output.name + ".source.json").read_text(encoding="utf-8"))
                self.assertEqual(hashlib.sha256(blob).hexdigest(), provenance["sha256"])
                self.assertTrue(provenance["ranges_validated"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
