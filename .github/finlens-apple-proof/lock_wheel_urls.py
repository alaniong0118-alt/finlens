"""Render the exact independently reviewed Linux wheel set for pip download."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hashlib
import json
import re

ROOT = Path(__file__).parent
EXPECTED = "02a4474d499ecfac70b4cfeb519b37d176a76434cb56d827f19c962add144df5"
INPUT = ROOT / "backend-wheel-candidate-ci-anchored.json"

def render(payload):
    if hashlib.sha256(payload).hexdigest() != EXPECTED:
        raise ValueError("wheel manifest identity")
    rows = json.loads(payload)["wheels"]
    if len(rows) != 73 or len({w["name"] for w in rows}) != 73:
        raise ValueError("wheel set mismatch")
    output = []
    for wheel in rows:
        url = urlsplit(wheel["url"])
        if (url.scheme != "https" or url.netloc not in {"files.pythonhosted.org", "download-r2.pytorch.org"}
                or url.query or url.fragment or unquote(url.path.rsplit("/", 1)[-1]) != wheel["filename"]
                or not re.fullmatch(r"[0-9a-f]{64}", wheel["wheel_sha256"])):
            raise ValueError("unapproved wheel URL or digest")
        output.append(f'{wheel["name"]} @ {wheel["url"]} --hash=sha256:{wheel["wheel_sha256"]}')
    return "\n".join(output) + "\n"

if __name__ == "__main__":
    print(render(INPUT.read_bytes()), end="")
