"""Local-only custody check; no network, model, database, or runtime admission."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

PATH = Path(__file__).with_name("public-input-metadata.json")

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
            if digest != row["sha256"] or os.fstat(stream.fileno()) != snapshot:
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
