# Attachment Check Preflight Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; no implementation delegation.

**Goal:** Avoid repeated battlefield classification when attachment state checks have no work, while preserving the existing mutation path and rules outcomes.

**Architecture:** Run one immutable query-scoped preflight. Return only if every battlefield card has no attachment target and is neither Aura, Equipment nor Fortification. Close that scope before the unchanged per-card mutation loop when any candidate exists.

**Tech Stack:** Python3.12, existing rules query scopes, canonical fixture records and pytest.

**Spec:** Constraints and checks below; full release scope remains `plan.md`.

## Evidence and design

The captured slow Master state has31 battlefield permanents and no attachment
candidates. The existing helper makes992 battlefield-scan generator calls;
one read-only classification batch makes32, preserving the full root/RNG.
Its per-card query scopes repeatedly rebuild the same immutable view. The
previous ranking-cache experiment did not reduce the actual captured work and
was rejected; do not reactivate it or weaken search to improve timing.

Choose a no-work preflight rather than carrying cached classifications across
departures. Any target or attachment category falls through to the old loop,
preserving its order, fresh scopes, replacement preflight and events.

## Global constraints and review focus

- No policy, difficulty, search/resource limit, printed data or mutable copy change.
- Auras without targets still leave; invalid targets, nonattachment detachment and bestow still execute the existing paths.
- Equipment/Fortification remain on the battlefield when detached.
- Discard preflight queries before any mutation; later cards must observe earlier departures.
- Complete root/RNG and accepted replay actions must match; private snapshots never become public fixtures.
- Never restart or alter the original full matrix.

### Task1: Regression and minimal fix

**Files:** `backend/rules_engine/state_based_actions.py`, new `backend/tests/test_attachment_check_preflight.py`.

- [x] Add no-work operation-count/purity tests and canonical attachment, bestow, invalid-target, atomic-preflight and mutation-scope controls. The abstract Fortification control is structural, not a real-card support claim.
- [x] Retain meaningful RED on unchanged production, then add only the preflight.
- [x] Run the whole new module and relevant complete attachment/layer/departure modules under explicit owned IO bounds; preserve environment/setup failures.

### Task2: Captured impact and review

- [x] Freeze candidate source; verify operation reduction on the retained actual state, full accepted998-action reconstruction, and a bounded fresh Master choice with complete decision/agent/root/RNG equality. No new natural game.
- [x] Evaluate actual measured benefit before adoption. Independent review must cover mutation boundaries and fallback cases.
- [x] Finish independent evidence review and prepare the accepted change for commit/export. Verify the exported committed tree before reporting completion.

## Execution ledger

- RED: four quadratic-work failures and 23 passes; GREEN:27 passes,1.38s.
- Captured helper:992 to32 scan-generator calls,124 to94 layer-four calls;
  complete root/RNG unchanged. Fresh Master choice19.54s, complete action,
  decision and fresh-agent-after equality;0 new natural games.
- Existing partial reconstruction:all998 accepted actions match,turn33,no winner;
  no AI calls or new natural games. Both bounded workers close normally.
- First whole epoch:309 pass/8 audit-denied undeclared Aura restart children;
  no original assertion changes. Preserve the failed epoch.
- Reviewed second harness adds only exact owned snapshot roundtrip children and
  a pinned preimport guard in their test environment. Pure launch controls pass
  4allow/19reject plus2 exact-wrapper controls before the one-shot launch.
- Final nine whole modules:317 ordinary tests,70 warnings,160.21s;2878 source
  pins unchanged,16 owned SQL file connections,20 readonly children closed,
  zero denied operations and normal supervisor/group closure.
- Parent metadata/source verifier passes without additional application calls.
  No operator-capacity, browser, native Forge, whole-game, strength or release
  certificate follows; the original frozen matrix is untouched.

- Final independent read-only review accepts source/tests/evidence with no blocker;
  pending-review wording and connection-versus-distinct-file wording corrected.

- After commit68b9fffb, a separately declared one-choice allocation profile
  preserves all complete outputs/root/RNG/pins and closes normally. Actual
  whole-choice layer-four scan-generator calls fall5803456->4795845, while
  total/planning copies remain945/917. Instrumented47.56s is not latency
  acceptance. Actual candidate total:one uninstrumented qualification choice
  plusone post-change profile;zero new natural games.
- Both initial cumulative/per-fix patches apply to their exact preimages and
  reproduce the68b9fffb committed tree; private PATCH-VERIFICATION.json retained.
