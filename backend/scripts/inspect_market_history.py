"""Run from backend: python -B -m scripts.inspect_market_history --help."""
import argparse
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys

from app.market_data_contracts import MarketContractError, require
from app.market_history import MAX_CONTEXT_BYTES, MAX_RESPONSE_BYTES, inspect_raw_history


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, "error: invalid_arguments\n")


def _windows_spelling(text):
    """Pure parsing only: do not erase parent traversal or follow namespaces."""
    require(type(text) is str and 0 < len(text) <= 4096 and not
            text.replace("\\", "/").startswith("//"), "invalid_local_path")
    parsed = PureWindowsPath(text)
    require(not parsed.drive or re.fullmatch(r"[A-Za-z]:", parsed.drive), "invalid_local_path")
    require(bool(parsed.drive) == bool(parsed.root), "invalid_local_path")
    tail = parsed.parts[1:] if parsed.drive else parsed.parts
    for part in tail:
        require(part != ".." and not part.endswith((".", " ")) and not
                any(ord(c) < 32 or c in '<>:"|?*' for c in part), "invalid_local_path")
        basename = part.split(".")[0].rstrip(" ").upper()
        require(not re.fullmatch(r"CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[1-9¹²³]", basename),
                "invalid_local_path")
    return parsed


def _check_windows_root(anchor):
    """Classify local DOS mapping before querying the root's drive type."""
    import ctypes
    from ctypes import wintypes
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        query = kernel.QueryDosDeviceW
        query.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
        query.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        count = query(anchor[:2], buffer, len(buffer))
        require(0 < count <= len(buffer), "unsupported_local_root")
        mappings = [item for item in buffer[:count].split("\x00") if item]
        require(len(mappings) == 1 and re.fullmatch(r"\\Device\\HarddiskVolume[0-9]+", mappings[0], re.I),
                "unsupported_local_root")
        drive_type = kernel.GetDriveTypeW
        drive_type.argtypes = (wintypes.LPCWSTR,)
        drive_type.restype = wintypes.UINT
        require(drive_type(anchor) == 3, "unsupported_local_root")
    except (AttributeError, OSError):
        raise MarketContractError("unsupported_local_root") from None


def _local_target(path):
    """Windows-only until another platform has an explicit root classifier."""
    parsed = _windows_spelling(os.fspath(path))
    require(os.name == "nt", "unsupported_local_root")
    if not parsed.drive:
        cwd = _windows_spelling(os.getcwd())
        require(cwd.is_absolute(), "unsupported_local_root")
        parsed = cwd / parsed
    require(len(str(parsed)) <= 4096, "invalid_local_path")
    _check_windows_root(parsed.anchor)
    return Path(str(parsed))


def _no_reparse(info):
    require(not stat.S_ISLNK(info.st_mode) and not
            (getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
            "invalid_local_path")


def _preflight_ancestors(path):
    target = _local_target(path)
    for part in reversed(target.parents):
        info = part.lstat()
        _no_reparse(info)
        require(stat.S_ISDIR(info.st_mode), "invalid_local_path")
    return target


def _read_local(path, limit):
    """Preflight is for trusted quiescent trees, not race-proof containment."""
    target = _preflight_ancestors(path)
    before = target.lstat()
    _no_reparse(before)
    require(stat.S_ISREG(before.st_mode), "invalid_local_file")
    with target.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require(stat.S_ISREG(opened.st_mode) and (opened.st_dev, opened.st_ino) ==
                (before.st_dev, before.st_ino), "invalid_local_file")
        data = stream.read(limit + 1)
    require(0 < len(data) <= limit, "invalid_local_file_bound")
    return data


def render_table(history):
    data = history.to_dict()
    source = data["provenance"]["source"]
    identity = data["declared_identity"]
    calendar = data["calendar"]
    lines = [f"Input: {history.input_kind} | provenance: unverified | trusted custody: false",
             data["declaration_notice"],
             f"Normalization: {history.normalization_state} | publication: {history.publication_state} | returns: unavailable | adjusted series: unavailable",
             f"Publication: {data['publication_id']} | version: {data['market_data_version']} | freshness: unknown",
             f"Declared symbol: {identity['symbol']} | security: {identity['security']['security_id']} | listing: {identity['listing']['listing_id']} | MIC: {identity['listing']['mic']}",
             f"Declared calendar: {calendar['calendar_id']}/{calendar['version']} | timezone: {calendar['timezone']} | coverage: {data['coverage_start']} to {data['coverage_end']}",
             f"Source: {source['provider']}/{source['product']}/{source['source_id']}",
             f"Retrieved (declared): {source['retrieved_at']} | available (declared): {source['available_at'] or 'null'}",
             f"Published (declared): {data['published_at']} | knowledge: {data['knowledge_mode']}",
             f"Context SHA256: {history.context_sha256}",
             f"Response SHA256: {source['response_sha256']}",
             f"Normalized content SHA256: {history.normalized_content_sha256}",
             f"Publication manifest SHA256: {history.publication_manifest_sha256}",
             "Reasons: " + ", ".join(history.reasons),
             "Session date | Unadjusted close | Declared currency | Observation state"]
    lines.extend(f"{row.session_date} | {row.unadjusted_close if row.unadjusted_close is not None else 'null'} | {row.declared_currency} | {row.observation_state}"
                 for row in history.rows)
    return "\n".join(lines)


def main(argv=None):
    parser = _Parser(description="Inspect unverified local EOD bytes; no acquisition or return calculation.")
    parser.add_argument("--payload", required=True, help="Local original JSON file")
    parser.add_argument("--context", required=True, help="Local metadata JSON file")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args(argv)
    try:
        _preflight_ancestors(args.payload)
        _preflight_ancestors(args.context)
        payload = _read_local(args.payload, MAX_RESPONSE_BYTES)
        context = _read_local(args.context, MAX_CONTEXT_BYTES)
        history = inspect_raw_history(payload, context)
        output = json.dumps(history.to_dict(), indent=2, ensure_ascii=True, allow_nan=False) if args.format == "json" else render_table(history)
    except MarketContractError as exc:
        code = str(exc)
        print("error: " + (code if re.fullmatch(r"[a-z_]{1,80}", code) else "inspection_rejected"), file=sys.stderr)
        return 2
    except (OSError, ValueError):
        print("error: local_input_unavailable", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
