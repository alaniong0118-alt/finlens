"""Test-only, one-use SEC prep. Network use is not part of the offline test."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ALLOWED = {
    "facts.raw": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
    "submission.raw": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/0000320193-26-000020.txt",
}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None

def stage(metadata, destination, contact, open_url=None):
    candidates = metadata["sec"]
    if {row["name"]: row["official_url"] for row in candidates} != ALLOWED or len(candidates) != 2:
        raise ValueError("input scope mismatch")
    if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", contact):
        raise ValueError("SEC contact absent or invalid")
    if any(not 0 < row["length"] <= 7_000_000 or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) for row in candidates):
        raise ValueError("input boundary mismatch")
    if open_url is None:
        open_url = build_opener(ProxyHandler({}), NoRedirect()).open
    destination.mkdir(mode=0o700, exist_ok=False)
    for row in candidates:
        url = ALLOWED[row["name"]]
        request = Request(url, headers={"User-Agent": f"FinLens verified financial research {contact}",
                                        "Accept-Encoding": "identity"})
        with open_url(request, timeout=12) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("SEC response not admitted")
            raw = response.read(row["length"] + 1)
        if len(raw) != row["length"] or sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("SEC source changed")
        (destination / row["name"]).write_bytes(raw)
    return len(candidates)

if __name__ == "__main__":
    try:
        if (os.environ.get("FINLENS_SEC_PREP_ADMITTED"), os.environ.get("GITHUB_RUN_ATTEMPT")) != ("two-fixed-sec-reads", "1"):
            raise RuntimeError("one-time SEC prep gate missing")
        metadata = json.loads(Path(__file__).with_name("public-input-metadata.json").read_text())
        root = Path(os.environ["RUNNER_TEMP"])
        if not root.is_absolute() or root.resolve() != root:
            raise RuntimeError("not an owned temporary root")
        count = stage(metadata, root / "finlens-apple-sec-input", os.environ["FINLENS_SEC_CONTACT"])
        print(f"PASS: {count} pinned SEC bodies staged privately")
    except Exception as cause:
        raise SystemExit(f"HOLD: {type(cause).__name__}") from None
