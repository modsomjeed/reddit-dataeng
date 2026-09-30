"""Back up the raw bucket to a local folder, or restore it from there.

The raw JSON in RustFS is the only copy of what was extracted; everything in ClickHouse
can be rebuilt from it, but the bucket itself lives in a Docker volume that is easy to
delete. `backup` copies new or changed objects down; `restore` uploads files the bucket
is missing. Both skip files that already match, so they are safe to rerun.
"""

import argparse
import logging
from pathlib import Path

from extract_reddit import ensure_bucket, s3_client
from settings import ROOT, read_env, setup_logging

log = logging.getLogger("backup")

BACKUP_DIR = ROOT / "data" / "backup"


def bucket_objects(s3, bucket: str) -> dict[str, int]:
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket)
    return {obj["Key"]: obj["Size"] for page in pages for obj in page.get("Contents", [])}


def backup(s3, bucket: str, target: Path) -> None:
    copied = skipped = 0
    for key, size in sorted(bucket_objects(s3, bucket).items()):
        path = target / key
        if path.exists() and path.stat().st_size == size:
            skipped += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, key, str(path))
        copied += 1
    log.info("%d copied, %d already up to date → %s", copied, skipped, target)


def restore(s3, bucket: str, source: Path) -> None:
    if not source.exists():
        raise SystemExit(f"no backup found at {source}")
    in_bucket = bucket_objects(s3, bucket)
    uploaded = skipped = 0
    for path in sorted(p for p in source.rglob("*.json") if p.is_file()):
        key = path.relative_to(source).as_posix()
        if in_bucket.get(key) == path.stat().st_size:
            skipped += 1
            continue
        s3.upload_file(str(path), bucket, key, ExtraArgs={"ContentType": "application/json"})
        uploaded += 1
    log.info("%d uploaded, %d already in s3://%s", uploaded, skipped, bucket)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=["backup", "restore"])
    parser.add_argument("--folder", type=Path, help="local folder to use instead of data/backup/<bucket>")
    args = parser.parse_args()

    setup_logging()
    env = read_env()
    s3 = s3_client(env)
    bucket = env["S3_BUCKET"]
    ensure_bucket(s3, bucket)
    folder = args.folder or BACKUP_DIR / bucket
    if args.direction == "backup":
        backup(s3, bucket, folder)
    else:
        restore(s3, bucket, folder)


if __name__ == "__main__":
    main()
