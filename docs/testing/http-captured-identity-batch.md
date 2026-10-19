# Captured HTTP Fixture Identity Batch

Source epoch: immutable `c637ca489aeaa2d8a1b45af5027d1f6833c492ec` plus eight test-only postimages. No production, shared-helper, canonical-data, RNG, or validation changes.

The unchanged eight-module baseline collected 489 unique ordinary cases: global-flash 40, queued-sequence 8, Cathar 6, discard-history 92, linked-discard 80, nonmana-kicker 75, wheel-draw 114, land-type-layers 74. It completed 429 passed / 60 failed / 0 errors or skips, 150 warnings, 145.34 seconds. Its failed ledger and closed source/runtime were preserved separately.

Six explicit HTTP fixtures now adopt their genuine captured state IDs through the existing helper, rather than overwriting them after birth. Cathar updates its local endpoint ID after adoption. The original queued worker passes its existing `game_id` parameter before Factory capture; all worker assertions, argv, phases, and 60-second timeouts remain unchanged.

Global-flash's 16 failures were not identity failures: the expected pure engine copy omitted the accepted-action recorder that HTTP calls. Two expected-oracle functions now invoke that same existing recorder on the copy, keeping every full snapshot comparison. Three added assertions require false coverage for out-of-birth-stock sources and unchanged original state. No coverage certification or permission change is claimed.

The fresh, unfiltered same whole eight modules completed **489 passed / 0 failures, errors, or skips**, 186 warnings, **212.60 seconds** (215.418 seconds outer). All 446 original assertions in touched files remain AST-identical and ordered; every approved function inverse reconstructs the original file byte-for-byte. All 3,232 other Git files are byte-equal. No original test was skipped, filtered, or weakened.

Source/HF input maps and fixed harness pins stayed equal. All 16 actual queued worker children exited 0 and were reaped; 256 observed parent native SQLite handles closed. No new threads, jobs, workers, owned FDs, journals, or unexpected events remained. External verification found 19 known PIDs absent and 76 existing owned DB/backup/lock files quiet. Fixture SQL release: 2026-10-14 09:57:33.636214 UTC.

The physical boundary was private network/IPC with readonly host resources and owned writable scratch. Parent native SQL auditing and the original queued-worker audit are distinct; all-child alias prevention is not claimed. This is this fixture batch's acceptance, not whole-backend CI, all 140 identity rows, natural-game strength, or competitive coverage.
