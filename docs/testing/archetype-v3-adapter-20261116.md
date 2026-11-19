# V3 pilot adapter — implementation, not run evidence

The v3 modules add the approved raised-budget pilot and compact trace format.
**No v3 pilot or matrix has been launched as part of this change.** Master AI,
rules, built-in decks, existing v2 adapters and source-pin files are unchanged.
The previous c2 pilot is not reused or reclassified as healthy.

The pilot entry remains restricted to a newly registered **36-game pilot**:
nine adjacent deck pairs, two seeds and both seats. A separate approved
**72-game health entry** now covers all 36 pairs, one new seed and both seats;
it is described below. No health plan is issued or run as part of this code
change. It is not the original 1,440-game/20-seed statistical matrix and cannot
close that gate or provide a meaningful seed-cluster interval with one seed.
AI strength remains unaccepted.

## What is implemented

- `archetype_plan_v3` reconstructs exact source-deck authority and freezes new
  run/cell identities, seeds, trace policy and **1,200 CPU / 1,500 wall seconds
  shared across play plus verification**. Runtime identity is frozen when the
  CLI issues a plan; unbound previews cannot execute. Two workers have one-core
  affinity and a 2-GiB address-space limit each. These are per-process controls,
  not cgroup reservations or a hostile-code sandbox.
- `archetype_trace_v3` writes a SHA256 record chain with per-action complete
  state/legal/RNG digests. Full before/after states appear every 64 actions,
  at changed choice/pregame boundaries, selected handler boundaries and final
  actions. Initial/final full state is retained. A **128-MiB candidate quota** (64 MiB in stopped trace1) refuses the
  complete next record before writing it; it never silently trims a trace.
- `archetype_game_v3` retains real checked actions and unchanged master
  decisions. Canonical bytes are hashed once per captured state. It still
  constructs complete state at every action and checks AI input mutation.
  It replays every action sequentially, compares complete-state digests and
  restarts through serialization at every action. Checkpoints do not skip
  replay. The first divergent action and mismatch categories are reported;
  hashes alone do not identify an expected differing state field.
- `archetype_worker_v3` uses private offline token/media caches and the existing
  cooperative network/descendant guard. Verification uses fresh engine state
  and selected real app-handler/SQLite comparisons at first/every100/last
  actions. Direct handler calls are **not HTTP or browser parity**. Atomic
  progress receipts identify the last fully flushed record and measured CPU
  categories. The interrupted operation remains unattributed if killed.
- `archetype_pilot_v3` waits for each owned child with `wait4`, retaining actual
  total CPU even on a signal exit. Verification receives the actual remaining
  CPU and wall allowances. A failed, missing or unbound verifier cannot retain
  a game winner: its entire verified outcome is compared with the game receipt.
  Progress hashes, byte boundaries and action counts are checked against the
  authenticated trace prefix before partial attribution is used.

All raw traces, snapshots, hands, reasoning, worker logs, databases and profiles
stay in the private output directory. CLI stdout contains aggregate status only.
Application settings and credentials are not forwarded to workers. There is no
network fetch, source-default app DB, developer media cache, or fallback AI.

## Campaign and restart policy

The declared campaign is **48 worker-hours**: 15 for a worst-case 36-cell pilot,
30 reserved for a conditional 72-cell health run, and three for overhead.
Both planned slots are charged throughout the controller lifetime, including
idle/setup/postprocessing time. Pilot launches reserve their remaining declared
schedule. The separately admitted health role reserves the next/in-flight
wall horizon under its own total charged cap, as described below. No 1,440-game execution command is
provided; its 1,500-second/cell ceiling alone is 600 worker-hours.

The current-user, same-host registry is
`~/.local/state/mtg/archetype-v3/`, with a private directory, an OS-held
`controller.lock`, permanent per-run consumption records, and the active
campaign ledger. The lock file is never removed to reset state. A new output
path cannot rerun the same ID, and a different ID carries forward prior v3
campaign charges rather than resetting the 48-hour allowance. This is
cooperative local enforcement; it is not distributed cross-host accounting.

No resume or automatic retry is supplied. If a controller is interrupted and
cannot prove all attempted child handles were reaped and accounted for, its
active record stays unproven and subsequent controllers refuse. Do not erase
or change the registry, HOME, or lock path to bypass that refusal. Operator
review is required; no automatic recovery/reset command is provided. A closed
controller record proves handle/accounting completion, not healthy games.

External environment installation or work outside the controller must also be
charged by the operator against the overhead reserve before approving the next
cohort. The remaining-budget ledger is authoritative for later admission; a
summary report is a point-in-time measurement before its own final publication.

## Operator commands after separate launch approval

Use a clean disposable Git checkout of the reviewed commit, without a
source-local `backend/mtg_lab.db`. Use Linux CPython **3.12.3** and a fresh
environment installed from the unchanged hash-locked application requirements
(28 application packages). Record that install separately: runtime version
inventory is not wheel-byte provenance. Preserve the checkout and outputs;
do not add outputs or private traces to Git.

For example, after the environment and the specific fresh run ID are approved:

```bash
cd /absolute/clean-checkout/backend
/absolute/fresh-venv/bin/python -B -m scripts.archetype_pilot_v3 plan \
  archetype-pilot-20261116-v3-trace2 /absolute/private/v3-plan.json

# Run only after reviewing that issued plan and receiving launch approval.
/absolute/fresh-venv/bin/python -B -m scripts.archetype_pilot_v3 run \
  /absolute/private/v3-plan.json /absolute/private/new-v3-output --execute-pilot
```

The plan file and output path are exclusive. The source revision must be the
exact clean commit and the runtime must match the issued plan. Source/runtime
drift, host sleep, cancellation, protocol failure, quota and resource limits
remain visible failures; no seed is silently dropped or replaced.

`PILOT-COMPLETE.json` means all scheduled cells were accounted for. Only
`usable: true` means every game finished with a genuine engine result and its
replay/selected comparisons passed. Timeout, action/turn limits, errors,
missing data or incomplete verification yield `usable: false` and **no
completed-game forecast**. Even a usable pilot accepts neither RC nor strength.
The process exits nonzero for an unusable pilot.

## Local checks and evidence scope

Tests use small authored schedules/phase receipts and bounded real engine
transitions. Native subprocess checks use owned stdlib children, not pilot
games. Registry tests use only private temporary directories, not the operator's
real registry. These tests do not constitute a fresh install, host pilot,
browser acceptance or complete RC acceptance.

```bash
cd backend
python -B -m pytest -q \
  tests/test_archetype_trace_v3.py tests/test_archetype_game_v3.py \
  tests/test_archetype_plan_v3.py tests/test_archetype_worker_v3.py \
  tests/test_archetype_pilot_v3.py tests/test_archetype_registry_v3.py \
  tests/test_archetype_health_v3.py tests/test_archetype_health_registry_v3.py \
  tests/test_archetype_parent_stop_v3.py \
  tests/test_archetype_matrix_plan.py tests/test_archetype_matrix_execution.py \
  tests/test_archetype_matrix_game.py tests/test_archetype_matrix_api_check.py \
  tests/test_archetype_matrix_pilot.py tests/test_archetype_matrix_worker.py \
  tests/test_interface_scope_compatibility.py \
  tests/test_interface_scope_current_delta.py \
  tests/test_interface_scope_phase1_repository_delta.py \
  tests/test_interface_scope_c14_assertion_delta.py \
  tests/test_interface_scope_76_mutations.py
```

Original implementation (`a77eddc0`, before the fidelity/quota revision) local
result on 2026-11-16: **375 passed, 0 failed/errors/skipped, 83.96 seconds**,
with one existing Pydantic `datetime.utcnow()` deprecation warning. This is
107 new v3 checks, 75 existing adapter checks and 193 source-compatibility
checks. It used the existing local application environment, not a fresh
hash-locked installation. The 12 v3 module/test source hashes matched before
and after the run and matched the branch files. The entire backend suite and
host/CI execution are not claimed by this scoped result.


## Card-order fidelity revision (not a new pilot result)

The stopped trace1 pilot and its root cause are documented in
[the diagnosis](archetype-v3-trace1-diagnosis-20261116.md). Its failed evidence
remains unchanged. The candidate adapter uses **trace wire schema 4** and a new
record-chain domain. Initial/final and checkpoint records retain ordered card-ID
lists; each action binds before/after order digests. Replay validates that order
against genuine transitions, restores it during each serde restart, and preserves
it in selected direct-handler snapshots. Canonical full-state hashes retain their
v2 value semantics; order is additional authenticated evidence. AI input-order
mutation also refuses. No logs, rules, AI or historical source pins are changed.

The CLI/module names and request envelope remain v3; the trace format is v4.
Old trace1 plans/records are not silently upgraded. After review, choose a fresh
ID such as `archetype-pilot-20261116-v3-trace2` and issue a new plan against the
exact merged candidate/runtime. Do not reuse the earlier example's trace1 ID,
reset the registry or resume its stopped schedule. No new plan or pilot has been
issued/launched by this revision.


Fidelity candidate checks on the existing local application environment:
**91 passed, 0 failed**, with four existing Pydantic `datetime.utcnow()` warnings,
across the game/trace/worker/plan v3 modules. This includes the real SBA
RED/GREEN, unchanged v2 transition digests and positive/negative direct-handler
order checks. It is not a fresh install, full backend or new pilot result;
broader composed verification is recorded separately when run.


The separate [trace2 quota proposal](archetype-trace2-quota-proposal-20261116.md)
raises the candidate trace ceiling to 128 MiB while retaining all checkpoint and
time/CPU policies. Its 36-cell trace-only ceiling is 4.5 GiB, with no valid
completed-game forecast from the stopped prefix. It preserves prior campaign
charges and the 30-hour conditional health reserve. Review/approval, a new source-
bound plan and an idle-host decision remain required; no new run is started.


Final local composed fidelity + quota candidate verification:
**396 passed, 0 failures/errors/skips, 93.71 seconds**, with five existing
Pydantic `datetime.utcnow()` warnings. This is 128 v3 checks, 75 unchanged v2
adapter checks and 193 interface-scope pin checks in one invocation. JUnit
contains 396 distinct cases. All 13 v3 module/test hashes matched before/after
and the branch bytes; engine/rules/AI/v2/pin files are unchanged. The runtime was
the existing local application environment, not a fresh hash-locked install.
Host/CI checks, a new issued plan and any new pilot remain separate.


## Separate all-pair health entry — implementation 2026-11-17

The limits below describe the original health run. The
[one pre-registered rerun](archetype-health-rerun-prereg-20261119.md) uses
2,400 shared CPU and 3,000 shared wall seconds for its exact run ID. Pilot
and other health plans retain the original values.

The maintainer approved code/tests for this separate health scope despite
trace2 being accounting-complete but **unusable** (35 resolved, one CPU timeout).
That result remains unchanged. **A failing health result is plausible and
acceptable to report** given the observed 1/36 timeout; it is not permission
to relax criteria or call a failure a pass. No plan issuance or launch is part
of this implementation, and private pilot outputs are neither reused nor read.

`archetype_health_v3` is a run-only CLI. It validates the exact existing health
plan: 72 cells, all 36 pairs of nine admitted original lists, seed 2026112101,
both seats, no sideboarding, no Burn/Mono Red substitution. It shares the
pilot scheduler and cell execution, while calling the separate
`archetype_health_worker_v3` role. The ordinary pilot CLI/worker still refuse
health cells; role/ID substitution, edited limits/seeds/roster, an unbound
runtime or stale source bindings refuse before execution. The health worker
binds both its own file and the common worker. No rules, AI, deck, v2 adapter
or source pin is changed.

Every-action exact replay/serde, selected first/every-100th/last direct-handler/
SQLite/card-order checks and limits stay unchanged: **1,200 shared CPU / 1,500
shared wall seconds per cell**, 2 GiB per worker, two one-core slots, 10,000
actions, 100 turns, 128 MiB trace, 64-action/decision checkpoints. No HTTP or
browser parity is inferred from the selected direct-handler comparisons. A
parent-detected outcome mismatch now sets the same stop event as a worker-
reported divergence; the added regression fails without that fail-fast line.

Health admission uses the **same** current-user host registry and permanent
run-ID records, with a new `archetype-health-20261116-v3-*` namespace. An exact
unused ID and fresh plan for the final clean commit/runtime still need operator
review. Previous pilot records remain readable; prior campaign charges carry
forward, and subsequent health IDs also carry prior **health-role** charges.
Neither a new output nor a new ID starts another 30-hour allocation. An unknown
child closure keeps the registry unproven and blocks both roles. Never reset
HOME, move the registry or remove a lock to bypass it.

The health role is bounded by **30 charged worker-hours total across its
attempts** and the remaining **48-hour campaign**; both slots are charged
through setup/idle/postprocessing as in v3. Before a cell launch, admission
reserves two slots through the maximum next/in-flight wall horizon, plus **60
worker-slot seconds of shutdown/postprocessing headroom**. It does not reserve
all 72 worst cases at once, which would consume 30 hours before any overhead.
If the remaining role/campaign budget cannot cover that next horizon, it stops
admission and reports an incomplete budget refusal, without retry or truncating
the declaration. The reserve is not an added per-cell allowance. Cooperative
clock checks stop/drain near the cap; actual charges are always retained,
including an overrun. If final report publication crosses either ceiling, the
closed ledger flags the overrun and the entry raises/nonzero rather than
returning success. No arbitrary-duration OS/I/O bound or cgroup guarantee is
claimed. External setup still consumes operator-accounted overhead.

After a separate plan/launch review only, the new run command is:

```bash
cd /absolute/clean-checkout/backend
/absolute/fresh-venv/bin/python -B -m scripts.archetype_health_v3 run \
  /absolute/private/reviewed-health-plan.json /absolute/private/new-health-output \
  --execute-health
```

This command is documented, **not executed here**. The health CLI does not
issue plans. It requires the fresh locked runtime, clean exact source, private
absent output, support admission and host headroom described above. An existing
pilot trace/receipt is not an input to the health role.

`HEALTH-COMPLETE.json` means ordered schedule accounting is complete, not that
health passed. `health_passed: true` additionally requires all 72 outcomes to
be resolved/draw with complete bound replay/parity/CPU evidence and **zero
resource-limited cells**. One limited cell is 1.389% of 72, not rounded to zero;
`max_resource_limit_cells: 0` remains decisive. An accounted timeout can produce
COMPLETE with `health_passed: false` and exit 1. Limits receive no winner/score;
engine deck-out/draw policy stays unchanged. Crash/sleep/protocol/divergence
failures stop admission and drain/reap; interrupted peers remain censored.

Accept a result only after checking the **actual terminal exit, final report
bindings and closed registry charges/overrun flags together**. The report is
published before registry closure, so it alone cannot certify final accounting.
Unknown child usage never becomes fabricated zero CPU. No resume or retries.
All forecast fields remain null even on health success;
`statistical_gate_complete` and `accepts_matrix_or_strength` remain false.
One seed supplies no seed-cluster confidence interval or strength percentage.
The unrun original statistical gate and overall RC acceptance remain open.

### Health-entry local verification

One explicit 20-module invocation of the command above passed **433 tests,
0 failures/errors/skips in 94.93 seconds**, with five existing Pydantic
`datetime.utcnow()` deprecation warnings. This is **165 v3 checks** (including
health and the standalone parent-stop regression), **75 unchanged v2 checks**
and **193 interface-scope pin checks**, not a sum of overlapping invocations.
All 433 JUnit identities are distinct; all 18 v3 source/test file hashes match
before/after and the branch bytes. The run used a disposable source archive
and existing local Python 3.12.3 environment, not a fresh hash-locked install.

The parent-stop regression separately failed on the base archive at the missing
stop assertion and passed with only the one-line fix. Health admission tests
were RED before its entry/registry existed; cooperative-cap and final-publication
failure cases are exercised with authored clocks/receipts. The 72-cell scheduler
tests use authored worker boundaries, not 72 real games. Bounded real engine,
serde/handler and owned child checks come from the scoped adapter tests.
No full backend suite, CI, new plan, health launch, real registry operation,
statistical acceptance or strength result is claimed. Host/CI verification is
still required before plan review and any separate launch approval.

## Health run terminal record — 2026-11-17

**Health FAILED by predeclared zero tolerance: 71/72 resolved, one CPU-limit
timeout, no replay divergence among the 71 verified games.** Accounting is
complete; `health_passed: false` and `usable: false`. No timeout is scored as
a loss or draw, and no policy is changed by this record.

| Operator-reported launch | Value, checked against authorized terminal metadata where available |
| --- | --- |
| Run ID | `archetype-health-20261116-v3-trace1` |
| Measured full source revision | `1a54be1f7fc71884336d790c55bb935a7037fbb0` |
| Issued plan **file-byte** SHA-256 | `601a8d68cf04c02ac4734bef034f9a58390dad1eafdd9da933c346e509859dc4` |
| Actual launch time | 2026-11-17 03:39:15 UTC; operator reports output directory creation at 03:39:16 UTC |
| Completion timestamp | 2026-11-17 06:46:40 UTC, operator-supplied final-report mtime; not a captured shell-exit timestamp |
| Runtime/install | Operator reports clean clone and same hash-locked venv; exact bound runtime digest is in the detailed result |

The grammar hard-codes `20261116` in the run ID; that token is **not** the
calendar launch date. The final report's canonical plan digest is
`c921d07f6e731c187ca5c0aa7992f2ad934ad4d238587766200b01327da11a35`, distinct from the plan-file hash.

The single limited game is **Drain Deck, seat 1 vs Ramp, seat 2** (ordinal 032):
**1,199.940 CPU / 1,202.771 wall seconds**, exit -24/SIGXCPU, at last recorded
turn **26 / postcombat main**, with **761** written actions and **25,597,276**
trace bytes. Its CPU progress receipt covers 752 actions; the nine later trace
actions do not extend that receipt's CPU attribution. All 71 resolved games
passed the bound per-action replay/serde and selected direct-handler/SQLite
checks: 36,404 actions/restarts and 470 selected boundaries. This is not HTTP,
browser or independent rules/AI correctness evidence.

The operator supplied the terminal summary fields `complete: true`,
`health_passed: false`, statuses `resolved: 71` / `timeout: 1`, and
`accepts_matrix_or_strength: false`. Numeric controller exit: **not captured**
(detached launch); it is not inferred from the CLI implementation. The operator
reports a closed registry with child handles reaped, neither health nor pilot
budget exceeded, and matching report hash
`e213787c3e81779eb288afa92536a5d2ed64a9b531e554c68b3ee5488598c22c`. The analysis did not read the registry.
Report and post-publication ledger figures are kept distinct in the
[detailed health result](archetype-v3-pilot-evidence-template-20261116.md#72-game-health-result--2026-11-17).

No rerun, resume, new plan, AI/rules change or limit increase occurred for this
read-only review. Forecasts remain null; health-only evidence does not close
the original statistical gate, establish strength or accept RC. See the
[timeout evidence and options](archetype-health-timeout-options-20261117.md)
before considering any separately approved experiment.
