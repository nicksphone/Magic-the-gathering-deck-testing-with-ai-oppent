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

## Frozen resource budget and pilot prerequisite

Use **two workers**, each limited to one CPU core, 2 GiB resident/address-space
budget for its process tree, and 90 CPU-seconds per game, alongside the 120s wall,
10,000 action and 100-turn ceilings above. The adapter must enforce these limits
on the worker tree, not only its parent. Do not oversubscribe: insufficient host
capacity stops admission. Two simultaneous workers require at least two available
cores plus controller headroom and 4 GiB worker memory plus runtime headroom.
At the wall ceiling the matrix is 73.3 worker-hours, approximately 36.7 hours at
two workers, plus startup/trace/replay overhead. That is a ceiling, not an expected
duration or permission to spend that budget without review.

**Expected duration is currently unknown; no pilot has run.** Before adapter
execution approval, use a separate `archetype-pilot-20261115-v1` plan: the eleven
adjacent pairs in the alphabetical roster cycle (including last/first), seeds
2026111601 and 2026111602, both seat orientations: 44 games. It uses the same
worker/resource/trace policy and is never merged into the main matrix. Record
per-cell wall/CPU/RSS, replay time, p50/p95, timeout counts and total elapsed time.
Forecast the matrix as 2,200 × pilot mean per-cell wall time / 2 plus measured
startup/replay overhead; also report the p95-based scenario and the ceiling.
A small pilot cannot establish a reliable tail bound; obtain Claude's budget
approval using the observed estimate before launching the full matrix.

Host suspend/sleep, controller crash, lost worker identity or interrupted trace
invalidates that run. Keep failed evidence, close owned workers using the
reviewed controller, and issue a **new run ID and output directory**, never resume
or splice its prefix. Worker failures remain recorded outcomes if the controller
can finish all cells under unchanged policy; they fail the health gate below.

## Pre-registered RC engine-health gate

These thresholds are frozen in generated `policy.health_gate`, before data:

- All eleven decks pass canonical/support admission; all 2,200 cells and traces
  are accounted for; **zero** missing cells/traces.
- **Zero** worker crashes, illegal accepted actions, replay divergences or
  API/simulator/restart parity divergences.
- At most **1% (22 of 2,200)** cells hit a resource ceiling (wall, CPU, memory,
  turn or tick limit; count their union once per cell). Report each cause and
  pair; no trading an error/divergence against this allowance.

Passing means only acceptable *declared engine-health coverage for this matrix*.
It does not accept AI playing strength or supersede AI-STATUS.md. Stronger
strength claims remain open. Limits/errors still give unresolved score bounds,
not inferred wins or losses. The current analyzer does not certify crashes or
trace/parity provenance; the next adapter must collect and enforce the gate.
Any threshold change after seeing pilot/matrix outcomes requires a new reviewed
plan, not retrospective relabeling of the run.

## Mirrored-seed semantics

The future adapter will use the **normal engine seed with swapped seats**. It
will not fix shuffles by deck. The same seed with decks exchanged between seats
can therefore give different hands and draw sequences to a given deck. This is
seat-balanced, not an identical-hand counterfactual. Both games remain one seed
block for descriptive uncertainty; independent-block inference assumes distinct
seed streams are representative, not a theorem about the PRNG. Seeds are shared
across matchups too, so matchups are not independent populations. No pooling or
causal strength claim follows from pairing alone.

## Per-deck admission inventory

Source examined: production `main-e51` (`e51ddb82`) plus this harness. Reproduce
with `python -m scripts.archetype_matrix_plan admission /tmp/new-admission.json`.
This reads only committed built-in lists and seed metadata; it uses
`ready_for_match`, the existing `admit_execution_rows` inventory check and actual
`deck_pair_coverage`. No DB, remote metadata, game or old run output is consulted.
All eleven lists have complete seed-only canonical readiness/inventory checks.
The **exploratory known-gap screen** is:

| Deck | Current admission screen |
| --- | --- |
| Blue Control | Pass known-gap screen |
| Burn | STOP: Rift Bolt (`suspend`); Searing Blaze (`controller-linked damage targets`, `conditional land-entry damage`) |
| Dimir Control | Pass known-gap screen |
| Drain Deck | Pass known-gap screen |
| Midrange | Pass known-gap screen |
| Mono Red Aggro | STOP: same Rift Bolt and Searing Blaze gaps |
| Ramp | Pass known-gap screen |
| Tempo | Pass known-gap screen |
| Tokens | Pass known-gap screen |
| Tribal | Pass known-gap screen |
| White Weenie | Pass known-gap screen |

**The full matrix is not currently runnable under this admission policy.** Nine
lists pass this screen; none is thereby runtime-certified. Coverage flags may
lag implemented features and need separate review/qualification, not bypass.
Rerun on the final measured revision. Do not omit the two stopped decks, swap
cards, or infer that unflagged mechanics work. No execution adapter is added by
these amendments.
