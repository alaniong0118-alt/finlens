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

## MD-WIKI increment 1: pure offline observation adapter

`app.nasdaq_wiki_adapter.inspect_wiki_bytes(payload, receipt, request)` accepts
original response **bytes**, original operator receipt **bytes**, and a frozen
`WikiInspectionRequest`. It opens no files, starts no services and makes no
network/provider/database calls. There is no CLI or integration into the Tiingo
inspector. The existing market contracts and return engine are unchanged.

The request requires the provider ticker, independently expected original-response
SHA256, expected run ID, acquisition start/end dates and selected start/end dates.
Dates are exact Python `date` instances. `input_kind` is `synthetic` or
`unverified_local`, a declaration only. An optional `expected_receipt_sha256`
provides an external metadata pin. Hexadecimal hash case is immaterial; payload
whitespace, numeric lexemes and every original byte remain significant. Hashes
are never repaired or calculated from reserialized provider JSON.

### Supported schema and bounds

The supported response has exactly `datatable` and `meta`; the table has exactly
`columns` and `data`, and metadata has exactly `next_cursor_id`, which must be
explicitly null. Every column has exactly `name` and `type`. Supported names/types:

| Column names | Exact declared type |
|---|---|
| ticker | String |
| date | Date |
| open, high, low, close | BigDecimal(34,12) |
| volume | BigDecimal(37,15) |
| ex-dividend | BigDecimal(42,20) |
| split_ratio, adj_volume | double |
| adj_open, adj_high, adj_low, adj_close | BigDecimal(50,28) |

Columns and matching cells may be reordered; the schema must otherwise match
exactly. Unknown columns/types/envelopes reject instead of triggering inference.
Increment 1B corrected volume's exact observed declaration to BigDecimal(37,15);
the obsolete BigDecimal(37,0) and arbitrary alternative types remain rejected.
Read-only acceptance against the three retained, independently pinned originals
now establishes compatibility with those specific bytes, as recorded below.

Limits reject rather than truncate: 4 MiB per response, 64 KiB per receipt and
canonical request context, 1,000 response rows, one to three receipt ticker
records, and 1,461 inclusive acquisition calendar dates. Empty acquisition
responses reject; a valid selection containing no observations returns an empty
tuple with `empty_selected_observations`. A selected window must be within the
acquisition window. Every acquisition row is validated before selection.

JSON rejects duplicate keys, malformed UTF-8, nonfinite values, excessive numeric
tokens/precision/magnitude, and malformed nested structures. Financial numbers
are decoded directly to bounded `Decimal` values, never through binary floats.
Raw and adjusted OHLC must be positive and internally coherent; volume is
nonnegative, raw volume integral, ex-dividend nonnegative and split ratio positive.
Adjusted fields undergo structural validation only and are never projected.

### Operator receipt and source bindings

The supported original receipt shape is demonstrated by the fictional in-memory
receipt in `tests/test_nasdaq_wiki_adapter.py`. Root and record keys are exact.
The pilot/source labels must identify the limited original WIKI/PRICES acquisition;
run ID must match the explicit expectation. Requested tickers and records must
be unique and agree. Request counts must equal the bounded ticker inventory;
page size is exactly 1,000. Receipt declarations require completed acquisition,
HTTP 200, `CAPTURED_STRUCTURAL_ONLY`, `has_more_pages=false`, and
`financial_quality_approved=false`. An approval flag cannot grant eligibility.

Each record's filename must be exactly
`WIKI_PRICES_<ticker>_<requested-start>_<requested-end>.json`; filenames are
validated strings, never filesystem paths to open. Credential-free query metadata
must contain exactly one of each: `ticker`, `date.gte`, `date.lte`,
`qopts.per_page`, with values matching that record's ticker/request dates/1,000.
Credentials, extra/duplicate parameters, blank values and mismatched bounds reject.
Errors contain stable market-contract codes, without echoing untrusted metadata.

The selected record's hash and byte size must match the supplied response, whose
hash must independently match the request pin. Actual row count and date extrema
must agree with the receipt; rows must have the requested ticker, unique dates
and dates inside acquisition bounds. Nonselected records are structurally checked;
their response contents/hashes are **not cross-file verified** by a one-response
call. Acquisition/request counts remain operator declarations, not network proof.

`captured_at_utc` accepts a valid UTC timestamp with up to seven fractional digits
and is returned verbatim, including trailing zeros. Its whole-second date/time
must not precede the run ID's start time or the records' observed dates. Fractional
text is not converted to a microsecond timestamp or silently rounded. It is a
run capture timestamp; `retrieved_at` and historical `available_at` stay null.

### Projection and financial restrictions

The frozen result holds a frozen request, tuple of frozen raw-close observations,
and tuple of blockers. Fresh JSON projections contain exact fixed-point close
strings, provider date labels and zero-based original row indices. Vendor dividend
and split indicators are explicitly unverified indicators, never canonical actions.
Acquisition bounds/count/extrema and selected bounds/count remain distinct.
Response, receipt, canonical inspection context and inspection-result SHA256 are
separate bindings. The inspection hash includes all three input bindings, version,
selected rows, blockers and the known dataset limitation. It is not a publication
manifest or market-data version pin; original bytes bind even unprojected fields.

All results remain financially blocked: custody, security identity, currency
authority, listing continuity, calendar completeness, corporate-action completeness
and adjustment semantics are unverified. Freshness is unknown and knowledge mode
is retrospective/revised. No security/company/CIK/listing identity, currency, MIC,
session close time, calendar, publication, version pin or action coverage is invented.
No adjusted prices, percentage changes, admitted returns, compounding or performance
values are produced. Receipt/hash consistency proves neither authenticated provider
custody nor financial correctness.

The coordinator-supplied missing AAPL dividend warning for 2017-11-10 and 2018-02-09
is retained as a **dataset limitation**, including for synthetic inspection. It is
not a claim that fictional test prices independently establish those events.
Zero ex-dividend/default split indicators never imply complete action coverage.
Positive indicators add blockers without removing any existing blocker.

Missing dates remain absent; there is no forward fill, interpolation or inferred
exchange calendar. In particular, shared-price filtering must not bridge the
reported 2017-08-07 gap. Once proper financial evidence exists, the unchanged
`market_returns.calculate_returns`, `align_returns` and `reinvested_growth` remain
the calculation infrastructure; this adapter supplies no alternative engine.

### Focused synthetic verification

From `backend`, using the existing environment:

```powershell
.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider tests/test_nasdaq_wiki_adapter.py -q
```

All response/receipt fixtures are fictional bytes constructed inside that test
module. Focused tests cover exact and immutable projections, bindings, schema,
pagination, numeric/date/resource limits, metadata/query rejection, missing dates,
capture precision, non-promotion of actions/adjustments and offline isolation.
The guarded fresh-process test checks imports and file/socket/process audit events
during inspection; it does not claim OS-level containment. No completed Tiingo or
market-return suites, browser/API checks or financial eligibility acceptance ran.

Increment 1B focused regression: **175 passed, 0 failed, 0 skipped**, comprising
the existing 172 cases and three targeted volume-schema cases. Read-only local
acceptance used the public interface with explicit response and receipt hash pins:

| Retained original | Acquired rows | Selected rows | 2017-08-07 present |
|---|---|---|---|
| AAPL | 961 | 955 | No |
| MSFT | 962 | 956 | Yes |
| COST | 961 | 955 | No |

Requested acquisition: 2014-06-01 through 2018-03-27; actual extrema:
2014-06-02 through 2018-03-27; selected extrema: 2014-06-10 through 2018-03-27.
Every selected date/close and original row reference matched the source bytes.
The three original SHA256 pins and recorded receipt pin matched independently
before invocation and on fresh reads afterward. Capture precision and all required
financial blockers survived; trusted custody remained false and financial
eligibility blocked. These checks establish bounded structural compatibility,
not provider authentication, action completeness or eligible returns.
