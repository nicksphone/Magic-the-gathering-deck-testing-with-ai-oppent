# Bounded Next-Combat Racing

## Implemented Scope

Master/Master Plus small-board blocking evaluates a limited set of surviving
legal block intents against the next public-board combat. The projection uses
real cleanup, untap, combat and death-trigger resolution, while unseen draws
remain opaque. Nested next-combat racing is disabled inside that projection.

At most twelve strongest current-combat intents plus legal no-block receive a
follow-up forecast. A twenty-four-transition bound limits each forecast; the
next attack is restricted to at most three attackers and two available blockers.
An unvisited or unsupported line is unknown, not a proven loss. Budget exhaustion
preserves the ordinary current-combat best choice.

The forecast assumes no intervening spells or other strategic plays. A predicted
board-only lethal is not a guaranteed win against hidden interaction.

## Evidence And Limits

The turn-25 fixture is a public-board reconstruction from the saved match's
later snapshot and log. The original pre-block snapshot and exact historical
block assignments were not retained. Inferred life totals and readiness are
identified in the test; hidden hands and library identities are excluded.

The isolated implementation passes 320 affected regressions, including both-seat
reconstruction, root-state immutability, trigger-based lethal, opaque information,
the thirteen-forecast cap and nonrecursive fallback. Parent integration against
the composed rules batch passed 7,367 affected checks across 192 modules in an
independent source/database copy. Subsequent Cathar and held-deployment deltas
have separately bounded checks; this is not a new full-suite or expert-play claim.

A nonwinning three-attacker/two-blocker microbenchmark has median 3.517 seconds
with racing versus 1.203 seconds without it, over three alternating trials. This
is a measured cost increase, not a whole-game latency estimate or a professional
AI guarantee. Broader decision quality and interactive latency remain open.

Evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/turn25-race-2207/`.
