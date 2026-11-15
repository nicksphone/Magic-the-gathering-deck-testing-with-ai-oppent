# Archetype matrix proposal — no measured games

This branch is a plan and inert planning/analysis harness only. It neither runs
AI games nor changes AI, rules, decks or source pins. Claude must review this
plan before a separate execution adapter and measured run. No earlier 110-series
prefix, timeout prefix, snapshot or result may be imported or resumed.

## Predeclared experiment

Use all eleven committed built-in lists, identified by name and exact deck text:
Mono Red Aggro, White Weenie, Blue Control, Dimir Control, Burn, Midrange, Ramp,
Drain Deck, Tokens, Tribal and Tempo. This covers the shipped roster; it does
not establish coverage of combo, reanimator or aristocrats. Those need reviewed
additional decks and a separately versioned experiment, not labels on these
results. Canonical metadata/support admission for every list remains required
before running; an unsupported card must stop admission, never be substituted.

Each of 55 unordered deck pairs gets 20 fresh fixed seeds, 2026111501–2026111520.
For every seed play both seat orientations with the same seed: 2,200 single
games. Both agents use master difficulty, normal hidden-information rules and
no sideboarding. This is not BO3 or a sideboarding-strength measurement. The
initial seed, seat assignment, original deck text and measured source revision
are frozen in the generated plan before execution. No seed selection after
seeing outcomes, retries, or silent omission. A pilot requires a different run
ID and seeds and never contributes a prefix to this matrix.

Proposed per-game ceilings: 120 seconds wall time, 10,000 accepted actions and
100 turns. The future controller must enforce the wall bound outside the game
process; a stuck decision must not hang the batch. These limits require review
before execution; they are not claims of adequate AI speed. Record all cells,
including timeouts, turn/tick limits, illegal actions, crashes and divergences.
Resource ceilings are unresolved outcomes, never losses or draws. Deck-out is
an ordinary engine win/loss with explicit cause; a genuine engine draw scores
half. No heuristic adjudication of unfinished positions. Global cancellation
leaves the matrix incomplete: analysis rejects missing cells. A new complete
run uses a new run ID; do not resume this plan under changed source/policy.

## Analysis

Report every pair, both seat win counts, draws, deck-outs, error/limit counts,
complete mirrored-seed blocks, latency distributions and decision-quality
availability. Preserve the full scheduled denominator. The current analyzer
reports outcome counts and score bounds; execution/latency/quality reporting
is work for the next adapter. Unresolved cells get score bounds 0–1, producing
worst/best bounds over *all* scheduled games; no resolved-only success rate.
No score CI is emitted for a pair with unresolved outcomes.

For fully resolved pairs, use the mirrored seed as the independent block:
average the two seat scores, then percentile-bootstrap those 20 block scores
(2,000 deterministic replicates, seed 271828 combined with pair identity).
Intervals are exploratory approximate 95% intervals, not calibrated guarantees;
20 blocks can give wide/degenerate intervals. Do not pool 40 dependent games as
independent trials or average all matchups into one skill percentage. Fifty-five
comparisons are descriptive, not multiplicity-adjusted significance tests.
Before/after claims require the same planned cells and a paired difference
analysis, separately reviewed; the current analyzer does not implement it.

## Trace and replay contract for the future adapter

Capture full initial hands/boards/RNG and each before/after snapshot in private
run output, plus actor, legal-action inventory, selected action, decision trace,
accepted-action count, elapsed time, termination cause and source/dependency
identity. Preserve raw traces locally; publish only reviewed aggregates. Never
print secret witness environment values. Each result names the trace SHA256.
Replay every accepted action under the same source, restoring at selected
boundaries; compare actor, legal actions, chosen action, full state and RNG.
The helper returns the first divergent step and field names only, including
missing-vs-null and boolean-vs-integer differences. It does not execute replay
or certify the hashes supplied by an external adapter. Stop/retain the first
divergence; never normalize IDs/state away to make a comparison pass. API,
simulator and fresh-process restart parity must be tested by the adapter,
not inferred from this pure comparison helper.

## Commands and scope

From backend, create an exclusive plan file in an owned output directory:

```sh
python -m scripts.archetype_matrix_plan plan FULL_40_CHARACTER_REVISION /tmp/new-plan.json
python -m pytest -q tests/test_archetype_matrix_plan.py
# Only after a reviewed execution adapter supplies every newly measured cell:
python -m scripts.archetype_matrix_plan analyze /tmp/new-plan.json /tmp/new-results.json /tmp/new-summary.json
```

There is deliberately no `run` command in this branch. Generated plans embed
all deck texts; review them and record their digest before running anything.
The revision argument is a declaration, not automatic checkout verification;
that verification and trace provenance belong to the future execution adapter.
Synthetic unit results test the math/schema only and prove no playing strength.
