# Current Backend Synthetic Owner Entry

Status: **230 passed, one guarded replay CLI failure; incomplete**. Eight HTTP
cases pass on frozen `783c80ba`, whose complete backend equals production/test
revision `542c5054`. This separately declared attempt follows the
[174-pass entry](current-backend-composed-entry-20261108.md); overlapping results
are not added. No application, test assertion, selection or gameplay limit changes.

## Scope And Result

Standard backend discovery uses `pytest -q --maxfail=1 -p no:cacheprovider`, with
no module or keyword selection. The reused environment, owned native SQL, seven
exact original restore/prune children, inspected fault factory and test-only
10ms ASGI timer retain their declared scopes. One new disposable empty owner-lock
fixture permits the existing HTTP lifespan to acquire its bootstrap database.

Twelve complete modules pass:

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
| `tests/test_ability_cost_discounts_integration.py` | 10 |
| `tests/test_ability_model.py` | 4 |
| `tests/test_ability_model_nissa_fixture_fidelity.py` | 4 |
| `tests/test_ability_suppression.py` | 18 |

The first twenty cases of `test_action_replay.py` also pass. Its next case,
`test_offline_cli_status_privacy_and_input_preservation[valid-0]`, fails when the
guard denies the original `scripts/reconstruct_action_replay.py` command as
`unknown-child-script`, before launching it. Replay CLI admission is outside the
existing seven-command protocol. This is a qualification boundary, not an
observed product replay defect or a whole passing replay module. The terminal
run retains exit 1, one failure, zero errors/skips and 126 warnings.

Six HTTP cases cover cost-payment rejection without state mutation, successful
payment and restored committed snapshots, for Tamiyo's Logbook, Deepwood Denizen
and Battlefield Butcher in both seats. Two further HTTP cases restore ability
suppression and reject mana/ability writes in both seats. These use native SQLite
and restore controllers within the same process; they do not establish a cold
worker restart, browser, TCP/TLS or complete HTTP acceptance. Eight loops record
363 timer ticks. The unchanged tests make eight observed AI choices; no separate
natural-game or matrix benchmark is scheduled.

## Synthetic Fixture And Guard Controls

Before guarded startup, the harness exclusively creates one new empty mode0600,
single-link file at the fresh `bootstrap/state.sqlite3.capacity-owner.lock`.
Its body is never read, hashed or copied. Only metadata is recorded and checked.
Admission requires the exact parent path, unchanged device/inode/mode/owner/size/
link identity, native open flags, pinned `DatabaseOwner.acquire` code/frame and
exact bootstrap owner/engine/database/PID/descriptor bindings. Eight native
acquisitions use that same fixture; its metadata remains unchanged. All real
operator locks, protected models and foreign databases remain excluded.

The native-method control with an inert engine is denied by the original guard
RED and admitted by the new protocol GREEN, with its descriptor closed. An
initial isolated-method compile omitted original import context and correctly
failed the code-signature check. Reinstating the original future and standard
library import context yields the identical native code signature; the policy
is not relaxed, and initial failed control records remain.

Fifteen denial controls cover raw reads, wrong frame/flags/path/child role,
owner/engine/query/PID bindings, changed code and hardlink/size/mode/inode changes.
After metadata restoration the native positive passes again. Existing controls
retain 31 audit denials, five SQL primitive denials, five native SQL positives,
seven fabricated child-receipt positives, fifteen child-receipt negatives and
five parent-admission negatives. Owner controls import no application, open no
SQL connection and launch no AI or CLI children. These are trusted-test controls,
not a general filesystem sandbox.

## Storage, Closure And Limits

The parent has 221 matching native SQL handles and authorized returns across
58 owned file targets, with zero constructor failures or authorizer rejections.
All seven original CLI children independently verify clean receipts, including
expected nonzero exits: four restore and three prune commands, with five further
native SQL returns and sixty distinct targets across parent and children. The
original inspected fault factory is admitted exactly once. Nineteen existing
guard helper ASTs and the restore/receipt policy bytes remain unchanged.

All 5,139 frozen public source SHA-256/Git blobs and 2,697 current backend files
verify. Source and harness pins remain unchanged. The declared CPU 720s,
inner 900s/outer 930s, AS 16GiB, retries 0 and output 128MiB bounds hold. Final generated
output is 22,700,737 bytes including the close receipt; the direct worker is
reaped, its owned process group is absent and no outer stop occurs. JUnit takes
70.461s, the worker 71.678s and supervisor 76.070s; these different boundaries are
not performance comparisons. Output polling can overshoot transiently, with
final accounting rejecting an exceeded cap. Ordered SQL handle/return comparison
can conservatively reject concurrent interleaving; the observed 221 pairs match.

Private metadata/source/receipt/JUnit verification is retained under
`/home/nick/mtg-rc-evidence-20261108/current-backend-synthetic-owner/` in
`FINAL-VERIFICATION.json`. No database, lock body, private trace, hand or snapshot
is included in the public change. Static prelaunch review independently checks
5,138 source files (excluding the frontend environment template), all current
backend files and the protocol within its stated scope.

Final independent read-only review finds no actionable issue in the terminal
evidence or documentation. It verifies the receipt/harness/control pins, JUnit,
native SQL/children, fixture metadata, closure and source comparisons without
running application tests or reading protected bodies or private traces.

The next replay CLI protocol needs its own exact source/frame/argument/path/
count admission and independent clean-child receipts. This terminal execution
must not be restarted or relabelled green. The historical fifteen block flags,
matrix partials, thirteen-style/expert-AI scope, clean installation, missing build
inputs, hosted CI, browser, native-runtime and all original RC gates remain open.

A GitHub read at 20:39:40 UTC still reports zero forks and the November 7 last push;
all seventeen returned open PR heads remain local ancestors.
[Roadmap issue 2](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/issues/2)
retains the broader rules/replay/data/AI scope. This local evidence does not
publish the branch or transfer PR51's hosted result to the new candidate.
