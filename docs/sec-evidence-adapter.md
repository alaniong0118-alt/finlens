# Inactive original SEC evidence adapter

The adapter is an enabling mechanism. Production selection, denominator,
withdrawal and evidence-policy registries are empty. It activates no metric.
Financial formulas, revenue bases, period rules and Gross Margin safeguards
remain in the existing financial engine. See the [authorization contract](financial-metrics.md#inactive-bounded-revenue-authorization-foundation).

`load_financial_metrics` supplies only its already-loaded issuer facts and existing
database session to `sec_evidence_adapter.load_production_evidence`. No HTTP
parameter can supply a path, SourceEvidence, approval, policy or production flag.
Synthetic evaluator fixtures have no production policy and cannot enter this path.
Empty financial permission registries return before configuration, file access,
transaction checks or evidence queries. Missing evidence policies also abstain.

## Trusted inputs and boundaries

`FINLENS_SEC_ORIGINAL_STORE` is an explicitly configured absolute operator-owned
directory. It has issuer/accession/original-filename layout, outside Git. No default
machine path is shipped or configured by this change. Reviewed immutable policies
contain basenames, exact filing metadata, original-byte hashes/lengths, pinned
capture-receipt hashes, taxonomy URIs, exact statement/fact/context locators, scope
reviews, parser revision, approval content/version and database snapshot digest.
Symlink/junction redirection and traversal are rejected. The initial supported
store contains `.htm`/`.html` originals, with receipt/report JSON alongside them.

Receipts must reconcile with the exact official SEC HTTPS document URL, issuer,
accession, filename, HTTP 200, exact original bytes, capture path and zoned retrieval
times. Receipt hashes are independent reviewed trust anchors. They attest to local
capture provenance; they are **not SEC signatures**. Accession and filed date are
not inferred from statement text or HTTP Last-Modified. They must match pinned
publication metadata from the existing provenance interface. That metadata's
source lineage remains an activation-review responsibility.

## Verification and completeness

Offline standard-library XML parsing permits UTF-8/ASCII well-formed Inline XBRL,
rejects DTD/entities and never fetches schemas, transforms or external resources.
QName resolution uses each element's namespace scope; rebinding, duplicate IDs,
unknown contexts, ambiguous periods and unsupported markup fail closed. The small
allowlist supports simple monetary nonFraction observations, USD, exact Decimal
sign/scale and the 2020 `num-dot-decimal` transform. The filing's DEI identity is
checked; its English month-name date transform is explicitly supported. Unknown
transforms, nil, fractions, numeric continuations, tuple/target attributes and nested
numeric markup abstain. Parser revision `sec-inline-v2` preflights the entire original
before candidate construction: unsupported Inline namespaces (including 2008),
unknown Inline constructs and tuples reject the document rather than disappear
from its inventory. Filing-identity facts accept only id/name/contextRef/format;
nil and extra attributes are rejected. Explicit target-instance attributes,
including empty targets, and targeted resources are unsupported. Contexts and units
must be inside the default header/resources structure.

Filing identity requires default body or header/hidden ancestry. Monetary facts
may additionally occur in recognized narrative TextBlock/continuation containers;
the naming restriction limits supported structure and does not establish economic
scope. Their explicit contexts, units and values still enter the complete raw
manifest. Arbitrary Inline ancestry is rejected; DEI identity cannot come from
narrative containers. This intentionally does not implement all Inline XBRL.

Context issuer/dates and explicit/typed dimensions are inspected. Reviewed
financial operands must be undimensioned. Known dimensioned observations are
excluded from the consolidated candidate population only after their contexts
are inspected. Empty/unknown dimensional containers fail. Equality of reported
amounts never establishes consolidated economic scope; the independent policy
must review the exact statement and operand scope.

Expat locates statement tables in original bytes; Unicode character ranges are
derived without cleaning or reserialization. A reviewed fact must occur in its
exact containing table/context with a pinned statement hash. The resulting
SourceEvidence fingerprint also binds the **entire reviewed policy**, except its
approval digest (which would be circular). Receipt, snapshot or parser changes
therefore cannot reuse an old authorization fingerprint.

The loader requires PostgreSQL repeatable-read/read-only transaction state. It
uses all previously loaded eligible issuer facts, including same-end/kind changed
starts, without ranked-selection filtering. It reads the issuer's complete local
publication inventory and version triple in that same snapshot. Policy digests
pin those inventories; a new publication, same-value amendment or changed version
invalidates evidence even before new facts are ingested. Only the configured
issuer directory and its immediate accession directories are inspected. Their
original-file inventory must exactly match the reviewed artifact manifest.
Across those originals, all undimensioned eligible Revenue/Net Income observations
for the relevant end/kind must match the complete stored and reviewed manifests.
Repeated identical source observations deduplicate; contradictions, missing
operands, extra facts, differing vintages and unreviewed starts are rejected.

Completeness is relative to **known local originals, publications and stored raw
eligible facts**. The adapter cannot prove that all SEC amendments have been
acquired, nor recover information omitted by historical ingestion. No network
acquisition or reconstruction is performed.

## Approval lifecycle and future review

The existing evaluator owns separate selection/denominator permissions, immutable
versions and explicit withdrawal/supersession. The adapter reuses those lifecycle
and manifest validators; missing/ambiguous policy or evidence produces no proofs.
Fully withdrawn scopes are skipped only after the existing evaluator checks their
lineage and explicitly reports `approval_withdrawn`. They require no policy or
artifact and do not disable unrelated active scopes. Active ambiguity, invalid
lineage, missing supersession and withdrawn successors never revive predecessors.
Verification is uncached and conservative: failure in an applicable active policy
returns no partial evidence. Multiple policies sharing operands can produce
distinct proof fingerprints and consequently abstain; combined activation is
outside the initial single-pair boundary.

Before any future activation, an independent reviewer must first approve the
artifact/receipt/provenance, accounting scope, complete manifests and versioned
policy. Review construction order is: pin independent artifacts/locators/snapshot
and approval reference; parse original observations; construct reviewed evidence
and fingerprints; construct the financial authorization; finally pin its digest
in the policy. Changing any reviewed policy input requires new evidence bindings
and a new explicitly reviewed authorization version. No builder or activation
endpoint is included here.

Initial proposed activation remains only the separately reviewed AAPL Net Margin
pair. Historical Revenue and combined permissions require separate review and
evidence. Astra must review namespace/transform restrictions, receipt and filed-date
trust anchors, accounting scope, manifest closure, lifecycle/permission isolation,
and immutable/append-only store operation. The filesystem is not transactionally
snapshotted with PostgreSQL; store write permissions and atomic append-only capture
are operator responsibilities. Each request verifies the bytes it actually read.

## Validation

Focused tests live in `backend/tests/test_sec_evidence_adapter.py`. Synthetic
policies replace internal trusted constants only inside isolated tests; shipped
registry emptiness is asserted before monkeypatching. An optional external-artifact
test reads the already verified AAPL original in place, without copying it into
Git, creating a real approval or querying SEC. A fresh clone skips only that test
if the external artifact is absent; synthetic parser and rejection tests still run.
