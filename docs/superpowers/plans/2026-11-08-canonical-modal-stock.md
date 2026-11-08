# Canonical Modal Stock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the handwritten positive Mountain stock in the shared modal-spell fixture with its complete pinned official object.

**Architecture:** Reuse `tests.canonical_positive_fixtures.deck_entry("Mountain", 32)` at the existing native `MatchFactory` boundary. Keep the shared helper's seeds, quantities, scene mutations and every gameplay assertion. Its four importing modules receive the same correction without changing their code.

**Tech Stack:** Existing Python/pytest fixtures and pinned Scryfall JSONL; no new dependency, data intake or production code.

**Spec:** [Task 1.3](../../plans/2026-09-09-ai-knowledge-base.md#task-13-delete-hand-written-fallbacks-replace-with-verified-seed-file) and [current RC requirements](../../testing/rc-readiness-20261108.md).

## Global Constraints

- Task 1.3 acceptance remains “zero hand-maintained oracle text in the repo; offline startup works from committed seed.” This finite correction does not waive synthetic/parser/negative scope or sign off the task.
- Preserve 32 copies per seat, seed 7134 for stock and 7135 for the original spell sample.
- Preserve all original test names, parameters and assertion ASTs in all five whole modules.
- Keep Incendiary Command RAW, shared canonical loader, official data, production, policy and resource caps unchanged.
- Never open protected owner/model bodies or user databases; qualification denies all SQL, sockets and children.

## Review Focus

- Both physical seats receive the same complete pinned Mountain input.
- Native card and printed-characteristic Oracle text retain the official value.
- The real modal spell and its original printed mode order stay unchanged.
- Declared synthetic targets and adversarial parser probes retain all existing checks.
- Whole affected modules pass without new filters, skips, source-pin exceptions or assertion changes.

### Task 1: Correct the shared positive input

**Files:**
- Modify: `backend/tests/test_incendiary_modal_root.py` (one import and the stock-row expression).
- Qualify whole: that module plus `test_incendiary_modal_boundaries.py`, `test_incendiary_modal_lifecycle.py`, `test_mode_target_native_schema.py`, and `test_modal_targetless_announcement.py`.

**Interfaces:**
- Consumes existing `deck_entry(name, quantity)` returning the complete official object under `card_metadata`.
- Preserves `position(seat)` returning the original prepared `(state, source)` pair.

- [ ] Capture a failing private fidelity witness on the unchanged source: both actual Factory deck inputs and native Oracle/printed fields must equal the pinned Mountain facts. Stop no assertions or game setup to manufacture a pass.
- [ ] Make the single fixture migration; add no permanent tests that merely mirror this low-impact expression.
- [ ] Pass the same fidelity witness, then run all five complete original modules once under a declared pure-IO guard and bounded owned process group.
- [ ] Verify source/input hashes, complete test identities/assertions and process closure; obtain independent read-only review, document the source boundary and export the committed patch.

## Execution Ledger

Ruling: this is an authorized fixture-data correction within the existing RC/Task 1.3 objective. It requires no product design or publication approval. The direct-literal census is exploratory, not an exhaustive inventory or a waiver for the remaining sites.

Current status: plan written before fixture implementation; no candidate source or qualification outcome yet.
