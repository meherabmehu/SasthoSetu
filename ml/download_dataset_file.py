"""Resume a public dataset file, validate its container and record its hash.

Uses curl's HTTP transport, including on Windows installations where Python's
large-file transfer stalls. Downloads stay in .part until validation succeeds.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path


def validate(path, kind):
    if kind == "zip":
        with zipfile.ZipFile(path) as archive:
            if not archive.infolist():
                raise ValueError("Empty ZIP archive")
    elif kind == "parquet":
        import pyarrow.parquet as pq
        if pq.ParquetFile(path).metadata.num_rows == 0:
            raise ValueError("Empty Parquet file")


def download(url, output, kind="zip", minimum_bytes=1):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        validate(output, kind)
        print(f"Using verified cached container: {output.name}", flush=True)
        return output
    binary = shutil.which("curl.exe") or shutil.which("curl")
    if not binary:
        raise RuntimeError("curl is required for resumable downloads")
    partial = output.with_name(output.name + ".part")
    command = [binary, "--fail", "--location", "--retry", "3", "--retry-delay", "2",
               "--connect-timeout", "20", "--speed-limit", "10240", "--speed-time", "45",
               "--continue-at", "-", "--silent", "--show-error", "--output", str(partial), url]
    print(f"Downloading {output.name}; progress is visible in {partial.name}", flush=True)
    subprocess.run(command, check=True)
    if partial.stat().st_size < minimum_bytes:
        raise ValueError("Downloaded file is smaller than the expected source")
    validate(partial, kind)
    with partial.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    partial.replace(output)
    output.with_name(output.name + ".source.json").write_text(json.dumps({
        "url": url, "sha256": digest, "bytes": output.stat().st_size,
        "container": kind, "container_validated": True,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {output.name}: {output.stat().st_size:,} bytes, sha256={digest}", flush=True)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("output", type=Path)
    parser.add_argument("--kind", choices=["zip", "parquet"], default="zip")
    parser.add_argument("--minimum-bytes", type=int, default=1)
    arguments = parser.parse_args()
    download(arguments.url, arguments.output, arguments.kind, arguments.minimum_bytes)
