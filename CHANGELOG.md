# Changelog

This file tracks milestone-level changes. The root README stays focused on the current product state.

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

