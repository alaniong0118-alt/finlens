"""Read-only Linux wheelhouse byte preflight; never opens wheel archives.

Use only trusted operator-owned immutable staging. The same verified wheelhouse
and lock must remain read-only through any separately approved install.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

BASE = Path(__file__).parent
MANIFEST = BASE / "backend-wheel-candidate-ci-anchored.json"
LOCK = BASE / "backend-acceptance-cpu.require-hashes.lock"
MANIFEST_SHA = "02a4474d499ecfac70b4cfeb519b37d176a76434cb56d827f19c962add144df5"
LOCK_SHA = "08ee8c032fa72580acd463bb8a5af889040d0573fee1501c7dfb3d5ce5d7920e"
WHEEL_COUNT = 73
TARGET = "Ubuntu 24.04 x64, glibc 2.39, normal CPython 3.14.7"
DIGEST = re.compile(r"[0-9a-f]{64}")
NAME = r"[a-z0-9]+(?:-[a-z0-9]+)*"
VERSION = r"[0-9]+(?:\.[a-z0-9]+)+(?:\+[a-z0-9.]+)?"
LOCK_LINE = re.compile(rf"({NAME})==({VERSION}) --hash=sha256:({DIGEST.pattern})")
WHEEL = re.compile(r"([a-z0-9_]+)-([0-9a-z.+_]+)(?:-[0-9][a-z0-9_]*)?-[a-z0-9_.]+-[a-z0-9_.]+-[a-z0-9_.]+\.whl")
CHUNK_SIZE = 1024 * 1024


def _pinned_input(path, digest):
    # These fixed inputs live in the trusted tool directory, never in staging.
    with path.open("rb") as stream:
        data = stream.read(CHUNK_SIZE + 1)
    if len(data) > CHUNK_SIZE or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"pinned input digest mismatch: {path.name}")
    return data


def check_binding(manifest_data, lock_data, count):
    doc = json.loads(manifest_data)
    rows = doc["wheels"]
    if doc["target"] != TARGET or len(rows) != count:
        raise ValueError("wrong manifest target or wheel count")
    from_manifest = {}
    allowlist = {}
    for row in rows:
        name, version, digest, filename = (row[k] for k in ("name", "version", "wheel_sha256", "filename"))
        wheel = WHEEL.fullmatch(filename)
        if (not re.fullmatch(NAME, name) or not re.fullmatch(VERSION, version)
                or not DIGEST.fullmatch(digest) or not wheel
                or wheel[1].replace("_", "-") != name or wheel[2] != version):
            raise ValueError("invalid manifest wheel record")
        if name in from_manifest or filename in allowlist:
            raise ValueError("duplicate manifest wheel record")
        from_manifest[name] = (version, digest)
        allowlist[filename] = digest
    from_lock = {}
    for line in lock_data.decode("ascii").splitlines():
        if not line or line.startswith("#"):
            continue
        match = LOCK_LINE.fullmatch(line)
        if not match or match[1] in from_lock:
            raise ValueError("unexpected or duplicate lock record")
        from_lock[match[1]] = (match[2], match[3])
    if from_manifest != from_lock:
        raise ValueError("manifest and lock wheel identities differ")
    return allowlist


def load_allowlist():
    return check_binding(_pinned_input(MANIFEST, MANIFEST_SHA), _pinned_input(LOCK, LOCK_SHA), WHEEL_COUNT)


def _identity(info):
    # atime can legitimately change when hashing.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _inventory(directory, allowlist):
    names = set(os.listdir(directory))
    if names != set(allowlist):
        raise ValueError(f"wheelhouse inventory mismatch: {len(set(allowlist) - names)} missing, "
                         f"{len(names - set(allowlist))} unexpected")


def verify_wheelhouse(path, allowlist):
    if path == Path("/") or not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("use a trusted non-root canonical absolute wheelhouse directory")
    directory = os.open(path, os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY)
    try:
        _inventory(directory, allowlist)
        for name, expected in sorted(allowlist.items()):
            if not WHEEL.fullmatch(name) or not DIGEST.fullmatch(expected):
                raise ValueError("invalid trusted wheel allowlist entry")
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError(f"not an unlinked regular wheel: {name}")
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                if _identity(os.fstat(stream.fileno())) != _identity(info):
                    raise ValueError(f"wheel identity changed before reading: {name}")
                digest = hashlib.sha256()
                remaining = info.st_size
                while remaining:
                    block = stream.read(min(CHUNK_SIZE, remaining))
                    if not block:
                        raise ValueError(f"short wheel read: {name}")
                    remaining -= len(block)
                    digest.update(block)
                if stream.read(1) or _identity(os.fstat(stream.fileno())) != _identity(info):
                    raise ValueError(f"wheel changed during reading: {name}")
                if digest.hexdigest() != expected:
                    raise ValueError(f"wheel digest mismatch: {name}")
            if _identity(os.stat(name, dir_fd=directory, follow_symlinks=False)) != _identity(info):
                raise ValueError(f"wheel path changed during reading: {name}")
        _inventory(directory, allowlist)
        return len(allowlist)
    finally:
        os.close(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("immutable_wheelhouse")
    opts = parser.parse_args()
    try:
        path = Path(opts.immutable_wheelhouse)
        if str(path) != opts.immutable_wheelhouse:
            raise ValueError("wheelhouse argument is not canonical")
        count = verify_wheelhouse(path, load_allowlist())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"WHEELHOUSE INTAKE FAIL: {exc}\n")
    print(f"WHEELHOUSE BYTE CHECK PASSED: {count} pinned wheel files; no installs or imports")


if __name__ == "__main__":
    main()
