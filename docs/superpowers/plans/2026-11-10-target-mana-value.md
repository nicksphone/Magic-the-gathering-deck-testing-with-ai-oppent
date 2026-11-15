# Target Mana Value Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make supported target restrictions use rules mana value rather than a payment estimate.

**Architecture:** Reproduce native hybrid-counter and snow-exile admission failures, then reuse the existing `mana_value` helper in `_target_card_matches_restrictions`. Preserve target spell X and every other restriction/caller.

**Tech Stack:** Python3.12, native rules/actions, pytest, existing positive-source phase/resource boundary.

**Spec:** `docs/superpowers/specs/2026-11-10-target-mana-value-design.md`

## Global Constraints

- Original full RC/AI-data/thirteen-style/rules/platform scope stays open. No full backend/HTTP/TCP/Forge retry without observed external IPC change.
- Native-only fixture/provenance bodies stay native-only; tooling must not read/hash/copy state, actual runtime bodies, opaque output, failed diagnostics or tracebacks. Exclusive outer captures precede interpreter compilation.
- Preserve CPU120/125, inner180/outer210seconds,4GiB,128MiB,retries0,maxfail1; -I-S-B/plain assertions/no autoload/cache.
- Existing tests, payment helper, mana-value helper, AI scoring and search limits stay unchanged. No card-specific exception or fabricated printing.
- Inline in the existing isolated branch, one fresh Astra-high final review; one Important/Critical RED/GREEN fix pass without re-review.

## Review Focus

- Two-brid symbols count by rules mana value despite different real paid amounts; target hint, checked cast and native resolution must agree.
- Snow symbols count one; illegal X=0 removal must reject atomically while X=1 succeeds.
- Stack X belongs to the target spell; preserve actual paid Walking Ballista X=1 versus X=2 boundaries and copied/selected-face neighbors.
- Target bounds and source contexts remain unchanged; declared graveyard populations do not imply naturally reached games.
- Complete canonical readers, caller snapshots, offered moves and restored frames stay authoritative; no mocked endpoint or rewritten printed fact establishes a positive case.

### Task 1: Use rules mana value in target restrictions

**Files:** Modify `backend/rules_engine/oracle_effects.py`; create `backend/tests/test_target_mana_value.py`; create `docs/testing/target-mana-value-20261110.md`; update README/plan/RC report.

**Interfaces:** Consumes `mana.mana_value`, existing `infer_target_restrictions`, `build_cast_hints`, `checked_action`, native priority passes, serializer and original canonical helper readers. Produces unchanged Boolean target restriction API and unchanged legal action schema.

- [ ] Write a whole50case module:6native paid Spectral Procession witnesses (both seats; white/mixed/generic);12Disdainful Stroke counter cases (both seats/restored/current/three payments);12Drown in the Loch illegal low-graveyard cases;4sufficient-graveyard controls;8Walking Ballista target-X controls;8snow permanent March X=0/1 cases. Expected: canonical facts unchanged; real paid native actions and atomic rejection assertions, no positive mocks.
- [ ] Run the whole new module before implementation. Expected: six native payment/resolution witnesses pass, then the first legal Disdainful Stroke target assertion fails; no boundary denial and normal owned closure. If not, investigate before any production change.
- [ ] Replace payment-estimate summation in `_target_card_matches_restrictions` with existing rules `mana_value`, preserving caller X and all other predicate logic. Expected: only an import and the local calculation change; no helper/payment/caller or old-test modifications.
- [ ] Run the entire new module followed by six original whole modules: `test_copy_stack_characteristics.py`10, `test_copy_stack160_fixture_fidelity.py`17, `test_mana_system.py`37, `test_ai_hybrid_cast_choices.py`45, `test_low_mana_value_cast_trigger_boundaries.py`8, `test_source_linked_payment_matrix.py`16. Expected:183unique ordered nodes, all passing phases,0deselection/denials, unchanged source/reference metadata, released loader/monitor and normal owned closure. No filtering/partition/retry.
- [ ] Audit exact source preservation and primitive RED/GREEN receipts, document limits, commit. Completion command: `/home/nick/MTG/backend/.venv/bin/python -I -S -B /home/nick/mtg-rc-evidence-20261108/target-mana-value-work/verify.py`. Expected: bounded production correction verified, all other prior approved Python sources unchanged, no full-RC claim.
- [ ] Obtain one fresh whole-change/public-boundary review, rule on all declined judgments, perform one required correction pass if any; export only exact public paths and reconstruct final trees, update primitive handoffs and retain/remove only this plan scratch. Expected: clean tracked tree, all evidence retained, original full goal active.
