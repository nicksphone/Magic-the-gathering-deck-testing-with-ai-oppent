# Counter fixture and cold-restore acceptance

The isolated `50f9e58bade68514572012dc5cd3e366482ec031` source plus these test-only fixture corrections passed four entire modules: **153 tests, 109 warnings, 72.97 seconds**, no failures, errors or skips. This is a component/source-specific result, not a whole `cf1c` CI or release certificate.

| Whole module | Ordinary tests |
| --- | ---: |
| `test_paid_counter_family_audit.py` | 108 |
| `test_activation_modifiers.py` | 25 |
| `test_activated_ability_timing.py` | 14 |
| `test_counter_fixture_births.py` | 6 |

Only test setup changes: the activation-modifier HTTP fixture supplies its real controller game ID to `MatchFactory` **before** birth-time stock capture; repurposed primitive timing boards start with the existing finite `controlled_basic_game` helper, unknown sideboard facts from birth, rather than mutating captured Factory stock. The helper is already public and is not duplicated. All 116 original assertions in the two affected modules retain their ordered ASTs; all other test-function bodies are unchanged. Invalid game identity and corrupted captured stock remain rejected. Canonical card rows, game logic, validators and API implementations are unchanged.

The six new regressions cover both seats' identity-safe Factory birth and trusted primitive cold-snapshot roundtrips, plus invalid identity and corrupted Factory-stock rejection. Their earlier isolated PURE proof is separate from this full mixed acceptance. No primitive board is presented as a certified captured deck.

The full run completed 40 actual child invocations: 38 snapshot serializer children and two unchanged original cold-HTTP workers, all return code zero and reaped. Both cold workers restored the actual owned file database, queried both seats, and checked root/controller/SQL equality and privacy under the pre-import fence. Child SQL protection is logical `query_only` plus a mutation-denying authorizer, **not** an OS-read-only file claim.

The private harness admits the exact stdlib `iterdump` read, `PRAGMA table_info(table)`: its argument is a table name, not a setter. Other argument-bearing pragmas, writes, DDL, ATTACH and extension loading remain denied. A separate nine-denial native protocol preflight also checked the entire one-row schema dump; it did not execute the cold game worker. Prospective bounded diagnostic output retention changes are private harness-only and are not shipped in this patch.

The source's 3206 existing file-set and bytes, interpreter/runtime pins and harness bindings remained equal. SQL ownership, threads, jobs, descriptors and children closed; external fuser checks over the recorded 16 existing paths were empty and all listed PIDs absent, with no journals/WAL/SHM. The authoritative release was **2026-10-13T22:22:03.013016Z**. Private databases, expected snapshots and raw child outputs remain in private storage, not this public package.

Historical stages remain distinct: the original `7435` baseline had 138 passes/9 failures, an administrative activation stop ran zero tests, and the first corrected fixture run had 151 passes/2 cold-harness failures. None is relabeled as green. The initial final-run metadata verifier expected 38 children and stopped; correcting that metadata expectation to the actual 40 required no game/test rerun. Final acceptance is only the independently counted 153-test run above. Broader AI/full-CI/full-release requirements remain open.
