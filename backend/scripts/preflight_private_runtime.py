"""Explicit offline metadata diagnostic; NEVER authorizes a private runtime.

Run with the intended interpreter and FINLENS_SERVER_PROFILE=sec_readonly:
    python -B -m scripts.preflight_private_runtime

Only backend/requirements.txt and installed distribution metadata are read. No
dotenv, application, encoder, model artifacts, registry or database is accessed.
Python compatibility means only satisfaction of declared Requires-Python fields.
Prereleases require explicit admission by the relevant declared specifier.
All results, including preliminary passes, exit 1 with overall status BLOCKED.
"""

import sys

# Prevent dependency imports from writing bytecode even without the -B flag.
sys.dont_write_bytecode = True

import json
import os
from importlib import metadata
from pathlib import Path

try:
    from packaging.markers import default_environment
    from packaging.metadata import Metadata
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    from packaging.version import Version
except Exception:
    # Even a broken/missing parser must produce a fixed, non-sensitive result.
    _PARSER_AVAILABLE = False
else:
    _PARSER_AVAILABLE = True


REQUIREMENTS = Path(__file__).parent.parent / "requirements.txt"
MESSAGES = {
    "PROFILE_REQUIRED": "Explicit FINLENS_SERVER_PROFILE=sec_readonly is required.",
    "PARSER_UNAVAILABLE": "Supported requirement metadata parsing is unavailable.",
    "REQUIREMENTS_INVALID": "Declared requirements are missing, unsupported or malformed.",
    "METADATA_INVALID": "Dependency metadata is missing, malformed or indeterminate.",
    "METADATA_AMBIGUOUS": "Multiple installed distributions declare the same identity.",
    "DEPENDENCY_MISSING": "An active declared dependency is not installed.",
    "DEPENDENCY_INCOMPATIBLE": "An installed dependency violates an active requirement.",
    "SENTENCE_TRANSFORMERS_INCOMPATIBLE": "Installed sentence-transformers violates its declared range.",
    "PYTHON_INCOMPATIBLE": "Python violates an active distribution's Requires-Python declaration.",
    "INSPECTION_FAILED": "Offline metadata inspection could not be completed.",
    "ARGUMENTS_UNSUPPORTED": "This diagnostic accepts no command-line arguments.",
}
LIMITATIONS = (
    "Model artifacts and numerical compatibility are not assessed.",
    "Database privilege safety and Next.js proxy correctness are not assessed.",
    "Runtime performance and concurrency are not assessed.",
    "Private deployment is not authorized; overall private-runtime status remains BLOCKED.",
)


class _Rejected(Exception):
    def __init__(self, code):
        self.code = code


def _reject(code):
    raise _Rejected(code)


def _requirement(text):
    requirement = Requirement(text)
    # A URL's identity/content cannot be established using version metadata.
    if requirement.url is not None:
        _reject("METADATA_INVALID")
    return requirement


def _roots(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        roots = [_requirement(line.strip()) for line in lines
                 if line.strip() and not line.lstrip().startswith("#")]
        if not roots:
            _reject("REQUIREMENTS_INVALID")
        return roots
    except Exception:
        _reject("REQUIREMENTS_INVALID")


def _inventory(distributions):
    installed = {}
    for distribution in distributions:
        names = distribution.metadata.get_all("Name", [])
        if len(names) != 1:
            _reject("METADATA_INVALID")
        try:
            name = canonicalize_name(names[0], validate=True)
        except Exception:
            _reject("METADATA_INVALID")
        installed.setdefault(name, []).append(distribution)
    return installed


def _distribution(distribution, name):
    # Read metadata only. Do not inspect package modules, files or model caches.
    raw = distribution.read_text("METADATA")
    if not raw:
        _reject("METADATA_INVALID")
    try:
        parsed = Metadata.from_email(raw, validate=True)
    except Exception:
        _reject("METADATA_INVALID")
    if canonicalize_name(parsed.name, validate=True) != name:
        _reject("METADATA_INVALID")
    if parsed.requires_python is None or not str(parsed.requires_python):
        # Requires-Python is optional in the metadata standard, but without it
        # this diagnostic cannot establish declared interpreter compatibility.
        _reject("METADATA_INVALID")
    return parsed


def _check_dependencies(roots, distributions, environment):
    installed = _inventory(distributions)
    python = Version(environment["python_full_version"])
    if environment["python_version"] != ".".join(map(str, python.release[:2])):
        _reject("METADATA_INVALID")
    pending = list(roots)
    parsed = {}
    active_extras = {}
    expanded = {}
    errors = set()
    while pending:
        requirement = pending.pop(0)
        # Child markers have already been evaluated with their parent's extras.
        # Root markers are evaluated in the base (no extras) environment below.
        name = canonicalize_name(requirement.name, validate=True)
        candidates = installed.get(name, [])
        if not candidates:
            errors.add("DEPENDENCY_MISSING")
            continue
        if len(candidates) != 1:
            errors.add("METADATA_AMBIGUOUS")
            continue
        if name not in parsed:
            try:
                parsed[name] = _distribution(candidates[0], name)
            except _Rejected as exc:
                errors.add(exc.code)
                continue
        package = parsed[name]
        if not requirement.specifier.contains(
            package.version, prereleases=requirement.specifier.prereleases or False
        ):
            errors.add("SENTENCE_TRANSFORMERS_INCOMPATIBLE" if name == "sentence-transformers"
                       else "DEPENDENCY_INCOMPATIBLE")
        if not package.requires_python.contains(
            python, prereleases=package.requires_python.prereleases or False
        ):
            errors.add("PYTHON_INCOMPATIBLE")
        extras = active_extras.setdefault(name, set())
        extras.update(canonicalize_name(extra) for extra in requirement.extras)
        if not extras.issubset(set(package.provides_extra or ())):
            errors.add("METADATA_INVALID")
            continue
        if name in expanded and expanded[name] == extras:
            continue
        expanded[name] = extras.copy()
        for child in package.requires_dist or ():
            contexts = [""] + sorted(extras)
            if child.marker is None or any(
                child.marker.evaluate({**environment, "extra": extra}) for extra in contexts
            ):
                try:
                    pending.append(_requirement(str(child)))
                except _Rejected as exc:
                    errors.add(exc.code)
    return errors


def _report(profile_ok, codes):
    return {
        "status": "BLOCKED",
        "exit_code": 1,
        "checks": {
            "explicit_profile": "PASS" if profile_ok else "FAIL",
            "python_dependency_metadata": "FAIL" if codes - {"PROFILE_REQUIRED"} else "PASS",
        },
        "diagnostics": [{"code": code, "message": MESSAGES[code]} for code in sorted(codes)],
        "limitations": list(LIMITATIONS),
    }


def inspect_runtime(*, requirements_path=REQUIREMENTS, environ=None):
    """Return fixed diagnostics; never echo metadata, environment or exceptions.

    Process environment only: no dotenv loading or profile fallback. Tests may
    supply a synthetic requirements path/environment and mock metadata discovery.
    """
    profile_ok = False
    codes = set()
    try:
        environment = os.environ if environ is None else environ
        profile_ok = environment.get("FINLENS_SERVER_PROFILE") == "sec_readonly"
        if not profile_ok:
            codes.add("PROFILE_REQUIRED")
        if not _PARSER_AVAILABLE:
            codes.add("PARSER_UNAVAILABLE")
        else:
            marker_environment = default_environment()
            # Parse root markers before traversal. The graph then evaluates each
            # transitive marker in the context of its declaring distribution.
            roots = _roots(requirements_path)
            active = [root for root in roots if root.marker is None or
                      root.marker.evaluate({**marker_environment, "extra": ""})]
            # Pass parsed roots rather than rereading the file during traversal.
            codes.update(_check_dependencies(active, metadata.distributions(), marker_environment))
    except _Rejected as exc:
        codes.add(exc.code)
    except Exception:
        codes.add("INSPECTION_FAILED")
    return _report(profile_ok, codes)


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    result = inspect_runtime()
    if arguments:
        result["diagnostics"].append({"code": "ARGUMENTS_UNSUPPORTED",
                                      "message": MESSAGES["ARGUMENTS_UNSUPPORTED"]})
        result["diagnostics"].sort(key=lambda item: item["code"])
    print(json.dumps(result, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
