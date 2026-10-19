# Read-Ahead Fixture Canonical Birth

The disposable `read_ahead_entry` browser fixture must use the existing
`tests.counter_family_canonical091.add_card` materializer, as the core spell-entry
goldens already do. The full official object for The Phasing of Zhalfir does not
contain creature power/toughness fields. The older flattened-row constructor
unconditionally indexes those fields and cannot consume this canonical object.

The correction changes only the import inside this fixture branch. Canonical
data, normalization, factory construction, rules, publication, browser actions,
assertions and time bounds remain unchanged. The other `cards=ROWS` route families
(devotion and the Stinkweed Imp wheel pose) still use their existing flattened
rows; this change does not migrate or certify them.

`test_browser_read_ahead_canonical_birth.py` extracts the actual branch from the
fixture source without importing the HTTP/server module. Only `publish` is
replaced with a capture of the real state and deck. The test runs real card
materialization, spell resolution, pending entry choice, checked chapter-two
selection and snapshot round trips, retaining complete canonical printed facts.

This is pure branch-fragment evidence, not HTTP or native-browser qualification.
The hosted failure displayed `TypeError: Failed to fetch` and ended in the
unchanged saga-choice wait; its actual HTTP response and transport cause were not
captured. The offline constructor failure must not be relabeled as an observed
hosted HTTP500 or a proven CORS/abort cause. The unchanged full browser suite
remains the native/API acceptance test.
