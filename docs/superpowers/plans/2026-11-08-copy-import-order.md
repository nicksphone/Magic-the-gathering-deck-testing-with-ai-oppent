# Copy Import Order Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. No implementation delegation.

**Goal:** Keep the existing native Card metadata prefix available after ordinary standard-library imports without weakening its copy-protocol guards.

**Architecture:** Initialize `typing`'s standard copy reducers before the copier freezes its existing registry layouts. Keep exact registry equality, native bindings, caller memo, foreign-code latch and fallback behavior unchanged.

**Tech Stack:** Python 3.12, stdlib `copy`, `copyreg`, `typing`, pytest.

**Spec:** The design and constraints below; broader release requirements remain in `plan.md`.

## Design and Evidence

The captured Control benchmark imports `game_state.copying` before `ai.agent`.
The former freezes three `copyreg` entries; the latter imports `typing`, adding
`ParamSpecArgs` and `ParamSpecKwargs`. No existing dispatcher/reducer changes, but
exact whole-table equality now disables the prefix. A measured copy has zero
prefix calls and 7,278 standard keep-alive calls. This explains that benchmark's
fast/generic parity, not all observed AI latency. The original whole-game profile
already used the prefix for many copies.

Options considered: relax registry equality, accept import-order-dependent
fallback, or initialize the standard reducers before freezing. Choose the last:
it retains the existing conservative guard and does not introduce a new copy
algorithm. The application already imports `typing`; initialization moves earlier
for callers which import the copier first. This is an implementation choice within
the authorized RC fixes.

## Global Constraints

- No change to policy, difficulty, resource/search limits, hidden-input boundaries or mutable metadata isolation.
- Preserve exact registry equality and all existing fallback/foreign-hook controls.
- Never edit the live matrix source or repeat its natural games.
- Do not use private snapshots as committed test fixtures.
- Fresh-interpreter import controls must prohibit SQL, networking, children and protected private bodies.

## Review Focus

- Copier-first and typing-first imports must both retain native prefix operation counts.
- A later custom reducer must still disable the prefix and execute correctly when reached.
- Caller memo overrides, foreign hooks, key behavior, keep-alive exceptions and dynamic field hooks must keep their existing semantics.
- Actual captured copies must preserve complete pickle graphs and authoritative state/RNG.
- Timing comparisons must name import order and fresh-agent history limits; no whole-game speedup claim.

### Task 1: Reproduce and correct initialization order

**Files:**
- Create `backend/tests/test_copy_import_order.py`: bounded fresh-interpreter controls.
- Create `backend/tests/copy_import_order_worker.py`: pure synthetic metadata/control worker.
- Modify `backend/game_state/copying.py`: initialize stdlib reducers before the native layout snapshot.

- [x] Add copier-first and typing-first subprocess tests comparing default and supplied-empty-memo copies, requiring equal graph values and fewer standard keep-alive calls in the native mode.
- [x] Add a later custom-reducer control requiring fallback, reducer invocation and unchanged source metadata.
- [x] Run the whole new module on unchanged production; retain the copier-first failure and passing controls.
- [x] Initialize the standard reducers, leaving the equality guard and copier algorithms unchanged.
- [x] Run the new module and whole existing copy-protocol/hidden-input modules under declared IO bounds; retain every failure without filtering.
- [x] Independently review the final diff and evidence, then commit the bounded fix.

### Task 2: Validate the captured-state impact

- [x] Freeze final candidate backend and compare its copy graphs/timings on the existing three captured states against the retained baseline.
- [x] Run one fresh Master choice per candidate source revision on the existing slow state; compare complete action and root/RNG preservation. Two candidate qualifications are retained, one before and one after the reducer-preservation fix, plus the original baseline. These are diagnostic choices, not new natural games or original-agent-history reconstructions.
- [x] Document exact source, import order, test scope and measurement limits; update the local patch export after review.

## Execution ledger

- Original source: one expected import-order failure, two controls pass. First correction: three pass; existing ten whole modules pass235 separately.
- Review finds preexisting Args/Kwargs reducers overwritten. Both failures reproduce; the correction restores only the prior identity-matched entries. Five fresh controls and the final ten-module235 cohort pass.
- Ruling: preserve preexisting collisions while initializing stdlib defaults; do not relax registry equality — this fixes the observed import gap without weakening custom-protocol fallback.
- Ruling: final fresh-agent qualification overlapped the protocol cohort; retain it for behavior/latency evidence, not speed attribution. A separate final-source copy-only epoch runs after both close and spends no extra AI decision.
- Ruling: the reducer correction changes production initialization, requiring a new source-bound qualification choice. Preserve the initial candidate rather than transferring its result to the reviewed source; actual total is two candidate choices plus one baseline.
- Captured reconstruction998 matches; baseline and final fresh decisions/actions/history/root/RNG match, but original whole-game agent histories are unavailable. No natural game is repeated.
