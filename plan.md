# MTG Deck Testing Lab Plan

This file tracks the remaining work needed to finish the project from the current codebase state.
It is ordered by dependency and user-visible impact.

## Current State

Completed and verified:
- Backend and frontend both build and run.
- Full backend test suite passes.
- Batch simulator now exposes live status, progress, errors, first-game turn summaries, and a short log excerpt in the UI.
- Batch runs are deterministically seeded per matchup and game, and include per-game result summaries.
- Replay tooling can compare logs and classify the first divergence.
- AI heuristic evaluation is stronger for battlefield state and removal timing.
- Custom deck analysis uses card metadata and curve shape instead of only name matching.
- Training export includes board snapshots in addition to hands and actions.
- Documentation has been updated to reflect the current code rather than only patch notes.

## Remaining Work

### 1. Expand Rules-Engine Coverage
1. Close long-tail Oracle and mechanic gaps for older and unusual cards.
2. Harden replacement, prevention, and layer handling where heuristics still remain.
3. Add more regression tests for triggered abilities, continuous effects, and board-state corner cases.
4. Keep the rules engine as the single source of truth for gameplay logic.

Acceptance:
- Core gameplay paths do not depend on silent fallback behavior.
- Every new mechanic ships with a regression test.

### 2. Deepen AI Decision Quality
1. Improve modal, split, transform, and dynamic-value card handling.
2. Expand strategic planning for control, combo, ramp, and attrition board states.
3. Strengthen mulligan evaluation using matchup and curve context.
4. Add more deterministic regression matches for built-in deck pairings.
5. Keep tuning based on replay and training data instead of manual special-casing.

Acceptance:
- The AI can pilot built-in archetypes credibly without obvious new-player mistakes.

### 3. Broaden Training and Diagnostics
1. Export richer traces for hands, legal moves, chosen actions, board snapshots, and outcomes.
2. Capture divergence labels and anomaly classes for replay review.
3. Add longer-running matchup diagnostics with first-divergence drilldown surfaced more prominently.
4. Extend anomaly annotation beyond the first-game snapshot so batch issues are easier to localize.

Acceptance:
- Simulation problems can be traced to a specific turn, action, or rule decision quickly.

### 4. Polish Competitive UI
1. Improve battlefield scaling so crowded boards stay readable.
2. Keep hand hover zoom and card inspection usable on desktop.
3. Denser stack, mana, and priority presentation for faster scanning.
4. Make pass/hold/response windows clearer during decision points.

Acceptance:
- Long games remain readable without cards disappearing into the layout.

### 5. Finish Release Hardening
1. Keep README, changelog, and plan current after each milestone.
2. Keep graph exports current so the codebase stays inspectable.
3. Run backend and frontend verification before each release candidate.
4. Trim stale bug notes once tests and runtime behavior prove they are closed.

Acceptance:
- The repository has a current-state README, a live plan, and green verification.

## Suggested Execution Order
1. Rules-engine coverage.
2. AI decision quality.
3. Training and diagnostics.
4. Competitive UI polish.
5. Release hardening.

## Definition of Done
- Backend and frontend run successfully.
- Full backend tests pass.
- Main gameplay loops work without obvious broken pages or dead-end states.
- AI can pilot built-in archetypes credibly across common matchups.
- The UI supports long-session deck testing without major readability issues.
- Docs and planning files reflect the real current state.
