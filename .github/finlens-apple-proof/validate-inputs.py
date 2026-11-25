"""Local-only custody check; no network, model, database, or runtime admission."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

PATH = Path(__file__).with_name("public-input-metadata.json")

def file_identity(info):
    # Normal reads may update atime. Compare identity and content-affecting
    # metadata, with nanosecond precision for modification and change times.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_uid, info.st_gid, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns)

def verify(directory):
    records = json.loads(PATH.read_text())["sec"]
    for row in records:
        if row["name"] not in {"facts.raw", "submission.raw"}:
            raise ValueError("unexpected input name")
        path = directory / row["name"]
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            snapshot = os.fstat(stream.fileno())
            if (not stat.S_ISREG(snapshot.st_mode) or snapshot.st_nlink != 1
                    or snapshot.st_size != row["length"]):
                raise ValueError("SEC input type or length differs")
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != row["sha256"] or file_identity(os.fstat(stream.fileno())) != file_identity(snapshot):
                raise ValueError("SEC input digest or file identity differs")
    return len(records)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retained_sec", type=Path)
    args = parser.parse_args()
    try:
        count = verify(args.retained_sec)
    except (ValueError, OSError, KeyError):
        raise SystemExit("HOLD: retained SEC input validation failed") from None
    print(f"PASS: {count} pinned SEC inputs, metadata only")
