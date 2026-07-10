# MTG Deck Testing Lab Completion Plan

This file describes the current state of the project and the work still required to finish it.
It is written from the codebase as it exists now, not from older patch notes.

## Verified Current Features

The following are implemented and currently supported by the repo:

- React + TypeScript frontend and FastAPI backend.
- Local SQLite persistence with replaceable repository boundaries.
- Deck import from pasted text and file upload.
- Built-in decks and expansion top decks.
- Card cache/sync flow with placeholder image fallback support.
- Rules engine for turn structure, stack, combat, priority, mulligans, mana, state-based actions, and several layered/replacement interactions.
- Targeted and mass artifact/enchantment removal via Oracle inference and reusable effect handlers.
- AI pilot support for human vs AI, AI vs AI, and autoplay diagnostics.
- Batch simulator with deterministic seeding, alternating play/draw order, job progress, first-divergence drilldown, and per-game result output.
- Replay and anomaly tooling for divergence detection and debug runs.
- Training export with hands, actions, and board snapshots.
- Documentation refreshes that reflect the current implementation rather than only patch notes.
- Full backend test suite currently passes.

## Known Remaining Bugs and Gaps

The project is functional, but the following remain open:

- Long-tail Oracle coverage is still incomplete for unusual or older cards.
- Replacement, prevention, and layer handling still rely on heuristics in edge cases.
- Multi-modal, split, transform, and dynamic-value cards still need more robust AI handling.
- Some low-impact X-spells now avoid trivial cast lines, but broader dynamic-value tuning still needs more matchup coverage.
- Matchup balance is still uneven for some builtin deck pairings, especially in long-run batch tests.
- The simulator diagnostics need even clearer root-cause attribution across longer runs.
- Crowded battlefield UI still needs better scaling and scanability for long sessions.
- README, changelog, graph exports, and plan files need to stay synchronized after future changes.

## Step-by-Step Plan To Finish

### 1. Close Rules-Engine Gaps
1. Audit the remaining Oracle and mechanic gaps against real decks that already exist in the repo.
2. Add explicit effect handlers for the most common missing patterns instead of broad fallback behavior.
3. Strengthen replacement, prevention, layer, and continuous-effect ordering where replay drift still appears.
4. Add regression tests for every newly covered mechanic and edge case.
5. Re-run the full backend suite after each rules change.

Exit criteria:
- No core gameplay path depends on silent fallback for a mechanic that already appears in test decks.
- New rules behavior is backed by focused regression tests.

### 2. Improve AI Decision Quality
1. Expand AI evaluation for modal, split, transform, and variable-value spells.
2. Improve mulligan decisions using curve, color access, and matchup context.
3. Strengthen tactical play for control, ramp, tempo, tokens, and attrition board states.
4. Add more deterministic head-to-head regressions so changes can be compared across releases.
5. Use replay and training exports to tune decisions instead of hardcoding special-case logic.

Exit criteria:
- Built-in decks can be piloted credibly without obvious new-player errors.
- Complex board states no longer cause repeated misplays for the same archetype.

### 3. Expand Diagnostics and Regression Coverage
1. Export richer per-game traces for hands, legal moves, chosen actions, board state, and outcomes.
2. Surface first-divergence information more prominently in simulator output.
3. Classify repeated anomalies by turn, action type, and rule category.
4. Keep the long-run replay matrix as the main tool for finding regressions.
5. Use the anomaly output to drive targeted fixes, then re-run the same matrix.

Exit criteria:
- A failed batch can be traced to a specific turn or action quickly.
- Replay drift and anomaly patterns are visible without manual log scraping.

### 4. Tune Balance and Deck Corpora
1. Re-check builtin deck balance using the batch simulator after each meaningful rules or AI change.
2. Keep adjusting existing builtin decks only with evidence from logs and matchup results.
3. Expand the regression matrix to cover the most important archetype pairings already supported by the project.
4. Keep imported card data and deck lists synchronized so tests reflect current oracle data.
5. Avoid inventing cards or deck pieces that are not present in the cached data or deck files.

Exit criteria:
- No builtin deck pairing is winning at an obviously impossible rate in the current simulator.
- Deck balance is supported by replay evidence rather than manual guesswork.

### 5. Finish UI and Release Hardening
1. Improve battlefield scaling so larger boards stay readable.
2. Keep hover zoom and card inspection usable on desktop.
3. Make stack, mana, and priority presentation denser and easier to scan.
4. Keep README, changelog, and plan.md aligned with the implementation.
5. Refresh graph exports and run backend/frontend verification before release checkpoints.

Exit criteria:
- Long-session play remains readable.
- Docs and generated artifacts match the current codebase.

## Execution Order

1. Rules-engine coverage.
2. AI decision quality.
3. Diagnostics and regression coverage.
4. Balance and deck corpora.
5. UI and release hardening.

## Verification Gates

After each phase:

1. Run the relevant backend tests.
2. Run the frontend build when UI files change.
3. Run a representative simulation or replay check when rules or AI change.
4. Refresh graph exports when code structure changes materially.
5. Update README and changelog when user-visible behavior changes.

## Definition of Done

The project is finished when all of the following are true:

- Backend and frontend run successfully.
- Full backend tests pass.
- Main gameplay loops work without obvious broken pages or dead-end states.
- AI can pilot the builtin archetypes credibly across common matchups.
- The simulator can explain failures with useful per-game diagnostics.
- The UI supports long-session deck testing without major readability issues.
- Docs and planning files reflect the real current state of the project.
