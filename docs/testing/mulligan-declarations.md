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

Required ordered bottom choices now occur after each paired redraw and before
another declaration, following [Comprehensive Rules 103.5](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).
The durable choice queue pauses separately for each player in starting-player
order. No casting, priority passes or keep/re-mulligan declarations can interrupt
it. Keep does not bottom cards already selected. Selection is bottom-most first;
this is library placement, not discard, so it does not emit discard triggers.

AI chooses using its hand-retention heuristic; this is not optimal mulligan
strategy. Human choices use the shared selection controls. Autoplay respects the
authoritative actor, and AI-owned pending choices can be stepped without granting
humans control over the AI hand. Counts have runtime response validation.

Old snapshots without completed-bottom metadata retain their unresolved
Keep-time selection. They cannot reconstruct bottom decisions that were never
stored. Opening-hand effects and mulligan-time abilities under 103.5b and 103.6
remain unsupported by this milestone.

## Bottom-Choice Verification (2026-09-30)

1,708 isolated backend tests pass. Fixtures cover both ordered bottom choices,
mid-queue snapshot restore, rejection of declarations while selecting, no double
bottom on Keep, legacy unresolved selection, and seven AI archetype policies.
The live HTTP test takes deliberate bottom selections through seven mulligans to
zero cards. Frontend contracts reject invalid completed-bottom counts.

A seat-balanced Aggro/Control/Tempo template smoke completes six logical BO3
series and 13 games without reported timeout, anomaly or determinism drift.
Small replay results do not establish matchup balance or expert AI. Local test,
browser and replay artifacts are retained in ignored
`backend/training_runs/mulligan-bottom-20260930/`.

Integration checks exposed a missing choice union, AI-owned choice stepping and
seat-1-first frontend autoplay logic. These were corrected; the subsequent build,
contract and browser reruns pass. Browser human BO3 flows exercise the new bottom
selection controls, not just synthetic rendering.

## Declaration Milestone Verification (`7e244ed`, 2026-09-30)

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

Complete opening-hand and mulligan-time effects next; do not infer expert mulligan
decisions, tournament readiness or matchup balance from these fixtures. Broader
legacy migration, hidden-information audits and restart coverage remain open.
