"""Resumable bounded parallel HTTP ranges for large public dataset archives.

Each completed range is validated against Content-Range and its byte count.
An interrupted ordinary .part file contributes its complete initial chunks.
Only this downloader's redundant chunks are removed after the final container
has passed validation. Original downloaded archives remain available.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from download_dataset_file import validate


def download(url, output, kind="zip", workers=4, chunk_mb=8):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        validate(output, kind)
        print(f"Cached verified container: {output.name}", flush=True)
        return output
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl is required")
    folder = output.with_name(output.name + ".chunks")
    folder.mkdir(exist_ok=True)

    def transfer(start, end, destination):
        header = destination.with_name(destination.name + ".headers")
        subprocess.run([curl, "--fail", "--location", "--retry", "2", "--retry-delay", "2",
            "--connect-timeout", "15", "--max-time", "90", "--silent", "--show-error",
            "--range", f"{start}-{end}", "--dump-header", str(header),
            "--output", str(destination), url], check=True, capture_output=True)
        ranges = re.findall(r"content-range:\s*bytes\s+(\d+)-(\d+)/(\d+)",
                            header.read_text(encoding="utf-8", errors="replace"), re.I)
        if not ranges or tuple(map(int, ranges[-1][:2])) != (start, end):
            raise ValueError("Server did not honor the requested byte range")
        if destination.stat().st_size != end - start + 1:
            raise ValueError("Range has an incorrect byte count")
        return int(ranges[-1][2])

    total = transfer(0, 0, folder / "probe")
    chunk_size = chunk_mb * 1024**2
    ranges = [(index, start, min(start + chunk_size, total) - 1)
              for index, start in enumerate(range(0, total, chunk_size))]
    existing = sum((folder / f"{index:06d}.chunk").stat().st_size
                   for index, start, end in ranges
                   if (folder / f"{index:06d}.chunk").exists()
                   and (folder / f"{index:06d}.chunk").stat().st_size == end - start + 1)
    if shutil.disk_usage(output.parent).free < total * 2 - existing + 2 * 1024**3:
        raise RuntimeError("Need room for remaining ranges, assembled archive and 2 GB reserve")
    partial = output.with_name(output.name + ".part")
    if partial.exists():
        with partial.open("rb") as source:
            for index, start, end in ranges:
                if end >= partial.stat().st_size:
                    break
                target = folder / f"{index:06d}.chunk"
                if target.exists() and target.stat().st_size == end - start + 1:
                    source.seek(end + 1)
                    continue
                target.write_bytes(source.read(end - start + 1))

    def piece(spec):
        index, start, end = spec
        final = folder / f"{index:06d}.chunk"
        if final.exists() and final.stat().st_size == end - start + 1:
            return final.stat().st_size
        temporary = folder / f"{index:06d}.part"
        remote_size = transfer(start, end, temporary)
        if remote_size != total:
            raise ValueError("Source changed while downloading")
        temporary.replace(final)
        return final.stat().st_size

    print(f"{output.name}: {total:,} bytes, {len(ranges)} ranges, {workers} workers", flush=True)
    completed, done = 0, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(piece, spec) for spec in ranges]
        try:
            for future in as_completed(futures):
                done += future.result()
                completed += 1
                if completed % 8 == 0 or completed == len(ranges):
                    print(f"  {output.name}: {done / total:.1%} ({completed}/{len(ranges)})", flush=True)
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    assembled = output.with_name(output.name + ".assembling")
    digest = hashlib.sha256()
    with assembled.open("wb") as destination:
        for index, _start, _end in ranges:
            with (folder / f"{index:06d}.chunk").open("rb") as source:
                while data := source.read(1024**2):
                    destination.write(data)
                    digest.update(data)
    if assembled.stat().st_size != total:
        raise ValueError("Assembled size differs from source")
    validate(assembled, kind)
    assembled.replace(output)
    output.with_name(output.name + ".source.json").write_text(json.dumps({
        "url": url, "bytes": total, "sha256": digest.hexdigest(),
        "container": kind, "ranges_validated": True,
    }, indent=2), encoding="utf-8")
    for index, _, _ in ranges:
        (folder / f"{index:06d}.chunk").unlink()
    if partial.exists():
        partial.unlink()
    print(f"Verified complete: {output.name}, sha256={digest.hexdigest()}", flush=True)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("output", type=Path)
    parser.add_argument("--kind", choices=["zip", "parquet"], default="zip")
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    parser.add_argument("--chunk-mb", type=int, default=8, choices=range(1, 65))
    args = parser.parse_args()
    download(args.url, args.output, args.kind, args.workers, args.chunk_mb)
