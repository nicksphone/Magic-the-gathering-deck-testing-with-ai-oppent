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
- Replay logs, batch simulations, matchup stats, anomaly diagnostics, first-divergence replay drilldown, turn-level AI trace summaries, first-game log excerpts, per-game batch results, and training trace export with board snapshots
- BO3 and sideboarding support with per-game swap locking
- denser match-status and between-games controls for BO3 sessions
- Fuzzy card-name correction for deck import and cached metadata resolution for imported lines
- AI seat control with archetype detection, mulligan logic, curve evaluation, interaction heuristics, and keyword-aware battlefield evaluation for tougher removal decisions

Recent large areas of coverage include:
- modal/split card face selection
- deterministic replay stability
- protection, prevention, and replacement edge cases
- broader death-replacement phrase coverage for common Oracle variants
- targeted and mass artifact/enchantment removal coverage
- trigger ordering metadata
- ordered continuous-effect layer traces for overlapping static effects
- explicit no-op fallback for unresolved Oracle text
- batch first-divergence output surfaced in the simulator results panel
- low-impact X-spell selection is skipped instead of forcing trivial cast lines
- deck import responses that include resolved cached card metadata for imported lines
- sideboard flow now locks to one swap pass per finished game and resets on `next-game`
- multi-match library search resolution and stale damage-counter cleanup on destroy
- explicit regression coverage for postcombat main, end step, cleanup, and next-turn advancement
- combat and planeswalker damage correctness
- stronger archetype-aware AI behavior with threat-weighted removal timing and richer battlefield scoring

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
- AI performance is strong on common archetypes, but still needs more training data and deeper tactical planning on complex board states
- Simulator diagnostics now include first-divergence replay comparison helpers, turn-level AI trace summaries, first-game log excerpts, deterministic per-game batch results, live simulator status/progress display, and result-panel divergence output, but the long-run root-cause workflow still needs more automated annotation and root-cause classification
- Built-in deck balance is still being tuned; deterministic batch runs are the primary audit tool for outlier matchups
- UI is functional, but several competitive-play polish items remain before it feels complete for long sessions

## Changelog

Historical milestone notes now live in [CHANGELOG.md](./CHANGELOG.md).
