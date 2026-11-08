# Sacrifice Eligibility Query Scope Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. No implementation delegation; independent read-only review before adoption.

**Goal:** Remove redundant immutable battlefield classifications from sacrifice eligibility without changing costs, candidates, policy or search allowances.

**Architecture:** Give `_eligible_sacrifice_ids(state, player_id, kind="creature", *, payment_kind="spell")` one synchronous rules-query scope around its existing calculation. Close it before returning to payment/mutation callers. Reuse matching outer scopes under their existing nonmutating contract; do not memoize results across calls or mutations.

**Tech Stack:** Python3.12, existing `rule_query_scope`, full canonical fixtures and pytest.

**Spec:** Evidence and constraints below; Gates1–3 and the larger AI/data scope in `plan.md` remain open.

## Design and evidence

The current captured31-permanent Control position yields identical eligibility
and complete root/RNG under one pure query scope. Standalone creature/permanent
eligibility for seat1 reduces scan-generator calls448->32, and seat2 reduces
544->32. The complete current Master profile exposes sacrifice eligibility among
remaining classification callers. Existing caller scopes may already cover some
calls: a complete captured decision/profile must demonstrate actual reduction
before adoption. The mana-query lead is separate, not included in this change.

Choose one local immutable scope over broader action/payment scopes, persistent
caches or changed search policy. The existing body stays unchanged in a query
helper; the existing public helper forwards every parameter inside the scope.

## Global constraints and review focus

- No changes to payment, eligibility order/filters, printed data, hidden information, search limits, model weights or game defaults.
- Scope ends before caller mutation; later zone/controller/type changes must be visible.
- Keep subtype/color resources, `spell`/`activation`/`mana` distinctions, can't overrides and controller checks.
- Preserve returned-list independence, nested-scope identity, error restoration and complete root/RNG.
- Private game/hand/agent/snapshot bodies never become public fixtures or repository artifacts.
- Never restart or alter the original full matrix91698; retain every failed/setup epoch.

### Task1: Regression and minimal correction

**Files:** new `backend/tests/test_sacrifice_query_scope.py`; `backend/rules_engine/costs.py`.

- [x] Add operation-count tests on full canonical Forest/Bears boards, both seats and creature/permanent kinds, requiring one full scan and exact ordered results/root/RNG.
- [x] Add fresh-query controls after native type/zone/control changes, subtype/color filtering, full canonical payment prohibition, list independence, nested scope and injected-error restoration.
- [x] Retain meaningful RED on unchanged production; add only the public scope wrapper and unchanged-body query helper.
- [x] Run the full new module and relevant whole cost/resource/layer modules in owned bounded workers; retain full-command environmental failures rather than exclude tests or weaken guards.

### Task2: Captured impact and adoption

**Files:** acceptance documentation and this plan; private source-bound evidence/patch exports.

- [x] Freeze candidate source and reconstruct the existing998 accepted partial actions with no AI/new game.
- [x] Declare at most one uninstrumented fresh Master choice and one allocation profile for the accepted candidate source; compare complete action/decision/fresh-agent-after/root/RNG and actual work against68b9.
- [x] Reject the candidate if complete-choice work does not improve, regardless of passing standalone controls. Do not claim general latency or strength from bounded timings.
- [x] Obtain independent read-only source/evidence review and prepare the accepted change for commit/export. Verify exported patches reproduce the committed tree before reporting completion.

## Execution ledger

- RED8 expected classification-count failures/25 passes; GREEN33passes1.75s.
- Whole15 canonical cost/resource/layer modules:456 ordinary passes,88warnings,
  48.99s;5123 frozen public inputs unchanged,80SQLconnections/15owned files,
  14ASGIloopfixtures and normal worker/group closure;no IOdenials/children.
- Captured replay998 matches with0AI/newgames;one unprofiled choice32.45s and
  one profile48.18s preserve full action/decision/agent-after/rootRNG and inputs.
  The uninstrumented choice overlapped other workers; no quiet unprofiled rerun or
  wall-speed claim. Profile follows their closure; prior profile47.56s.
- Actual whole-choice scans4795845->4338161,eligibility1871calls onbothsources;
  copies945/917 unchanged. Actual work reduction meets adoption criterion;
  practical latency remains open.
- Runner-generation first attempt failed before application work; corrected
  extraction/indentation is retained in DECISION-PREPARATION-ATTEMPTS.json.
- Full backend entry (no module/keyword filter,--maxfail1) retains first missing
  source-admission setup failure and second optional archive Path.exists
  PermissionError collection failure. No test/assertion/skip changes;fullgateopen.
- Parent public-source/metadata verifier passes; independent final review accepts source/tests/evidence. Verify accepted
  commit/export tree before reporting completion.

- Final review corrects controller-filter wording and the uninstrumented-only
  overlap statement; no new application execution or private payload reads.
