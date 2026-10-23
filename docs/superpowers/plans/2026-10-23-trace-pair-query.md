# Trace Pair Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Remove a redundant stats derivation without changing trace contents.
**Architecture:** Reuse `effective_combat_stats(..., unknown_as_zero=True)` once
per row, preserving the original expression evaluation order and integer casts.
**Tech Stack:** Existing Python, stdlib unittest and unchanged canonical fixtures.
**Spec:** `../specs/2026-10-23-trace-pair-query-design.md`.

## Global Constraints
- All 14 resource limits, cumulative BO3 deadline and complete traces unchanged.
- No SourceB/F, protected index, private trace publication or existing test edits.
- Source-only owned checkout; native execution requires reviewed bounded C role.

## Review Focus
- Empty boards perform no stats queries.
- Noncreatures preserve the legacy unknown-as-zero behavior.
- Counters and end-of-turn modifiers remain fresh across successive snapshots.
- Full trace payloads retain exact legacy JSON bytes and state invariance.
- The pair call stays after types/tapped and before keywords; no persistent cache.

## Task 1: Preserve The Wire Image With One Pair Query
**Files:** Modify `backend/analytics/decision_quality.py::_battlefield_snapshot`;
create `backend/tests/test_trace_snapshot_single_query.py`.
**Interfaces:** Existing private snapshot and public continuous pair query only.
- [x] Write four native unittest methods using pinned complete fixture admission.
- [x] Qualify the no-SQL/network/source-write runner before native imports.
- [x] Run unchanged baseline: actual one pass/three call-count failures, no errors.
- [x] Change only the snapshot pair lookup/import after baseline closure.
- [x] Run the same four methods: all pass, with exact legacy payload comparisons.
- [ ] Independently review code, old-module preservation and native receipts.
- [ ] Commit and publish for whole hosted CI; do not infer RC or matrix acceptance.
