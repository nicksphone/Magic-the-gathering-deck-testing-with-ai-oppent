# Graveyard Destruction Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Admit two complete stack-only destruction clauses without admitting unknown graveyard interactions.

**Architecture:** Add a whole-original-text grammar to the existing positive coverage function. Reuse complete pinned canonical fixture readers and native checked actions; preserve the inventory's other context and identity vetoes.

**Tech Stack:** Python3.12, native rules engine, pytest, existing metadata-only boundary runner.

**Spec:** `docs/superpowers/specs/2026-11-09-graveyard-destruction-coverage-design.md`

## Global Constraints

- The original RC scope remains open; no new full-backend or HTTP retry while IPC is blocked.
- No fixture/state/snapshot/result/failed-stream body reads, hashes or copies by tooling; public code and exact catalog resources only.
- CPU120/125, inner180/outer210 seconds,4GiB,128MiB,retries0,maxfail1; plain assertions, no autoload/cache.
- Preserve every existing test assertion and ordering; no runtime target/cost/resolution change.
- Work inline in the existing isolated branch. One fresh final Astra-high reviewer; one Important/Critical RED/GREEN fix pass.

## Review Focus

- Parenthetical functional tails must not disappear into reminder removal: test original-text rejection.
- Nonartifact creature restriction must survive paid casting: test artifact and land rejection without spending.
- Missing targets must not become optional: test checked-action rejection.
- Granted graveyard permissions must remain interactive/unknown: test permission veto.
- Normalized or restored characteristics must not waive source/context checks: test actual restored inventory and state preservation.

### Task 1: Complete destruction coverage and native continuations

**Files:** Modify `backend/rules_engine/oracle_effects.py`; create `backend/tests/test_graveyard_destruction_coverage.py`; create `docs/testing/graveyard-destruction-coverage-20261109.md`; update public RC handoff docs as needed.

**Interfaces:** Consumes `complete_stack_instruction_coverage(card)`, `public_graveyard_inventory(state, actor)`, existing canonical `tests.pending_permanent_fullraw.raw_card(name)`, and checked actions. Produces the existing receipt shape with `effect_key='destroy_permanent'`, `payload={}`, exact lowercase target domain and `residual=''` for exactly two complete instructions.

- [ ] Write native paid/illegal-target tests first, then positive inventory/attack tests for both seats and both canonical names. Assert native mana spent3 for Murder,2 for Go for the Throat; illegal artifact (Go for the Throat), land and absent targets preserve the complete original snapshot. Assert actual target/spell graveyard after restored resolution.
- [ ] Add whole-body negative tests for appended instruction, parenthetical instruction, condition, activated prefix, missing period and extra period; inventory keyword/grant vetoes stay non-inert.
- [ ] Prepare a new fixed-bound component epoch using only the approved public catalog plus the explicitly authored test source. Run the entire new module before implementation. Expected: native paid/legality cases pass, first positive inventory test fails with AssertionError; no private-body inspection. Record ordered phase metadata and closure.
- [ ] Extend only `complete_stack_instruction_coverage(card)` with an anchored match against the original stripped Oracle string for `Destroy target (creature|nonartifact creature).`; preserve all other branches.
- [ ] Run the entire new module and original whole modules `test_public_graveyard_inventory.py`, `test_target_restrictions.py`, `test_pending_removal.py`. Expected: all component phases pass,0deselection, no new boundary denial, monitor/loader release, source/reference metadata unchanged. Keep original full-backend acceptance explicitly blocked and historical failures named.
- [ ] Verify original source preimages/AST/assertions, document actual evidence and limits, commit the bounded change. Use task-done with a pure evidence auditor of the final epoch, not a replay. Expected: qualified component evidence only.
- [ ] Obtain one fresh whole-change review with the exact public source package and primitive evidence; rule on every declined item. Fix Important/Critical findings once using RED/GREEN plus green component suite. Retain rulings and produce source-only local patches without remote writes. Expected: clean tracked worktree and reconstructable exact-tree local handoff.
