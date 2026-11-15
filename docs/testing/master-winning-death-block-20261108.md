# Master Winning Death-Block Correction

Status: bounded tactical correction verified; full backend and RC qualification
remain open. This does not adjudicate or change the fifteen historical flags in
the [terminal block triage](master-block-flag-triage-20261108.md).

## Defect And Change

The existing full-canonical Strong regression has a defender-controlled Zulaport
Cutthroat, an attacking Elvish Warmaster supported by Elvish Archdruid, and the
opponent at one life. Checked combat kills the blocker and its native death
trigger wins for the defender. This is a controlled old-board position, not a
paid-entry sequence, reconstructed historical game or arbitrary-card certificate.

Extending that same fixture to Master and Master Plus exposes four failures:
both modes retain the blocker in both seats. The Strong reference wins in both.
The cause is the stats-only pre-projection chump rejection in
`AIAgent._search_block_assignments`: it discards the allocation before native
death/other combat triggers can establish a terminal outcome.

The correction removes that early rejection and its unused keyword local.
Within the existing planning budget, the native projection can now resolve these
candidates; winning outcomes can reach the existing terminal ranking. The later nonterminal
material filter, exact-response completeness, unknown-result handling, scoring
weights, shortlist sizes and planning limits are unchanged. No card-name or
trigger-text exception is added. More candidate projections may now be attempted;
this is not a latency improvement claim.

The existing test helper gains an optional difficulty argument defaulting to
Strong. The winning and hidden-draw regressions now include both Master modes.
New both-seat controls retain nonlethal material when the death trigger does not
win, or when the actual printed ability is suppressed. All 21 original assertion
ASTs remain unchanged; an exact inverse of the declared helper/parameter/control
edits reproduces the original test-module AST. Its fourteen original cases remain
covered within the final thirty-case module.

## Separate Executions

All executions use immutable public source packets based on `49a7e061`, the reused
Python environment, user-site/bytecode/plugin autoload disabled, and a pre-import
pure runtime/content-write fence. No natural games, original matrix restart or
metric changes occur.

| Execution | Recorded result |
| --- | --- |
| RED: six winning-block cases on original production source | Four native assertion failures in Master/Master Plus; two Strong passes |
| GREEN: same six cases after the correction | Six passes; both native winning-outcome assertions pass in all modes/seats |
| Seventeen complete combat/quality modules on final source | 321 ordinary passes and six passed subtests; 120 failures in the audit module because its artifact-output environment variable was missing |
| Corrected complete `test_public_block_leaf_audit.py` on the same frozen source | 120 passes; the exact previously failed case identities, with an owned evidence output directory |
| Full backend discovery with first-failure stop | 72 passes and one SQLite guard denial; two dependency deprecation warnings |

The first combined execution remains failed. The corrected audit-module execution
does not create a single green seventeen-module run or a passing full suite.
Other passed modules and choices were not repeated for counts. Their coverage
includes nonlethal retention, lethal survival, first strike, native allocation,
uncertain hidden draws, retained intents, query purity, bounded shortlist/native
projection counts, exact-response unknowns and the unchanged block metric. The
audit module covers ten styles, two families, both seats and three conditional
combat cases; it is not the required thirteen-style strength benchmark.

The full discovery failure is
`tests/regression_agent_wave2/test_restart_and_additional.py::test_pending_modal_discard_choice_survives_sqlite_restart`.
Its attempted connection targets the owned pytest temporary database and is
denied at `sqlite3.connect` before a connection is created. That is an execution
boundary, not evidence that the restart behavior passes or a new product defect.
No SQL exception or database-read permission was added for this attempt.

## Evidence And Remaining Scope

Three packets each contain 5,135 public files with verified SHA-256 and Git blob
IDs. The complete current 2,697-file backend matches the final packet. An AST
comparison permits exactly the two declared production deletions and no other
production change. All source pins remain unchanged during execution.

The extracted actual guard passes thirteen denial controls; its function ASTs
match the versioned executed drivers. Focus and original combined executions use
their retained driver versions. The failed-module follow-up and full attempt use
the driver with the explicitly owned artifact destination. Runtime denial counts
are zero except the one recorded full-discovery SQLite denial. There are no
runtime SQL connections, socket constructions, ASGI loops or child launches
inside the workers. The fence is not a general filesystem sandbox.

All five supervised epochs are directly reaped, with explicit process-group
absence, no outer stop and no leftover group. The corrected audit module writes
120 private synthetic-position artifacts; their names and SHA-256 hashes bind to
the execution. No snapshot, hand, raw trace or private evidence body is committed.
The verifier's first draft stops at a metadata-only inverse-transform error;
the corrected verifier passes without repeating application execution.

Private evidence is retained in
`/home/nick/mtg-rc-evidence-20261108/master-death-block/`, including declarations,
versioned drivers, JUnit, source bindings, closure records and
`FINAL-VERIFICATION.json`. Fresh read-only review independently verifies the
source, original assertions, result/closure hashes and driver bindings, with no
actionable findings. Commit and exact-tree export records are retained alongside
this evidence; they do not change its qualification scope.

A fresh read-only GitHub observation at 19:25 UTC still reports zero forks and
seventeen open PRs. All returned heads already exist in the base ancestry. This
does not publish the correction or transfer PR51's hosted result to it.

The fix preserves an immediately winning searched block in these canonical
positions. It does not prove every winning block survives a bounded shortlist,
general strategic preference, matched-game improvement or expert AI strength.
The original matrix partials, unresolved flags, full thirteen-style/data plan,
latency, current-source hosted/full-suite checks, pinned build inputs and browser/
native-runtime release gates remain open.
