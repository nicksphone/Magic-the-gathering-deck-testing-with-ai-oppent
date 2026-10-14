# Durable-Trigger HTTP Fixture Identity

This test-only correction was measured on immutable `f102874f`, not relabeled
as a current published-source qualification. Its three target preimages are
also byte-identical at published `45d4ef47`.

The original whole cohort comprises `test_next_turn_draw.py` (32 tests),
`test_permanent_keyword_grants.py` (16) and
`test_static_global_keyword_contracts.py` (54). Before repair, twelve HTTP
setups changed a Factory-born state ID after its private stock facts captured
that ID. Serialization correctly rejected the mismatch.

Three existing HTTP setup functions now call the existing trusted
`adopt_fixture_state` helper instead of changing the state ID. The helper
validates the state and preserves its genuine ID and stock facts while moving
the explicit HTTP controller/registry/persistence binding. No facts are cleared,
rewritten or recaptured. Later persistence calls remain unchanged.

Both runs used the same 102 original node identities and order, without filters,
skips, retries or additional cases:

- Baseline: 90 passed, 12 failed, zero errors/skips; 26.33s, 78 warnings.
- Candidate: 102 passed, zero failures/errors/skips; 29.38s, 90 warnings.

All 76 assertion ASTs and 27 other functions/classes are unchanged. Original
paid casts, durable draw/grant resolution, privacy, atomic rejection, cleanup
and SQLite restore assertions remain intact. Production, shared helpers,
canonical cards, Factory/default stock, RNG and AI policy are unchanged.

The existing 900s-work/15s-cleanup physical guard and native SQL admission bodies
were retained. Source/runtime/input pins matched before and after execution.
All 56 observed native SQL handles closed, both known PIDs were absent, and
external fuser checks were empty for 14 SQL/backup/lock files and owner directories;
jobs, threads, owned descriptors and journals were quiet.

This qualifies only the declared three-module fixture correction using
in-process HTTP clients. It does not certify whole CI, all trigger mechanics,
browsers/TLS, AI strength, or a completed benchmark. The failed baseline is
retained separately.
