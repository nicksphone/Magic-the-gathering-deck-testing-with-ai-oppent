# Resumable Mulligan Declaration Rounds

All callers now use `pregame_actor` to select the next undeclared player in
starting-player order. The engine rejects repeated or out-of-order declarations.
Each round records declarations in durable snapshots; neither mulligan hand is
reshuffled until all remaining participants declare. A player who keeps sits out
later rounds. All participating libraries are shuffled before drawing new hands.

HTTP restoration preserves the current declaration round, RNG state and acting
seat. Older snapshots without the declaration field start a new round among
their unkept players. An already-persisted legacy redraw is not retroactively
undone. The UI explains which player declares next and disables unavailable Keep
actions. SQL stores snapshots only; pregame rules remain application code.

## Rule Boundary

This milestone repairs declaration order and round redraw batching, not all
London mulligan semantics. The existing implementation still chooses ordered
bottom cards on Keep. Current [Comprehensive Rules 103.5](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
describe bottom placement as part of taking a mulligan, before another
declaration round. A durable bottom-choice phase and corresponding AI/UI changes
remain required. Opening-hand effects and mulligan-time abilities under 103.5b
and 103.6 are also not covered by this change.

## Verification (2026-09-30)

1,699 isolated backend tests pass, including starting seats, deferred redraws,
kept-player exclusion, deterministic mid-round snapshots, legacy snapshot defaults
and HTTP/SQLite restore with unchanged state after rejected repeat declarations.
Frontend lint/build/unit checks and the complete Chromium action/recovery/BO3
harness pass. A seat-balanced Aggro/Control/Tempo template replay completes six
logical BO3 series and 15 games without reported timeout, anomaly or drift. This
small replay is not matchup-balance evidence or complete pregame certification.

Local full-suite/browser logs and replay JSON are retained in ignored
`backend/training_runs/mulligan-declarations-20260930/`.

## Known Limitations and Next Upgrades

Complete bottom-selection timing next; do not infer expert mulligan decisions,
opening-hand effect coverage, tournament readiness or matchup balance from these
ordering fixtures. Legacy snapshots cannot recover historical declaration rounds
that the old implementation never stored.
