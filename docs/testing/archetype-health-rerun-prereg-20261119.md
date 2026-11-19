# One all-pair health rerun — pre-registration, 2026-11-19

The first health run accounted for all 72 cells. It failed the zero-tolerance
gate after Drain Deck in seat 1 versus Ramp in seat 2 reached the shared
1,200-CPU-second limit on turn 26 after 761 accepted actions. All 71 completed
cells passed replay and selected handler/SQLite parity. The first result stays
failed. See the [health result](archetype-v3-pilot-evidence-template-20261116.md#72-game-health-result--2026-11-17).

The one rerun uses `archetype-health-20261116-v3-rerun1`. The date is part of
the existing plan and registry ID grammar. The exact ID selects the increased
limits and the registry consumes it once. Use the same host and operator account
so prior charges and the permanent ID record apply. Use a fresh plan and output
directory. Record the outcome either way. This pre-registration allows one
attempt, with no further limit raises or replacement attempts under this decision.

| Control | Rerun |
| --- | --- |
| Shared game and verification CPU | 2,400 seconds per cell, raised from 1,200 |
| Shared game and verification elapsed time | 3,000 seconds per cell, raised from 1,500 |
| Roster and seed | Same nine admitted decks, all 36 unordered pairs, both seat assignments, seed `2026112101`, 72 cells in the same order |
| Other controls | Same master AI, rules, two one-core slots, 2 GiB per worker, 10,000 actions, 100 turns, 128 MiB trace and checkpoint policy |
| Verification | Every-action replay and serde checks, and the same selected direct-handler/SQLite parity checks |

Beyond the new run and source/runtime identities, the two time limits are the
only plan policy changes. Pilot plans and other health IDs use 1,200 CPU and
1,500 wall seconds. Schema, roster, trace fields and the source and runtime
verification checks stay intact. The new plan binds the updated tracked source
and the actual runtime environment at issuance. Keep the application hash lock.

Success requires 72/72 genuine completed outcomes under the existing gate,
including a genuine engine draw if one occurs, with every replay and selected
parity check matching and complete CPU and child-closure evidence. Zero tolerance
for resource limits stays in force. Any timeout, other limit, error, divergence,
incomplete schedule or missing evidence is a failed health result. Record the
terminal report, exit, registry closure and charge, and keep the old result.
Publish aggregates. A pass would establish completion and verification for this
exact cohort at these limits. It makes no claim about AI strength, quality of
play, statistical matrix acceptance, or overall release readiness.

## Admission arithmetic

The last closed registry record reported 85,510.88 health worker-seconds and
133,000.63 campaign worker-seconds remaining. At admission, use the actual
registry balances after charging setup and take the smaller. The controller
checks two slots through the longest next or in-flight wall horizon and adds
60 worker-seconds for shutdown. A 3,000-second horizon therefore needs
`2 × 3,000 + 60 = 6,060` worker-seconds. The reported health balance clears
that threshold by 79,450.88 worker-seconds and is the binding balance. The
prior full run charged 22,489.12 worker-seconds, which supplies a planning
reference for the rerun.

The controller rechecks the balance on every refill and charges both slots
throughout. A worst-case 72 cells at the new wall limit cost 216,000 worker-
seconds before extra overhead. Starting fits the reported balance. Completion
within the balance is contingent on actual durations. If admission later stops
the schedule, record that as incomplete and failed, with all charges carried
forward. Do not borrow from the campaign balance or reset the registry.

## Host issuance and execution

Use the final merged revision in a clean disposable checkout with no source-
local `backend/mtg_lab.db`. Use Linux CPython 3.12.3 and a fresh venv installed
with `python -m pip install --require-hashes -r requirements-py312-linux.lock`
from `backend/`. Use the same operator account and its existing registry at
`~/.local/state/mtg/archetype-v3`. Check that the previous record is closed, all
children are reaped, the ID is unused and the host is idle with at least three
available CPUs and 5 GiB memory headroom. Budget disk space for up to 9 GiB of
trace plus logs, databases and other run artifacts. Keep the plan and output
outside the checkout under a private, existing parent, with both paths unused.

```sh
cd /absolute/clean-checkout/backend
/absolute/fresh-venv/bin/python -B -m scripts.archetype_pilot_v3 plan \
  archetype-health-20261116-v3-rerun1 /absolute/private/health-rerun1-plan.json --kind health
sha256sum /absolute/private/health-rerun1-plan.json
```

Review the issued plan and record its SHA256, revision and runtime identity
before launching. The operator runs this command once and records its exit.

```sh
/absolute/fresh-venv/bin/python -B -m scripts.archetype_health_v3 run \
  /absolute/private/health-rerun1-plan.json /absolute/private/health-rerun1-out --execute-health
```

Use the [operator result checklist](archetype-v3-pilot-evidence-template-20261116.md#reading-a-future-health-result--operator-checklist-2026-11-17)
to record the report and exit together. No plan was issued and no cohort was
launched in preparing this change.
