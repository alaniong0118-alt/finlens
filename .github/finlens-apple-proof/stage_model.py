"""Stage only the pinned, public MiniLM files, without any Hub credentials."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import ssl
import sys
from urllib.parse import quote, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

META = Path(__file__).with_name("public-input-metadata.json")
METASHA = "4261ae96fa6b0ece1f68d2620a53fcf726eeda3a55d799049c94be521ba97794"
REPO = "sentence-transformers/all-MiniLM-L6-v2"
HOSTS = {"huggingface.co", "cdn-lfs.huggingface.co", "cdn-lfs-us-1.hf.co",
         "cdn-lfs-eu-1.hf.co", "cdn-lfs.hf.co", "cas-bridge.xethub.hf.co"}
LIMIT = 32 * 1024 * 1024 if sys.platform == "win32" else 1024 * 1024


def check_url(url):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc not in HOSTS or parts.fragment):
        raise ValueError("unapproved model transport URL")


class StrictRedirect(HTTPRedirectHandler):
    max_redirections = 3
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def load_rules():
    payload = META.read_bytes()
    if hashlib.sha256(payload).hexdigest() != METASHA:
        raise ValueError("metadata identity")
    rules = json.loads(payload)["model"]
    if rules["model"] != REPO or not re.fullmatch(r"[0-9a-f]{40}", rules["revision"]):
        raise ValueError("model identity")
    return rules


def write_checked(response, file, rule):
    n = rule["size"]
    if not (0 < n < 100 * 1024**2):
        raise ValueError("invalid model length rule")
    if rule["method"] == "sha256":
        digest = hashlib.sha256()
    elif rule["method"] == "git-blob-sha1":
        digest = hashlib.sha1(f"blob {n}\0".encode())
    else:
        raise ValueError("unexpected digest rule")
    with file.open("xb") as stream:
        while n:
            block = response.read(min(n, LIMIT))
            if not block or len(block) > n:
                raise ValueError("model length mismatch")
            stream.write(block)
            digest.update(block)
            n -= len(block)
        if response.read(1) or digest.hexdigest() != rule["digest"]:
            raise ValueError("model content mismatch")


def stage(root, fetch):
    rules = load_rules()
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    model = root / ("models--" + REPO.replace("/", "--"))
    rev = rules["revision"]
    snapshot = model / "snapshots" / rev
    for relative, rule in rules["files"].items():
        target = PurePosixPath(relative)
        if target.is_absolute() or ".." in target.parts or target.as_posix() != relative:
            raise ValueError("invalid model path")
        file = snapshot / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{REPO}/resolve/{rev}/{quote(relative)}"
        check_url(url)
        with fetch(url) as response:
            write_checked(response, file, rule)
    # Add the offline alias only after verifying every snapshot file.
    (model / "refs").mkdir()
    (model / "refs" / "main").write_text(rev, encoding="ascii")
    return len(rules["files"])


def main():
    if len(sys.argv) != 2:
        raise SystemExit("HOLD: expected new model cache path")
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), StrictRedirect())
    def fetch(url):
        response = opener.open(Request(url, headers={"Accept-Encoding": "identity"}), timeout=45)
        if response.status != 200 or response.headers.get("Content-Encoding", "identity") != "identity":
            response.close()
            raise ValueError("model transport response")
        return response
    try:
        count = stage(Path(sys.argv[1]), fetch)
    except Exception as exc:
        raise SystemExit(f"HOLD: model staging {type(exc).__name__}") from None
    print(f"PASS: {count} pinned model files; no model loaded")


if __name__ == "__main__":
    main()
