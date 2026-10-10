# Dormant AAPL Net Margin proposal for Astra High

Status: review preparation only; **not approved or activated**. Baseline main /
cca903b11d9242576ce41d32ca1b2859a0ab3e9a. See the [adapter contract](sec-evidence-adapter.md)
and [proposal records](../backend/app/aapl_net_margin_proposal.py).

## Exact permission and original bases

Proposed reference: permission `denominator:net_margin`, approval ID
`aapl-net-margin-0000320193-26-000020-q3`, version **1**. Only Net Margin may use
this exact Revenue/Net Income pair. Formula remains net income / revenue.
Revenue's original basis remains `customer_contract`, never globally `total_revenue`.
The separately reviewed statement establishes consolidation for this pair; matching
amounts alone do not establish scope. No Revenue selection permission, global
equivalence, historical Revenue permission or Gross Margin permission is proposed.

Both identities bind CIK `0000320193` (AAPL), SEC Company Facts API / us-gaap,
accession `0000320193-26-000020`, 10-Q, filed **2026-07-31**, direct-quarter
**2026-03-29 through 2026-06-27**, USD. Database IDs are audit cross-references,
not authorization keys; financial source identity excludes DB IDs/frame/FY labels.

| Operand | Concept | Exact USD | DB ID | Original fact | Economic scope |
| --- | --- | ---: | ---: | --- | --- |
| Revenue | RevenueFromContractWithCustomerExcludingAssessedTax | 109,417,000,000 | 1853 | f-56 | consolidated_revenue |
| Net income | NetIncomeLoss | 29,789,000,000 | 1976 | f-104 | consolidated_net_income |

Original locators: `aapl-20260627.htm`, table ordinal **12**, context **c-18**,
verified absence of dimensions, original USD measure. The current-quarter column
reports Total net sales and Net income on the condensed consolidated statement.
Statement character range **125113:187899** is independently derived by the parser;
policy pins table/fact/context and the statement hash, rather than trusting offsets.

## Immutable pins

Original source: `https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/aapl-20260627.htm`.
Store-relative layout: `0000320193/0000320193-26-000020/aapl-20260627.htm`.
Artifact: **1,018,326 bytes**, SHA-256
`ff8ff7fb32493f9ca51b5d3afa6b336adacea503f7e50e53618a6e585e7eac07`.
Receipt: `retrieval-20261010T111011020789Z.json`, SHA-256
`0d3b3c51c53780ffa7564d57dfa6450d5a5041afb62855619ffcd8c5a3bee62a`.
Receipt reconciles official URL, HTTP 200, capture times and exact bytes/path.
The earlier failed preservation receipt is not this capture's trust anchor.

Taxonomies: `http://fasb.org/us-gaap/2025`, `http://xbrl.sec.gov/dei/2025`;
parser `sec-inline-v2`. Statement SHA-256:
`417819dec67798830dd5659634bf5e9b3bfc130ad766946d4e883dc2b194889b`.
The complete current-quarter raw candidate manifest has exactly the two identities
above; repeated identical original observations deduplicate without hiding conflicts.
The known local original inventory contains only this original document.

Company publication versions: **data 1 / facts 0 / evidence 1**. Complete AAPL
publication inventory (both records are included in the snapshot pin):

| Accession | Document | Form / filed | Chunks | Publication data version | Content digest |
| --- | --- | --- | ---: | ---: | --- |
| 0000320193-25-000079 | aapl-20250927.htm | 10-K / 2025-10-31 | 92 | 1 | 8fafe74d5952ed4c7820fd0531c8a3a387c8b4d1422f70ded9dc5121d8092a81 |
| 0000320193-26-000020 | aapl-20260627.htm | 10-Q / 2026-07-31 | 37 | 0 | 5fcca79f7e4f27d26cf769f2c6604ebae6ea35e3bba45e7762fe0c13bd429eda |

Both publication configurations are
`parser-v1/chunk-2500-overlap-250/sentence-transformers/all-MiniLM-L6-v2`.
These publication digests describe indexed evidence, not original SEC bytes.
Snapshot SHA-256: `01b530f47b1d7b15bd7306af097d3bf972eeef17dabdc72467e195451a540dd9`.

Literal proposed policy SHA-256 (excluding circular approval digest):
`69ec848cfd38d3f827abd748d4efccd744777c8a2b8cf02b677166daa3749a53`.
Revenue evidence fingerprint:
`7dbb968795450f8003e3093e66229a98b565f0e7b2139656ac437e72f18fb949`.
Net Income evidence fingerprint:
`7b5a3312bf2e56edbaa7210d5acbbee29c6426acae626a564b903060ed75e964`.
Authorization content SHA-256:
`8b39531ff03ffd1f4a0fb9b58a20900aed6ae599f5dc12a9726ccfaaf1f56253`.
These fingerprints were verified against parsed original observations and the
literal proposed policy, not generated from synthetic statement text. Decimal
representations in policy/approval JSON are pinned too; numerically equivalent
literal rewrites still require reviewed repinning. No automatic pin renewal exists.

## Disabled activation boundary and lifecycle

The proposal is a side-effect-free module with immutable literal descriptors.
No production loader or registry imports it. All four registries remain empty;
even importing the proposal performs no registration, configuration or evidence I/O.
There is no runtime environment flag, HTTP switch or activation helper.
The activation path is deliberately a **separate reviewed code patch** registering
exactly the denominator record and matching evidence policy. Revenue selection and
withdrawal registries remain empty at initial activation; global equivalences stay empty.

The operator must separately configure `FINLENS_SEC_ORIGINAL_STORE` to an absolute,
operator-owned original store outside Git. No machine-specific root is embedded in
the proposal or calculation engine. The existing receipt binds its original capture
path: relocating it will fail validation and requires separately reviewed provenance,
not a silent path rewrite. Symlink/junction redirection fails closed. Store access
must preserve original bytes/receipts and enforce immutable append-only operation.

Withdrawals/supersessions use the existing explicit versioned lifecycle. A newer
approval requires explicit predecessor supersession; a withdrawn successor never
revives the predecessor, including successors moved to another period. New facts,
amendments, publications, versions, original files or changed evidence invalidate
the pins and require a new independent review/version, never automatic fallbacks.

## Validation and remaining review gates

Focused tests assert real production emptiness before test substitutions. The
optional external acceptance cases require `FINLENS_REVIEW_SEC_ORIGINAL_STORE`.
They read real originals and receipts without copying or modification and use
detached publication/fact fixtures; isolated monkeypatch installs records only in
the test process. A separate read-only PostgreSQL dry run validates the same
literal records against current real publication/candidate data, without registering
them. No production installation or environment modification is performed.

Before activation, obtain separate user approval and Astra High approval of the
exact records, then recheck current raw candidates, publication snapshot and bytes.
This review has bounded local completeness, not proof that all SEC amendments exist.
Receipts are local trust anchors, not SEC signatures; filed-date source lineage is
the publication interface and must be independently accepted by the reviewer.

Specific Astra High questions:

1. Do the exact statement column, context, concepts and provenance establish
   consolidated NetIncomeLoss / Total net sales for this specific pair while
   retaining the customer-contract basis elsewhere?
2. Are the capture receipt and filed-date publication lineage acceptable independent
   trust anchors, including the target publication's legacy data version 0?
3. Are the exact two-candidate manifest, two-publication snapshot and one-original
   inventory sufficiently bounded, with fail-closed handling of amendments,
   restatements, changed starts and later vintages?
4. Are dormant registration separation, immutable pin/fingerprint construction,
   revocation/supersession behavior and Gross Margin/Revenue isolation adequate?
5. Is the operator's append-only store/path configuration acceptable given that
   filesystem bytes and PostgreSQL are not one atomic snapshot?
