# Changelog

This file tracks milestone-level changes. The root README stays focused on the current product state.

## 2026-07-10

- Rules coverage:
  - Added generic Oracle inference and handlers for targeted and mass artifact/enchantment removal.
  - The new coverage includes `destroy target artifact or enchantment` style cards and `destroy all artifacts and enchantments` sweepers.
  - Creature death replacement now applies consistently through destroy, sacrifice, combat cleanup, and state-based actions.
  - Death replacement now also matches common `nontoken` and `another creature` Oracle variants instead of only one phrasing.
  - Death-trigger collection now respects controller-scoped clauses such as `a creature you control dies`.
  - Additional-cost sacrifice now also respects exile-instead-of-dying replacement effects.
- Simulator diagnostics:
  - Batch simulation now records the first divergence between the first two games in a matchup.
  - The Testing Simulator UI now surfaces that first-divergence report directly in the results panel.
- AI X-spell policy:
  - Low-impact X-spells now require a meaningful minimum X instead of being forced at trivial values.
  - Token-producing X-spells such as `Secure the Wastes` are skipped early when they would only produce an insignificant board state.
- AI control pacing:
  - Control, Counter-heavy, and Tempo agents now distinguish urgent interaction from stable value turns so they do not over-pass into draw-spell lines.
  - Stable main phases can now prefer castable value spells over idle hold-up when no real response is needed.
- AI face selection:
  - Modal and transform-style face selection now scores the actual face `type_line`, which improves role-sensitive choice on split/DFC-style cards.
  - AI valuation now better separates creature, instant, and value faces when the board state changes.
- Diagnostics classification:
  - Replay divergence now classifies common root causes such as pass-vs-action, land-drop mismatch, cast-choice mismatch, and cast-resolution error.
  - Anomaly clustering now recognizes land-drop misses correctly instead of relying on a broken regex pattern.
- UI battlefield scaling:
  - Crowded battlefield rows now shrink density-aware card and land render sizes so large boards stay readable.
  - Hover preview remains available for closer card inspection when the board is compressed.
- UI density polish:
  - The stack log and priority-stop controls now use more compact layouts for long-session scanning.
- Regression coverage:
  - Added backend tests for the batch first-divergence report and the stricter X-spell selection floor.
  - Added regression coverage for control choosing a value draw spell over idle pass priority in a stable main phase.
  - Added regression coverage for replay classification and anomaly clustering buckets.
  - Added regression coverage for modal face scoring that reacts to face type lines and board state.

## 2026-07-09

- Sideboarding flow hardening:
  - Match controllers now track whether a player has already sideboarded for the current finished game.
  - The `/matches/{match_id}/sideboard` endpoint now rejects repeated sideboard applications before the next game starts.
  - The next-game transition clears the per-game sideboard lock so BO3 flow remains consistent across games.
- Test coverage:
  - Added regression coverage for the single-sideboard-per-game contract and the reset that happens on `next-game`.
- Search and cleanup polish:
  - Library search effects now collect all matching cards instead of stopping at the first hit.
  - Destroyed permanents clear stale damage and prevention counters before moving to the graveyard.
- Phase/progress correctness:
  - Turn progression regression coverage now explicitly exercises postcombat main, end step, cleanup, and the next untap.
  - `_deal_unblocked_damage()` now has a consistent integer return type contract.
- Oracle fallback cleanup:
  - Unresolved Oracle text now maps to an explicit `noop` effect instead of pretending to be life gain.
- BO3 UI polish:
  - The match controls panel now shows score, game number, match target, and sideboard availability in a denser status grid.
  - The between-games panel now says explicitly whether sideboarding is open or the match is already complete.
- Replay diagnostics:
  - Replay comparison logic now lives in reusable analytics helpers.
  - Diagnostics can report the first diverging log line and classify whether the mismatch is an action mismatch or a broader replay drift.
  - AI diagnostics now emit turn-level trace summaries with board snapshots for the first game in each matchup.
- Batch determinism:
  - Batch simulation now seeds each game deterministically from the matchup and game index.
  - Batch responses now include per-game results with seeds, winners, turn counts, and timeout flags.
- Rules coverage:
  - Generic destroy-all-creatures resolution now exists for Oracle text that says to wipe the board.
  - The resolver path is covered by regression tests using a real sweep effect.
- Simulator UI polish:
  - The Testing Simulator now shows per-game batch results in addition to the first-game excerpt and aggregate stats.
- AI tactical evaluation:
  - Battlefield scoring is now keyword-aware and values evasive or protected threats more accurately.
  - Control removal decisions now weigh target threat level instead of treating all removal targets equally.
- Training export enrichment:
  - Structured training rows now include board snapshots derived from AI trace logs.
- Simulator UI polish:
  - The Testing Simulator now shows live job status, a progress bar, failure output, and compact first-game turn/log summaries while batch jobs run.
- Custom deck analysis:
  - Archetype classification now uses cached card metadata and curve shape when available, not just deck-name keywords.

## 2026-06-11

- Continuous-effect diagnostics:
  - Layer traces now expose ordered applied layer entries for overlapping static effects.
  - Combined power/toughness plus keyword clauses are parsed as a single static effect instead of dropping the keyword half.
- Deck metadata completeness:
  - Deck import responses now include resolved cached card metadata for mainboard and sideboard lines when available.
  - This exposes face data, image URIs, oracle text, and legality metadata alongside the parsed deck list.

## 2026-06-07

- Combat protection and prevention fixes:
  - Trample spillover into protected planeswalkers now respects protection.
  - Combat damage now respects `damage can't be prevented` before consuming prevention shields.
  - Regression coverage added for both cases.
- Rules/AI groundwork:
  - Modal/split face selection is preserved through cast resolution and AI valuation.
  - Replay determinism remains stable on the current regression matrix.
  - Trigger ordering metadata, replacement traces, and continuous-effect traces are available for diagnostics and training export.

## 2026-06-06

- Combat flow fixes:
  - Blocker declaration hands priority back to the active player after assignment.
  - The block-declaration window is single-use per combat step to prevent repeated blocker prompts.
  - A Tempo vs Drain timeout loop was eliminated by the combat window fix.

## 2026-05-18

- AI and diagnostics milestones:
  - Added stack-only 2-ply tactical search for complex counter windows.
  - Added inevitability-driven control endgame policy.
  - Improved threat scoring for artifacts, enchantments, and planeswalkers.
  - Added deterministic replay drift labeling and first-divergence reporting.
  - Added structured training trace export from verbose head-to-head logs.

## 2026-05-17

- Core AI stability improvements:
  - Fixed land-play legality leaks in the AI action selector.
  - Added priority-pass logging for deeper debugging.
  - Improved control matchup behavior and built-in deck color correctness.

## 2026-05-16

- Early infrastructure and matchup improvements:
  - Better deck deduplication in `/decks`.
  - Expanded fallback metadata for control/removal package cards.
  - Land tapping logic improved for dual/multi-color lands.
  - Added matchup profile scaffolding and endgame policy hooks.
