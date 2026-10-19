# Phase 1 Stored-Deck Corpus Acceptance

## Qualified Component

Over an isolated archive of `92a59e1135fa53e1c4363734a61211bfb88e4a81`
plus the minimal correction below, one fresh, bounded three-whole-module run
passes **61 ordinary cases**, with zero failures, errors
or skips, in 6.53 pytest seconds. This is a data/CLI component qualification,
not a gameplay, rules-support or AI-strength certificate.

The declaration retains the new stored-deck module (3 cases), the unchanged
`test_knowledge_gap_report_fields.py` (44), and unchanged
`test_knowledge_gap_report_face_cache.py` (14). No cases were deselected.

## Genuine Stored Corpus

The tests use the existing complete official 155-card RAW/rulings fixtures and
real `Repository`, `KnowledgeIngestor` and CLI implementations. No canonical
rows or repositories are stubbed. Physical HTTP is replaced by `MockTransport`;
there is no live Scryfall intake or live/user database access.

The real default corpus resolves to 149 canonical records. An owned persisted
deck declares 60 mainboard and 15 sideboard cards, introducing verified Farewell
(main) and Supreme Verdict (side), both outside that default set. The actual
coverage CLI first returns 1 for missing knowledge. The real sync CLI ingests
the two full official records and their verified rulings; coverage then returns
0 for 151 distinct requested names. Repeating sync makes zero API requests and
preserves all stored deck/cache/knowledge rows, IDs and timestamps.

The same flow passes with casefold-duplicate stored names. A separate real,
empty-repository unit control checks first-supplied spelling, deterministic
casefold ordering and distinct printed face names. It asserts missing coverage,
not fabricated canonical knowledge or gameplay support.

## Minimal Correction

The pristine two-case run had one pass and one strict failure: coverage reported
153 instead of 151 requested names. `knowledge_report` previously deduplicated
raw strings. The only production change retains the first spelling with
`dict.setdefault(name.casefold(), name)` and then sorts those values using the
existing casefold key. Other function bodies, canonical/rulings/cache/image
logic and CLI exit predicates remain byte-identical. Distinct face names are
not collapsed by card or Oracle identity. Both original new-test cases are
unchanged; only the additional identity control was appended.

## Execution Bounds

Both runs used a 300-second outer deadline plus 15-second kill grace. The final
run used two owned local SQLite files and two explicitly declared actual
in-memory test callers. All 8 connection handles were closed, the two existing
SQL files had `fuser` exit 1 with empty output, and all three known owned PIDs
were absent before lease release at `2026-10-15T00:52:12.215508Z`.

The runner audits native connection targets and trusted fixed caller identities;
it is **not** a general SQL-statement authorizer, ATTACH/DETACH firewall or
hostile-SQL sandbox. The pinned cohort uses known schema/CRUD/report operations.
No foreign connection or network operation was observed. Default database,
startup, provider, subprocess, native checked-action and chooser paths were not
used. Source (1,977 files) and runtime HF (3,678 entries) were equal before/end;
there were no unexpected IO denials or measurement charges.

## Evidence Boundary

The failed baseline remains immutable under
`diagnostics/ci/phase1-stored2-baseline-actual-20261015-iHcFwLi3/`, full archive SHA
`f7e13e8bc9d3b7cf9df5ae8a7663d39864304df44c33ee3a2155235b5f5bf2e9`.
The gate does not establish completeness of arbitrary stored user decks, local
image availability, engine support, current global CI, or measured AI strength.
No old benchmark NULL, lifetime counter, root allocation or learned artifact was
changed or promoted.
