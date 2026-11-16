# V3 pilot adapter — implementation, not run evidence

The v3 modules add the approved raised-budget pilot and compact trace format.
**No v3 pilot or matrix has been launched as part of this change.** Master AI,
rules, built-in decks, existing v2 adapters and source-pin files are unchanged.
The previous c2 pilot is not reused or reclassified as healthy.

The only executable cohort here is a newly registered **36-game pilot**:
nine adjacent deck pairs, two fresh seeds, both seats. A **72-game health plan**
can be generated separately for all 36 pairs, one new seed and both seats, but
neither this worker nor the pilot command executes that health plan. Its
eventual launch needs separate approval and a health-run entry point. It is
not the original 1,440-game/20-seed statistical matrix and cannot close that
acceptance gate or provide a meaningful seed-cluster interval with one seed.
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
  actions. Initial/final full state is retained. A **64-MiB quota** refuses the
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
idle/setup/postprocessing time. New launches must reserve the remaining
declared schedule, not just the next cell. No 1,440-game execution command is
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
  archetype-pilot-20261116-v3-trace1 /absolute/private/v3-plan.json

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
  tests/test_archetype_matrix_plan.py tests/test_archetype_matrix_execution.py \
  tests/test_archetype_matrix_game.py tests/test_archetype_matrix_api_check.py \
  tests/test_archetype_matrix_pilot.py tests/test_archetype_matrix_worker.py \
  tests/test_interface_scope_compatibility.py \
  tests/test_interface_scope_current_delta.py \
  tests/test_interface_scope_phase1_repository_delta.py \
  tests/test_interface_scope_c14_assertion_delta.py \
  tests/test_interface_scope_76_mutations.py
```

Local result on 2026-11-16: **375 passed, 0 failed/errors/skipped, 83.96 seconds**,
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
