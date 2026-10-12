# Synthetic Tiingo EOD fixtures

These three JSON files are handwritten, fictional test data using the documented
EOD field names supplied in the task. They were not downloaded from Tiingo and
prove no entitlement, adjustment algorithm, provider origin or production coverage.
Dates are UTC-midnight session labels. The test format explicitly declares
splitFactor = new shares / old share (2-for-1 is 2; 1-for-10 is 0.1).
Production confirmation of that direction remains an external prerequisite.

divCash is only an ex-date amount indicator: it does not establish share basis,
ordinary versus special classification, gross/net treatment or completeness.
Adjusted fields are preserved for inspection, never used by the return engine.
All EOD-only normalized publications remain unavailable, including ordinary bars.

A future separately reviewed adapter needs verified, instrument/date-bound full
corporate-action inventories and coverage for each adjacent exchange session:
split direction/effective date, ordinary/special/unsupported distribution
classification, currency/amount/gross treatment, dividend share basis, any specific
split references and same-day ordering. A neutral splitFactor/divCash row cannot
attest that no other action occurred. Adjustment differences require a verified
adjustment policy and relevant complete event history, potentially beyond the
response range. Source request/response custody and provider licensing are also
outside this offline adapter. No completeness override exists here.
