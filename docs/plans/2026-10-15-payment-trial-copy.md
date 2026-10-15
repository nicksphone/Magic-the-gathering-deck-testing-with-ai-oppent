# Payment Trial Copy Implementation Plan

> Execute inline with TDD; request one independent review before publication.

**Goal:** Reduce measured payment-planner cloning cost without changing payment
search, decisions, complete histories, resource accounting or gameplay.

**Architecture:** Extract the existing AI selective card copier into
`game_state.copying`. Its default keeps history. The existing AI wrapper
explicitly retains its old history-omission and caller-memo policies. Only
three trial-copy calls in `rules_engine.mana._plan_payment` use the shared copier.

**Tech Stack:** Existing Python dataclasses, standard-library `copy`, pytest.

**Evidence:** Exact-source series-55 chooser profiling identifies copying inside
recursive payment planning. A corrected 54-clone, no-game comparison passes
whole values, RNG, history, aliases and sibling isolation. Selective copying is
faster on the declared fixtures; this is not yet a native-game speed claim.

## Constraints

- No search pruning, plan cache, decision weights, caps, seeds or winners change.
- No rules-engine import from AI; no new dependency or persisted schema.
- Retain every payment-trial history entry and mutable-state isolation.
- Keep existing AI history policy and `_copy_card_field` test access.
- Preserve the existing benchmark's dynamic field-copy ablation hook, not just
  its import name. Honor caller attribute-dictionary memo overrides rather than
  overwriting them during fast-path setup; characterize the old defect first.
- Exact-type optimization only; subclasses/custom copying retain fallback.
- No user/live DB, public private trace, provider, training or learning use.

## Execution

- [x] Add failing shared-copy and actual paid-planner regressions. Check baseline
  failure before implementation; retain all original tests.
- [x] Extract the existing copy machinery, preserving aliases/cycles/memos and
  adding explicit default history retention. Replace only three mana copies.
- [x] Run new tests plus unchanged selective-copy/projection modules under
  pre-import SQL/socket/process denial. Compare complete payment plans, native
  branch visits, snapshots, RNG and event/history order against stdlib copying.
- [x] Run the whole affected mana/resource/payment and AI neighbor declaration
  on an owned source-only checkout, including actual HTTP where present.
- [ ] Validate the actual previously deadline-limited series 55 on the exact
  candidate, with its original shared 600-second BO3 budget and reference
  first-game hash. A one-series result is not full-matrix acceptance.
- [ ] Independent review; correct any findings with regressions. Refresh the
  graph, archive private evidence on verified NFS, commit and push normally.

## Review Focus

- Caller memo overrides must not be overwritten or mutated.
- Cards, their attribute dictionaries and cross-field aliases must share one memo.
- Mutable nested metadata and cycles must remain independent of the source.
- History subclasses and custom copy contracts must not take exact-list shortcuts.
- Local clone measurements do not prove native matrix completion or AI strength.

## Functional Checkpoint

Local candidate `7e81e30e6137e3012b7c485b764b60a1bc80ff59` passes 1,505 cases
in 30 whole modules (849.32 seconds, zero failures/errors/skips). All 1,990
source files match before/after, 52 child commands end and 29 actual local
database files have no remaining handles. The original Tempo/Blue Control
seed-731 game completes naturally; its 316.555-second call is not a matched
speed comparison or evidence about the separate series-55 deadline.

The first broader run stopped during collection with nine errors and zero SQL
connections because its runner explicitly configured a forbidden source-relative
database path. Removing only that override lets the unchanged tests use the
default in their isolated copy. The failed runner and ledger are preserved;
no production database admission rule was weakened.

## Native Checkpoint: Not Accepted

The exact `7e81e30e` once-only native series-55 run ends with resource exit 3.
Game 1 retains the original hash, winner and 421 accepted ticks. Game 2 reaches
269 accepted ticks but still exhausts the original shared 600-second series
budget. Every one of the old 261 accepted Game-2 traces is an exact prefix;
the eight additional ticks do not demonstrate a material speedup or close the
deadline. The candidate remains local, not published as a performance fix.

The functional code review is clear. That result and the 1,505-case pass do not
override the actual native failure. The original full matrix remains open.

A separate six-copy measurement on the actual hydrated 120-card initial state
identifies nested knowledge as the largest measured card-field copying cost.
The first recursive prototype preserves values, aliases, cycles, RNG and all
15 sibling-isolation comparisons, but is slower in both instrumented and direct
uninstrumented comparisons. It is not integrated. Further prototypes must
demonstrate useful direct-copy improvement before product integration, then
retain whole functional and native acceptance requirements.

## Nested Metadata Follow-Up

The smaller follow-up inlines immutable child values while preserving memo
overrides, dictionary value-before-key ordering, cycles and stdlib fallback for
custom objects, keys and subclasses. It never shares mutable canonical metadata.
Three direct hydrated-state comparisons measure 0.0383/0.0390/0.0393 seconds for
the earlier helper and 0.0358/0.0366/0.0357 seconds for the follow-up. All six
copies and all 15 sibling-isolation comparisons pass. These are small copy-only
measurements, not a native-game speed or strength result.

The new eight-case module first reports five failures and three passes. The
corrected four-whole-module pure cohort passes all 65 cases in 16.69 seconds,
with no SQL/socket/process/provider attempts. Independent source review finds
no actionable issue and confirms the AI ablation hook remains active.

The original 30 affected modules plus the new module then pass all 1,513 cases
in 862.73 seconds, with no failures, errors or skips. All 1,991 source paths and
the parent worktree index remain unchanged. All 52 registered child commands
end, 14 engines are disposed, no connection is left for runner cleanup, and a
corrected direct check of all 29 owned database files finds no handles. The
first closure command returned `fuser` usage because this binary rejects `--`;
that invocation and the actual corrected scan are preserved separately.

The natural-game call passes in 317.431 seconds; this is not a matched timing
comparison. No resource caps, search branches, payment plans, decisions, seeds,
weights or winners are changed.

## Native Follow-Up: Deadline Still Open

The subsequent exact `60b26ec1ef2218c1ce659727dec2f65ea13b6052` native run
also ends with resource exit 3. Game 1 matches the complete retained reference:
winner 2, starting player 1, 421 ticks, turn 14 and log hash
`d998349bc2b41818023c3c02e5c23fbe710eaa5ea4d4a0e7791127ec1dc60ab8`.
It takes 108.47 seconds. Game 2 again reaches 269 ticks, turn 9, with log hash
`f82248ad0dc6a9fd669d9b4ec4d8eb2877f74ebe865e809e08a99d69a6bbaac3`,
then hits the unchanged shared deadline without a winner. Its 511.70 seconds
are not a fresh per-game budget. The complete series takes 620.37 seconds
wall time and 618.60 seconds CPU; the deadline is cooperative.

The once-only host supervisor retains the fixed native-exclusive lease through
post-run source/runtime verification, owned process-group closure and a direct
check of all six output files. Source and dependencies match, all owned process
groups end, SQL closes, and there are no writers, threads or policy denials.
Clean closure is not a passing matchup. No material native speed improvement or
deadline closure is established, and 109 other series are outside this run.
Independent comparison finds all 623 Game-2 log entries and all 269 complete
AI traces identical to `7e81e30e`, without exclusions. Private closed-root
evidence is archived under
`diagnostics/ci/native-series55-60b26-20261015-xmm5dzqr/` on NFS.
Further diagnosis needs a genuine late-game chooser profile: the older compact
action traces omit selected-choice IDs and cannot support guessed replay.

## Profiled Late-Game Diagnostic

A separate once-only run on the same `60b26ec1` source profiles one genuinely
executed main-phase chooser call: game 2, tick 242, turn 9. The profiler records
10.36 cumulative seconds for that call, not an independently stored stage-wall
measurement. Within it, 98 `copy_match_state` calls account
for 6.04 cumulative seconds, including 2.12 cumulative seconds in the card-field
helper. These overlapping cumulative times must not be added. The retained
cost-sorted report contains 64 source-bound functions, explicitly omits 604
other source rows and counts 73 unknown entries. It is not a complete call graph
or evidence that every chooser invocation has the same cost distribution.

This instrumented series still ends with deadline exit 3: game 1 matches the
original reference, and game 2 reaches 267 accepted ticks with no winner.
All 267 AI traces match the unprofiled reference prefix. The selected tick is
among the accepted actions, not a synthetic or repeated chooser invocation.
The shared 600-second budget and all other caps remain unchanged. Profiling
overhead is included; 603.06 seconds wall and 601.50 seconds CPU do not establish
an unprofiled speed result or a gameplay regression from the earlier 269 ticks.

Source/runtime checks, owned-group closure and all seven output-file handle
checks pass. The private closed-root archive is
`diagnostics/ci/native-series55-late-profile-60b-20261015-bdjmz86f/` on NFS.
The subsequent bounded experiments below retain complete fields, mutable-state
isolation, histories and payment search. Neither is integrated as a performance
fix merely because its correctness tests pass.

## Rejected Root-Container Prototype

Three alternating baseline/candidate pairs copy the same genuine hydrated
120-card initial state. The measured candidate passes its 78-case correctness
cohort and all six complete-value/RNG/history checks, but the median copy-only
difference is approximately 3.5% across three variable pairs. No useful native
gain is established. A separate hook correction passes 82 cases but is not
timed; its bytes must not inherit the earlier measurement. Both remain rejected
prototypes, not product changes.

## Paid-Prefix Candidate: Not Integrated

The candidate shares identical checked announcements and settled projections
between friendly-destruction and unanswered-outcome queries, retaining complete
root/action identity and callback safety. Initial review exposes an eager winner
read before the unanswered consumer's hidden-zone check. Twelve strict new
regressions first fail; lazy access then preserves both consumers' original read
order and counts. The corrected 12-whole-module component passes 267 cases.

One fresh 48-whole-module execution subsequently passes all 1,946 cases in
924.93 seconds, with no failures/errors/skips and the complete existing natural
game retained. An earlier same-roster run records 1,940 passes and six cold-worker
failures from a missing launcher environment value. Restoring only the original
isolated-root/TMPDIR environment closes those failures; product and test bytes
are unchanged between the two executions. Both ledgers remain distinct.

The separate unprofiled native run still ends at the unchanged shared deadline.
Game 1 has the exact original hash/winner/421 ticks and takes 107.69 seconds,
against 108.47 seconds for the retained reference, only a 0.72% difference.
Game 2 reaches 288 ticks and turn 10 rather than 269 ticks and turn 9, but has
no winner and no qualified quality result. All 1,010 Game-1 entries and all 623
common Game-2 entries match as complete strings, without dropped fields.

The series records 603.25 seconds wall and 598.48 seconds CPU. The earlier
620.37-second reference has a larger cooperative-deadline overshoot; subtracting
these totals does not establish a causal speedup. Tick costs are nonuniform,
and one short cohosted archival operation is disclosed without attributing an
effect. Source/runtime preservation and process/SQL/lease closure pass, but the
experiment does not establish enough benefit to justify merging its private
frame cache. Candidate patch `538e4fbd` remains archived and unmerged.

Closed private evidence is under
`diagnostics/ci/20261015-paid-prefix-1946-PASS-io66jcpx/` and
`diagnostics/ci/native55-paid-prefix-deadline-20261015-k74PQRQw/` on NFS.
This does not complete a matchup, the 110-series matrix or measured AI strength.

## Next Diagnostic Boundary

The closed packet has no complete late root, RNG/topology reference or full
choice-bearing action sequence. Its compact traces cannot justify an inferred
replay. Future targeted timing first needs a genuine checkpoint and exact helper
inputs, with restoration validated before measuring anything. Full chooser
reproduction would additionally require agent and module-cache history.
High payment-plan call counts and overlapping cumulative times alone do not
prove reusable inputs; mutable postconditions and shared search-node budgets
must not be memoized away. No further cache or search change is authorized by
the rejected measurements themselves.
