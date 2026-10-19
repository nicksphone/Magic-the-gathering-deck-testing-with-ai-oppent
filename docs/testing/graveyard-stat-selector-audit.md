# Graveyard Stat Selector Audit

Tests-only immutable baseline: own source archive SHA256
`7f36cf395d3856d586667192215c6658accbd8f559ed72c1eba18750b9405943`.
This is not a claim about current parent or main source.

Final whole NEW module: **20 PASS / 28 strict FAIL, 0.83s, exit 1**.
Earlier 36-case run: 20 PASS / 16 FAIL, 0.70s, exit 1.
No skips, xfails, selection filters, SQL, or network during collection/execution.
Precollection guard denies sqlite3, sqlite3.dbapi2, _sqlite3 and audited
connections; both denial controls passed and subsequent violations were empty.

Full canonical Detritivore raw is copied byte-for-byte from Meitner's verified
variable-suspend intake (SHA `11cebb050b3a685a71810f5be1397cf732735706bf0ab8eb4284811b506de05a`).
Full Terravore raw was retrieved before tests from official Scryfall named API,
2026-10-07T02:24:07Z (SHA `0151be99d0d2751fb926252767daf850b407a7ecb2762f18138e7314536d5469`).
Neither Oracle body is shortened or modified. Existing full Island, Mutavault,
and Dryad Arbor rows provide Basic-supertype versus land-subtype discrimination.

Both seats: actual printed Detritivore stats fail in battlefield/hand/graveyard;
Terravore all-graveyard stats and public views survive snapshot restoration.
Explicit controlled-inventory fixtures test controller on battlefield versus
owner elsewhere. They do not claim a simulated control-changing spell.
Unknown-selector negatives and all unqualified owner/opponent/all graveyard
land counts pass. Every query preserves the complete serialized root, including
RNG/log/event state. Basic/nonbasic owner/opponent/all counts all fail.

## Proposed Product Scope (Not Implemented)

`backend/rules_engine/continuous.py` preimage SHA256:
`355e74fedc60c4368c65e22d1de4964784ac022f679eebd7a1ba153775e34303`.
Only `_graveyard_card_matches_selector` at line 1074 needs a proposed additive
anchored `basic|nonbasic` + singular/plural `land` branch before type/subtype
fallback. Require printed Land type, then inspect exact Basic supertype in the
printed type line (before the subtype separator). Dryad Arbor's Forest subtype
must not make it basic. Unknown suffixes must continue returning false.
Reuse `_stat_resource_count` line 732 without domain/ownership changes.
No named-card checks and no effective battlefield type conversion in graveyards.

No product edit is included or authorized by this report. Suspend X, costs,
schema, engine, AI, paid-action lifecycle, and broader selector grammar are not
qualified. No existing main/parent source or active SQLite root was accessed.
