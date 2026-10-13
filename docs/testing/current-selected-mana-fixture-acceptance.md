# Selected-mana fixture acceptance

Immutable `e1dda1bb0fc3c2d10a22f0385e079003e636f838` plus two test-helper corrections and nine new strict controls passed **55 tests, 79 warnings, 35.17 seconds**, with no failures, errors or skips. This is component acceptance, not whole-head CI, complete AI-strength or release qualification.

| Whole module | Ordinary tests |
| --- | ---: |
| `test_selected_mana_http.py` | 12 |
| `test_spell_type_caller_projection.py` | 34 |
| `test_selected_fixture_contracts.py` | 9 |

The HTTP fixture previously copied a genuine environment state but overwrote its ID after Factory stock capture. It now uses the existing explicit `adopt_fixture_state` helper: preserve the environment's identity and facts, validate before mutation, rekey the registered controller and persisted row, and retain its configuration. No automatic repair, recapture, facts clearing, engine/API or validator change is introduced.

The projection runs the entire original browser-fixture function. Its publication callback now accepts the actual `capture_original_stock` keyword and asserts it is precisely `False`. That branch explicitly repurposes a basic Island into the complete Tamiyo fixture. Its test-only constructor namespace uses the already-published finite `controlled_basic_game` helper to create this trusted primitive with unknown stock from birth; it does not clear captured Factory facts afterward. Genuine Factory cases and their corruption rejection remain intact. The original browser-function body, canonical fixture rows and all unrelated functions are unchanged.

All 54 original ordered assertion ASTs are preserved; one strict-False assertion is added. NEW9 controls retain their original bytes. The existing c45 constructor and adoption helpers are dependencies, not duplicated files in this increment. NEW9 use actual Factory/serde with inert controller/publication projections; they alone are not an HTTP/Repository certificate.

Actual whole-module acceptance includes the original 12 HTTP payment/hybrid cases, invalid-request root/SQL/privacy assertions and in-process persistence/restoration. No child process ran in this cohort, so it is not a new native cold-process certificate. All 3212 source files and their bytes, interpreter/runtime pins and guard bindings remained equal during execution. Resources closed with no unexpected I/O, owner descriptor, live threads or jobs; external checks covered the recorded 14 existing paths, with empty fuser output, absent PIDs and no journals/WAL/SHM. The authoritative SQL release was **2026-10-13T23:08:44.184588Z**.

History is immutable and separate: original55 baseline **31P/24F**; first PURE candidate **40P/3F** exposed the captured-stock issue after correcting the keyword; corrected PURE candidate **43P**; final mixed acceptance **55P**. A later relative-path tail command failed administratively after the successful parent verification; it was not a test rerun or invalidation. Private SQLite files, raw root/controller snapshots and owned logs remain private and are not included in public postimages.
