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
comparison. Native series 55 has not been rerun on this follow-up, and its
original deadline acceptance remains open. No resource caps, search branches,
payment plans, decisions, seeds, weights or winners are changed.
