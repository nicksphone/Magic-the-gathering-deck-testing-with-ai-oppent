# Current-source recovery, sideboard and interaction checks

These follow the [test-loop timer qualification](asgi-timer-qualification-20261108.md)
on the same source-only `4775d475` archive. Its 2,875 tracked backend/audit inputs
match before/after and remain byte-identical to the current checkout's backend /
audit tree. Product, fixture and test assertions are unchanged. The 10 ms test-loop
wakeup and its limitations remain explicit; this is ASGI/SQLite evidence.

## Completed-series restore and different-card swaps

The complete `test_human_bo3_terminal_restore.py` and
`test_human_bo3_native_swaps.py` modules pass **2 tests**, zero failures, errors or
skips, in 479.86 seconds. Each executes its existing natural three-game Python
BO3 with externally piloted human controllers. They reuse the existing fixed
seed/decks; they are scenario checks, not independent AI-strength samples.

| Scenario | Accepted action POSTs | Result | Cold reads |
| --- | --- | --- | --- |
| Completed-series restoration | 780 | Natural 2–1 series | After games 1 and 2, then the completed series |
| Different-card sideboards | 790 | Natural 2–1 series | After games 1 and 2, then the completed series |

The second scenario swaps one different card per seat after game one, preserves
each main-plus-sideboard inventory, and verifies rebuilt sixty-card stocks for
games two and three. Separate receipt readback confirms sixteen atomic rejection
records: six HTTP 400, six 409 and four 422 responses, each with equal before/after
memory, controller and SQLite snapshots. Completed series reject another game.
Both terminal cold snapshots and scores equal their saved completed roots.

The original per-scenario 1,190-second / 6,000-action limits and each read-only
worker's 60-second timeout stay intact. The combined runner/outer limits are
2,590/2,600 seconds, allowing the existing post-terminal cold reads. Only the
exact committed worker/interpreter/canonical cwd/environment/UUID arguments are
admitted. The generous child ceiling is separate from the unchanged test bounds.
The new runner and timer shim use fresh output/database namespaces; passed older
harness versions remain retained.

All six cold workers finish with matching pinned shim hashes and absent PIDs.
The supervisor exits normally after approximately 490 seconds, reaps its direct
child and verifies the process group is absent without leftover cleanup. Its new
`finally` path is separately exercised with three inert lifecycle controls: normal
exit, live termination and a Python exception. A control-only missing-`__file__`
setup error is reproduced and retained before correction; no application game is
spent on it. Forced termination of the supervisor itself still requires an
independent owned-group closure check.

Independent review rehashes all 2,875 source files, checks JUnit, runner/shim /
supervisor pins, child completions and closure, and accepts the bounded result
without remaining findings. It does not inspect raw private episode bodies.

## Additional complete ASGI modules

| Whole module | Passed | Exercised behavior |
| --- | --- | --- |
| `test_cleanup_repeat_http.py` | 2 | Canonical discard-trigger priority and repeat cleanup, both seats |
| `test_death_replacement_http.py` | 3 | Death/zone replacement and SQLite restoration |
| `test_opaque_selection_http.py` | 8 | Paid selection, wrong-actor rejection and ordered-bottom recovery, both seats |
| `test_browser_origin_http.py` | 33 | Rejection before body/dependency/SQL/action/sync entry; trusted/no-Origin start, preflight and recovery |

This separate four-module cohort passes **46 tests** in 74.22 seconds, with zero
failures/errors/skips. All children are denied. Recorded SQLite connection
targets stay in the fresh cohort bootstrap or pytest roots; 266 connections and
zero denied operations are recorded. All 2,875 source hashes match. Existing
Starlette/Pydantic deprecation warnings remain visible (2,232 warnings).

Independent review checks the tightened roots, source/runner pins, JUnit and
connection metadata, with no findings. The audit observes connection targets; it
is not a complete filesystem/SQL `ATTACH` fence. These results do not establish
TCP/TLS, real browser execution, native Forge, expert AI or overall RC readiness.

## Admission and job lifecycle

A separate fresh cohort passes **48 tests** in 7.62 seconds across six complete
modules, with zero failures, errors or skips:

| Whole module | Passed |
| --- | --- |
| `test_simulation_admission.py` | 12 |
| `test_simulation_job_quota.py` | 16 |
| `test_simulation_job_cache.py` | 2 |
| `test_simulation_shutdown.py` | 9 |
| `test_simulation_engine_shutdown.py` | 3 |
| `test_lifespan_native_cleanup_retention.py` | 6 |

These checks combine actual owned SQLite/ASGI admission, replay, conflict, quota
and cache operations with the existing parked-worker doubles, cancellation
threads and lifecycle AST controls. They are 48 tests, not natural games or a
production-throughput sample. Quota cases use the existing low test limit of two;
the default 10,000-job constant has a separate assertion.

All 79 recorded SQLite connection targets are within the new cohort's bootstrap
or pytest roots. Children remain forbidden, zero denied events are recorded,
and all 2,875 bound files match before/after. The source-only archive's additional
lease marker truthfully names its canonical owned root; no hosted-CI environment
is impersonated. Independent read-only review rehashes the source and checks
lease markers, runner pin, connection targets and JUnit, with no findings. The
two existing dependency deprecation warnings remain visible. The same timer and
connection-observation limitations above apply.

Declarations, original failures, controls, JUnit, separate readback verification
and closure receipts remain private under
`/home/nick/mtg-rc-evidence-20261108/http-current-4775/`. Raw hands, snapshots and
decision records are not committed or made public fixtures.
