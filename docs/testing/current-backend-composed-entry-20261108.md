# Current Backend Composed Entry

Status: **174 passed, one HTTP fixture setup error; incomplete**. This is a
source-bound full-discovery attempt on `542c5054`, not a passing full backend,
hosted result, completed HTTP case or RC gate. Application and test bodies are
unchanged. Earlier 72/81-case entry attempts and separate component results are
not added to this run's count.

## Scope And Result

Standard backend pytest discovery runs without module or keyword filters and
stops at the first failure. It reuses the Python environment, disposable SQL,
exact original CLI admission and the existing test-only 10ms ASGI timer.

Eight complete modules pass before the stop:

| Module | Ordinary passes |
| --- | ---: |
| `audit/exile-counter-body/body-goldens/test_full_body_cda.py` | 4 |
| `tests/regression_agent/test_interactions.py` | 30 |
| `tests/regression_agent_wave2/test_casting_contracts.py` | 34 |
| `tests/regression_agent_wave2/test_restart_and_additional.py` | 6 |
| `tests/release_agent/test_restore.py` | 11 |
| `tests/release_agent/test_retention.py` | 27 |
| `tests/release_agent/test_safety.py` | 7 |
| `tests/test_ability_cost_discounts.py` | 55 |

The next case,
`test_http_scoped_cost_payment_is_atomic_and_restored[Tamiyo's Logbook-1]`,
errors during `TestClient` startup in `DatabaseOwner.acquire`. The guard denies
the owner-lock open before contents are accessed. No owner-lock file is created
and the declared bootstrap directory remains empty. One ASGI loop starts and
records three timer ticks; the HTTP fixture does not finish startup and no
passing HTTP/action/recovery result follows from it. The error remains recorded,
with exit 1, zero test failures/skips and 48 warnings.

JUnit records 55.675 seconds, the worker 56.859 seconds and the supervisor
60.057 seconds. These are different timing boundaries, not latency comparisons.
The worker makes eight observed AI choices within the existing tests. No separate
natural-game or matrix benchmark is scheduled; test-contained gameplay is not
relabelled as a strength benchmark.

## Native Storage And Child Evidence

The parent returns 165 native SQLite connections across 49 owned file targets,
with matching audited handles and authorized returns, zero constructor failures
and zero authorizer rejections. Seven original CLI invocations execute: four
restore commands and three ordered pruning commands. Their independent clean
receipts verify five further native SQL returns; the combined executions touch
51 distinct owned SQL targets. These counts do not represent additional tests.

Every child must match its original test frame, actual pytest fixture, executable,
arguments, count/order and inherited guarded bootstrap. User-site loading is
disabled before startup. Clean source, guard, native-return and child-admission
receipts are required independently of expected nonzero CLI exits. All seven
receipts satisfy those checks. The original inspected `FailingConnection` is
admitted once before construction with its exact native base, execute code,
closure, test frame and owned database; other custom factories remain denied.

The main guard retains the reviewed native SQL/factory policy. The restore-policy
module is byte-identical to its reviewed original and supplies only command
admission; a second conflicting audit hook is not installed. Fifteen helper ASTs
and the renamed pruning admission remain unchanged. Protected bodies and foreign
database opens remain denied. Content writes are fenced to owned execution,
bootstrap/child receipts and declared source-cache SVG generation. UNIX socket
construction supports the in-process test loop; network operations remain
denied. This is trusted-test instrumentation, not a general filesystem sandbox.

## Controls, Closure And Limits

Prelaunch controls exercise five native SQL positives, five denied SQL primitives,
31 expected audit denials, seven fabricated clean-receipt positives, fifteen
child-receipt rejection cases and five parent-admission rejection cases. They
launch no application tests or CLI children. Newly created synthetic protected
names are denied before body reads; no real protected file is examined.

Review found that the initial output cap omitted nested artifacts and could miss
a worker finishing between polls. Recursive metadata accounting and unconditional
post-cleanup accounting now include the close receipt itself. The first terminal
control reconstructed an exit predicate and falsely passed; its corrected version
executes the actual finally block and trailing exit expression, observes RED exit0
and then GREEN exit1 for an over-cap completed worker. All earlier observations
are retained. A final pinned metadata-only control confirms the same executed
supervisor code; application tests are not repeated for that check.

The declared CPU720s/inner900s/outer930s/16GiB/128MiB bounds and retries0 remain.
Polling permits transient output overshoot; final accounting rejects an exceeded
bound. This execution ends below the cap at 9,948,293 bytes including its close
receipt, with no outer stop. Its direct worker is reaped and the owned process
group is explicitly absent. The inherited ordered handle/return comparison can
conservatively reject interleaved concurrent constructors; it was not relaxed,
and all 165 observed parent pairs match here.

All 5,137 frozen public SHA-256/Git blobs and the complete current 2,697-file
backend verify. Source, guard and harness pins remain unchanged. Private
declarations, child metadata, JUnit, controls and closure evidence are retained
in `/home/nick/mtg-rc-evidence-20261108/current-backend-composed/` with
`FINAL-VERIFICATION.json`. Database bodies, lock bodies and private snapshots are
not included in the public change.

The separately declared [synthetic-owner follow-up](current-backend-synthetic-owner-20261108.md)
later advances through eight HTTP cases using one new empty exact-path fixture.
This earlier stopped execution remains unchanged. The protocol preserves refusal
of real operator locks, protected models and user databases. The
[Master correction](master-winning-death-block-20261108.md), historical
matrix partials/flags, thirteen-style/expert-AI requirements, clean installation,
build inputs, hosted CI, browser and native-runtime gates retain their scopes.

A fresh GitHub read at 19:59 UTC still reports zero forks and a November 7 last
push. [Roadmap issue 2](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/issues/2)
remains open; its broader rules, replay, metadata and AI acceptance is unchanged.
This local attempt does not publish the branch or transfer PR51's hosted result.
