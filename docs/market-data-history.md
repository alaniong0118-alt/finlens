# Offline raw-close history inspector

This local inspection tool composes the existing Tiingo EOD normalizer with a
bounded raw-history view. It does not acquire data, authenticate evidence, persist
data or publish eligible returns. Fictional acceptance data is confined to tests.

From `backend` using the existing local Python environment:

```powershell
.venv/Scripts/python.exe -B -m scripts.inspect_market_history --payload tests/fixtures/tiingo_eod/ordinary.json --context tests/fixtures/market_history/synthetic-context.json
.venv/Scripts/python.exe -B -m scripts.inspect_market_history --payload tests/fixtures/tiingo_eod/ordinary.json --context tests/fixtures/market_history/synthetic-context.json --format json
```

Output goes only to stdout. Invalid input returns exit 2, a stable sanitized code
on stderr, and no observation output. Successful inspection returns 0 even when
publication/returns are blocked: exit 0 means the inspection succeeded, never
that data is admitted. The path-based CLI supports Windows trusted, quiescent
directory trees on explicitly classified local fixed-volume roots only. Other
platforms and unclassifiable roots fail closed; the bytes-only projection remains
separately usable and has no filesystem dependency.
Use `-B` (or PYTHONDONTWRITEBYTECODE=1) to avoid interpreter bytecode writes.

## Filesystem boundary and supported paths

Ordinary relative paths (including `./tests/...`) and drive-qualified absolute
paths are accepted only after lexical validation. Relative paths are joined to
the lexically validated current directory without resolve/realpath. Rejected
spellings include UNC/device/extended namespaces, URLs, alternate streams,
reserved Windows names, trailing-dot/space aliases, `..`, drive-relative `D:file`
and root-relative `\file`. Parent traversal is rejected rather than normalized.

Root classification queries QueryDosDeviceW before GetDriveTypeW. Only a single
direct `\Device\HarddiskVolumeN` mapping and DRIVE_FIXED (3) are supported.
Network mappings, SUBST/DOS-device redirections, multiple/unknown mappings and
removable/CD/RAM/unknown drive types reject. No directory lookup occurs if this
classification fails; there is no fallback classifier or bypass flag.

Both input paths' ancestors are preflighted before either leaf is inspected or
opened. Each chain is checked from drive root to immediate parent, stopping at
the first missing/inaccessible/non-directory component, symlink, junction or any
FILE_ATTRIBUTE_REPARSE_POINT. Descendants are never inspected after rejection.
The relevant ancestry is revalidated immediately before each read. Only then is
the leaf inspected with lstat; reparse/nonregular leaves reject. That metadata is
reused for the existing opened-handle identity check and limit-plus-one read.

These path checks **do not provide race-proof filesystem or network containment**.
Drive mappings, parents or leaves can change after a check, including between two
ancestor checks or before opening. The identity check is after opening and cannot
undo a remote lookup. File content can also change while its identity stays the
same. Attacker-writable/concurrently replaceable trees and changing drive mappings
are unsupported operating conditions. Do not use this CLI for those inputs.
Python socket audit hooks do not contain Windows filesystem redirector traffic.
Stronger protection would require separately reviewed OS handle-based traversal
and replacement controls, which this inspector does not implement.

## Context contract

The synthetic-context fixture is the complete schema example. Root fields:

- `schema_version`: integer 1.
- `input_kind`: `synthetic` or `unverified_local`, both caller declarations.
- `adjustment_basis`: `raw` only.
- `request`: exactly one security, listing, supplied calendar, source, format,
  symbol and effective mappings, coverage dates, publication ID/version/time.
- Optional `expected_bindings`: non-null lowercase SHA256 strings named
  `normalized_content_sha256` and/or `publication_manifest_sha256`. A mismatch
  rejects with `stale_history_binding`. They are content pins, not custody proof.

Every nested record uses exact keys/types; unknown/missing fields, duplicate keys,
floats/nonfinite metadata numbers, coercible booleans and unsupported bases reject.
Dates use YYYY-MM-DD; timestamps require ISO date/time/seconds and an explicit
offset or Z. Source `available_at` and listing/mapping end dates may be null.
Metadata text is bounded printable ASCII to prevent terminal control injection.
The source response hash must match the original payload bytes. Do not rewrite
provider bytes through a float-decoding JSON parser before inspection.

Context <=256 KiB; payload <=4 MiB. Inclusive coverage spans at most 366 calendar
dates, with at most 366 explicitly supplied sessions. Bounds reject, never truncate.
The minimal context supports initial publications only, with no predecessor input,
corporate-action inventory, completeness flag or custody authorization mechanism.

## Financial semantics and trust

The table labels exact fixed-point Decimal strings as **Unadjusted close**, with
declared currency and explicit present/missing observations. JSON also includes
the supplied close timestamp and digest-bound observation IDs. No monetary float
conversion, rounding, return calculation, adjusted substitution, gap bridging,
forward fill or interpolation occurs. Sessions come only from the supplied calendar;
weekdays, missing bars and ticker/CIK do not establish calendar or security continuity.

`input_kind`, `provenance_state=unverified`, `trusted_custody=false`, observation
state, existing normalization/publication state and `return_state=unavailable`
remain separate. Adjusted series are unavailable. All original blocker reasons
survive. The fixture deliberately leaves continuity unresolved, producing an
unsupported publication. Declaring continuity verified may remove that one reason
but never authenticates it or removes missing corporate-action coverage.

Original response SHA256, normalized-content SHA256 and publication-manifest SHA256
remain distinct. A fourth hash fingerprints the original metadata context bytes.
Optional pins detect stale bindings, including unchanged raw closes with changed
sidecar values or receipt metadata. Without an external pin, recomputing hashes
describes a new caller-supplied input; it cannot establish which version is true.

Retrieval, availability and publication timestamps are labelled declarations.
Unknown source availability stays null; freshness stays unknown. Knowledge mode
remains retrospective_revised. The provider's UTC-midnight field is a session-date
label, not a close instant. Calendar time-zone/version and supplied close times are
preserved without claiming independent calendar authority or point-in-time data.

## Synthetic fixtures and remaining gates

The ordinary/split/dividend payloads in `backend/tests/fixtures/tiingo_eod` are
existing handwritten fictional data. This context binds the ordinary fixture's
exact bytes. For another local fixture, explicitly provide its matching hash in
an in-memory context or a separately supplied local context; no hash is repaired
automatically. A synthetic label itself is not proof that arbitrary input is fictional.

Real-data admission still requires instrument/request/response custody, calendar
and currency authority, provider rights for retention/display/redistribution, and
independent adjustment semantics. Action-aware returns additionally require complete
relevant event coverage, split direction/dates, cash classification/share basis,
currency, gross/net treatment and same-day ordering. Existing EOD indicators cannot
satisfy these gates. No current provider terms or entitlement are asserted here.

## Focused validation

From `backend`:

```powershell
.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider tests/test_market_history.py tests/test_inspect_market_history.py -q
```

Tests cover only the new projection/CLI boundary, using synthetic data and in-memory
mutations. The subprocess acceptance audit checks Python write/socket events and
forbidden database/model dependencies; it is not an OS network-containment test.
Mocked ordering, reparse/root rejection and replacement-window tests exercise the
supported path checks without real remote shares or unsafe junctions. Completed
normalizer and return-engine suites are not repeated.

Actual ordinary-fixture stdout excerpts (2026-10-16):

```text
Input: synthetic | provenance: unverified | trusted custody: false
Normalization: blocked | publication: unsupported | returns: unavailable | adjusted series: unavailable
Session date | Unadjusted close | Declared currency | Observation state
2026-01-05 | 100 | USD | present
2026-01-06 | 105 | USD | present
```

JSON also reports `available_at: null`, `freshness_state: unknown` and these
separate identifiers:

```text
response_sha256: bc9d0af20c28aead8f51e191c718b56b332420c2ab82a12da4530ba51e22f442
normalized_content_sha256: 54527de98d329875e393a7e673a9dcb2b90a025d46cab503e8e3f43ecbb215fc
publication_manifest_sha256: 5c3d90b69ce8e495faf0878345d74f65e363242a98c49a00c5de9261ec75851c
```
