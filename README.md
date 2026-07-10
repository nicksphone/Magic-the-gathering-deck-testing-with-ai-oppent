# MTG Deck Testing Lab

A professional desktop-first Magic: The Gathering deck testing application for rules-aware playtesting, AI-vs-AI validation, and long-run deck analysis.

The project is built for serious deck work:
- Human vs AI playtesting
- AI vs AI simulation
- Batch matchup analysis
- Custom deck import and deck library management
- Rules-engine-first gameplay logic

## What It Does

### Gameplay
- 2-player match flow with turn structure, priority, stack, combat, and cleanup
- London mulligan handling
- Manual phase advancement and autoplay
- Land drops, casting, activated abilities, and combat actions
- Damage, prevention, protection, replacement effects, and trigger resolution
- Death replacement now applies consistently across destroy, sacrifice, combat cleanup, and state-based actions
- Death replacement now also understands common `nontoken` and `another creature` Oracle variants
- Death triggers now respect controller clauses like "a creature you control dies"
- Additional-cost sacrifice replacement now respects exile-instead-of-dying effects
- Planeswalker loyalty parsing now supports `-X` and `+X` style abilities with X-value propagation through AI and resolution
- Planeswalker combat targeting
- Loss conditions for life and decking

### Card Data
- Local card cache synced from live card data
- Oracle text, mana cost, type line, colors, rulings, legalities, and image metadata
- Double-faced, split, modal, and token-aware card handling
- Fuzzy matching for deck import correction

### AI
- Deck-aware AI with archetype detection
- Difficulty levels: `casual`, `strong`, `master`, `master_plus`
- Mulligan and curve evaluation
- Interaction timing, threat assessment, combat math, and counterspell selection
- Modal/split card face selection based on board state and game stage

### Simulation and Diagnostics
- AI vs AI autoplay
- Batch simulation
- Replay inspection
- Deterministic regression checks
- Match logs, anomaly output, and training trace export
- Anomaly clustering now recognizes multi-word land-drop misses and repeated main-phase pass loops from AI trace data

## Architecture

Gameplay logic lives in application code. SQL is for storage only.

### Backend Layers
- `backend/card_data`
  - Card sync/cache, image cache hydration, fuzzy lookup
- `backend/rules_engine`
  - Turn structure, priority, stack, combat, targeting, timing, state-based checks, and rules inference
- `backend/effects`
  - Modular effect handlers and resolver registry
- `backend/game_state`
  - Canonical state model and serialization
- `backend/ai`
  - Tactical AI, archetype detection, matchup policies, and endgame behavior
- `backend/decks`
  - Deck parser/import, built-ins, expansion decks, sideboarding support
- `backend/analytics`
  - Batch simulation, diagnostics, replay summaries, replay comparison drilldown, and anomaly analysis
- `backend/persistence`
  - Storage layer only
- `frontend/src`
  - Match UI, deck UI, controls, logs, and simulator views

## Current Status

The application currently supports:
- Rules-aware 2-player testing with turn structure, priority, stack, combat, cleanup, and turn advancement
- Human vs AI, AI vs human, and AI vs AI matches
- Manual phase progression and autoplay-driven simulation
- Built-in deck imports, expansion deck imports, file/text deck import, and deck saving
- Local card caching with image fallback handling and token art resolution when available
- Partial cache rows are merged with fallback metadata so common cards do not lose oracle text or type data
- Imported deck analysis now folds `card_faces` into archetype scoring so split and modal cards are classified by their actual text and type data
- Replay logs, batch simulations, matchup stats, anomaly diagnostics, first-divergence replay drilldown, turn-level AI trace summaries, first-game log excerpts, per-game batch results, and training trace export with board snapshots
- Training exports preserve active-player and priority-player context for later AI analysis
- Verbose AI traces now include active-player and priority-player context for easier replay analysis
- Card-play analytics that separate strategic main-phase pass windows from combat-step passes in verbose head-to-head logs
- Replay divergence classification now distinguishes pass-vs-action, land-drop mismatch, cast-choice mismatch, and cast-resolution error cases
- BO3 and sideboarding support with per-game swap locking
- denser match-status and between-games controls for BO3 sessions
- density-aware battlefield scaling keeps crowded boards readable while preserving hover inspection
- compact stack, priority, and mana-pool displays make long-session response windows easier to scan
- Fuzzy card-name correction for deck import and cached metadata resolution for imported lines
- AI seat control with archetype detection, mulligan logic, curve evaluation, interaction heuristics, and keyword-aware battlefield evaluation for tougher removal decisions
- Control AI now distinguishes urgent interaction from stable-value turns so it does not over-pass into draw spell lines
- Modal and transform-style face selection now uses the face type line, not just the parent card type, for more accurate AI valuation
- Loyalty abilities with X costs now flow through move generation and AI materialization instead of being dropped as malformed activations

Current focus:
- expanding Oracle coverage for older and unusual cards
- improving replacement, prevention, and layer fidelity in edge cases
- deepening tactical AI for complex board states and matchup-specific heuristics
- tightening simulator diagnostics and replay attribution when a run diverges
- keeping the UI dense and readable during long sessions

## Setup

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9999 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### Open the App
- Frontend: `http://<server-ip>:5173`
- Backend: `http://<server-ip>:9999`

## Testing

### Backend
```bash
cd backend
pytest -q
```

### Frontend
```bash
cd frontend
npm run build
```

## API Overview

Base backend default: `http://0.0.0.0:9999`

Key endpoints:
- `GET /health`
- `GET /cards`
- `POST /cards/sync`
- `POST /cards/sync-bulk`
- `GET /decks`
- `POST /decks/import`
- `POST /decks/import-file`
- `GET /decks/builtin`
- `GET /decks/expansion-top`
- `POST /decks/analyze`
- `POST /matches/start`
- `GET /matches/{match_id}`
- `GET /matches/{match_id}/legal-moves`
- `POST /matches/{match_id}/action`
- `POST /matches/{match_id}/autoplay`
- `GET /matches/{match_id}/replay`
- `POST /matches/{match_id}/sideboard`
- `POST /matches/{match_id}/next-game`
- `POST /simulate/batch`
- `POST /simulate/batch/start`
- `GET /simulate/batch/{job_id}`
- `POST /ai/diagnostics`
- `GET /ai/priors`
- `POST /ai/priors/rebuild`
- `GET /analytics/history`

## Deck Import

Supported text format:
```text
4 Lightning Bolt
3 Counterspell
20 Island

Sideboard
2 Negate
2 Dispel
```

Import sources:
- Paste deck text
- Upload a `.txt` deck file
- Choose built-in decks
- Choose expansion decks

## Card Data and Images

The app syncs and caches card data locally.
- Card metadata is stored for repeatable testing
- Missing card art falls back to local placeholder handling
- Token art is resolved when available
- Split/modal face metadata is preserved for UI and AI use

## Simulation Notes

- AI vs AI autoplay can be stepped or run continuously
- Batch runs are used for matchup analysis and regression checks, with deterministic per-game seeding, alternating play/draw order, and per-game result summaries for repeatable comparisons
- Replay logs are normalized for deterministic comparison
- Verbose logs can be exported into training examples with board snapshots and per-turn action summaries
- The Testing Simulator panel shows live job status, progress, failure output, and compact first-game turn/log summaries while batch jobs run

## Known Limitations

- The rules engine still does not cover every Oracle edge case or every older/obscure mechanic
- Some static/replacement/layer interactions still rely on heuristic inference rather than full Oracle-parity modeling
- Sideboarding exists, but the BO3 user experience is still lighter than the core one-game testing loop
- AI performance is strong on common archetypes, but still needs more training data and deeper tactical planning on complex board states; face-selection heuristics for modal/transform cards are improved, but broader matchup tuning still remains
- Simulator diagnostics now include first-divergence replay comparison helpers, turn-level AI trace summaries, first-game log excerpts, deterministic per-game batch results, live simulator status/progress display, and result-panel divergence output, but the long-run root-cause workflow still needs more automated annotation and root-cause classification
- Verbose trace payloads now carry active-player and priority-player context so later drilldowns can distinguish turn-owner decisions from stack-response decisions
- Card-play analytics now distinguish strategic main-phase pass windows from combat-step passes so the logs do not over-report harmless blockers windows as stalls
- Simulator diagnostics now classify common divergence buckets such as pass-vs-action, land-drop mismatch, cast-choice mismatch, and cast-resolution error, and anomaly clustering now detects land-drop misses correctly
- Built-in deck balance is still being tuned; deterministic batch runs are the primary audit tool for outlier matchups
- UI is functional, but several competitive-play polish items remain before it feels complete for long sessions; battlefield density, stack density, mana pooling, and priority visibility are improved, but there is still room for further refinement

## Changelog

Historical milestone notes now live in [CHANGELOG.md](./CHANGELOG.md).
