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
METASHA = "ad1233011ff3e089089d4ba7f4e220ddc782ba252d3ca9569c91dc7ca89c3d02"
CANDIDATE = "f20197bbcecc5164227dfef7ff96cca4d7f9a886"
REPO = "sentence-transformers/all-MiniLM-L6-v2"
HOSTS = {"huggingface.co", "cdn-lfs.huggingface.co", "cdn-lfs-us-1.hf.co",
         "cdn-lfs-eu-1.hf.co", "cdn-lfs.hf.co", "cas-bridge.xethub.hf.co",
         "us.aws.cdn.hf.co"}
LIMIT = 32 * 1024 * 1024 if sys.platform == "win32" else 1024 * 1024


class StageFault(ValueError):
    """Only fixed public reason codes reach the workflow log."""
    pass


def check_url(url):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc not in HOSTS or parts.fragment):
        raise StageFault("redirect_transport")


class StrictRedirect(HTTPRedirectHandler):
    max_redirections = 3
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def load_rules(candidate=CANDIDATE):
    payload = META.read_bytes()
    if hashlib.sha256(payload).hexdigest() != METASHA:
        raise StageFault("manifest_digest")
    manifest = json.loads(payload)
    if manifest["candidate"] != CANDIDATE or candidate != CANDIDATE:
        raise StageFault("candidate_revision")
    rules = manifest["model"]
    if rules["model"] != REPO or not re.fullmatch(r"[0-9a-f]{40}", rules["revision"]):
        raise StageFault("model_identity")
    return rules


def check_candidate(candidate):
    load_rules(candidate)


def write_checked(response, file, rule):
    n = rule["size"]
    if not (0 < n < 100 * 1024**2):
        raise StageFault("manifest_length")
    if rule["method"] == "sha256":
        digest = hashlib.sha256()
    elif rule["method"] == "git-blob-sha1":
        digest = hashlib.sha1(f"blob {n}\0".encode())
    else:
        raise StageFault("manifest_digest_method")
    with file.open("xb") as stream:
        while n:
            block = response.read(min(n, LIMIT))
            if not block or len(block) > n:
                raise StageFault("body_length")
            stream.write(block)
            digest.update(block)
            n -= len(block)
        if response.read(1):
            raise StageFault("body_length")
        if digest.hexdigest() != rule["digest"]:
            raise StageFault("content_digest")


def stage(root, fetch):
    rules = load_rules()
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    model = root / ("models--" + REPO.replace("/", "--"))
    rev = rules["revision"]
    snapshot = model / "snapshots" / rev
    for relative, rule in rules["files"].items():
        target = PurePosixPath(relative)
        if target.is_absolute() or ".." in target.parts or target.as_posix() != relative:
            raise StageFault("manifest_path")
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
    if len(sys.argv) == 3 and sys.argv[1] == "--check-candidate":
        try:
            check_candidate(sys.argv[2])
        except StageFault as exc:
            raise SystemExit(f"HOLD: model binding {exc}") from None
        except Exception:
            raise SystemExit("HOLD: model binding unexpected_failure") from None
        print("PASS: fixed application revision and input manifest")
        return
    if len(sys.argv) != 2:
        raise SystemExit("HOLD: expected new model cache path")
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), StrictRedirect())
    def fetch(url):
        response = opener.open(Request(url, headers={"Accept-Encoding": "identity"}), timeout=45)
        if response.status != 200 or response.headers.get("Content-Encoding", "identity") != "identity":
            response.close()
            raise StageFault("response_not_identity_200")
        return response
    try:
        count = stage(Path(sys.argv[1]), fetch)
    except StageFault as exc:
        raise SystemExit(f"HOLD: model staging {exc}") from None
    except Exception:
        raise SystemExit("HOLD: model staging unexpected_failure") from None
    print(f"PASS: {count} pinned model files; no model loaded")


if __name__ == "__main__":
    main()
