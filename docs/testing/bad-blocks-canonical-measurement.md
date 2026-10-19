# Canonical Bad-Block Measurement

This qualifies the existing dominated-chump counter, not general blocking
quality or improved AI strength. No rules, AI policy, weights, private trace,
historical baseline or existing test assertions are changed.

## Reproduced Admission Bug

On published `4c37225aeee38b8047d03ecd968caccd5ae79df1`, the first 22-case
canonical cohort passes 20 cases and fails two in 10.02 seconds. A declaration
containing an unknown blocker is silently filtered by the low-level combat
executor, so the observer reports zero instead of unavailable. The expanded
unchanged-production cohort passes 22 and fails ten in 12.20 seconds: both-seat
missing attacker/blocker, duplicate blocker, tapped blocker and flying-attacker
restrictions reproduce the same admission defect. Neither run has fixture
errors, skips or native-I/O attempts.

The observer now reuses `checked_action` and its returned copy. Only copied
string-valued blocker selections are converted to singleton lists, retaining
the old valid legacy syntax without changing the request. Native legality,
payments and declaration postconditions are checked before measurement.
Rejected or unresolved projections retain the existing `None` result.

## Actual Qualification

The corrected whole new module passes all 32 cases in 11.64 seconds. Four
whole modules then pass 219 cases with 11 warnings in 21.12 seconds:

- `test_bad_blocks_canonical_fidelity.py`
- `test_task23_canonical_block_outcomes.py`
- `test_analytics_batch.py`
- `test_baseline_report_comparison.py`

Full pinned canonical cards use explicitly declared old boards, not paid
creature births. Independent checked priority actions resolve actual combat:
ordinary chump, lethal-preventing chump, trade, first strike and indestructible
outcomes agree with the observer. Native trample/deathtouch allocation remains
unavailable to the bounded observer. Both seats, valid singleton/list forms,
root/RNG/request preservation, snapshot restoration and opposing hidden-hand
identity permutation are covered. The latter qualifies this counter only,
not the entire AI information boundary.

A precollection audit hook denies SQLite, socket construction/connect/bind/DNS
and subprocesses. All four modules execute without denied attempts, leftover
threads or source/configured databases. All published source files and the new
test have identical gate-begin/end hashes. This is a Python audit boundary,
not an OS security sandbox.

## Remaining Acceptance

The counter compares a selected block against no block; it does not rank every
legal assignment, identify every missed winning block or distinguish all
future material value. Do not describe it as a complete blocking-quality
oracle. Matched before/after runs must use the same corrected observer, rules,
data, seeds, seats, budgets and metric definitions in both policy arms.
The original September baseline's unavailable `bad_blocks` is not zero and
remains immutable. No matched measurement or phase completion follows from
these component tests.
