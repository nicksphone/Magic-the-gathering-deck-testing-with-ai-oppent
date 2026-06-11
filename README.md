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
  - Batch simulation, diagnostics, replay summaries, and anomaly analysis
- `backend/persistence`
  - Storage layer only
- `frontend/src`
  - Match UI, deck UI, controls, logs, and simulator views

## Current Status

The application currently supports:
- Rules-aware 2-player testing
- Built-in and custom deck import
- AI-controlled matches in either seat
- Manual and autoplay simulation modes
- Replay and batch diagnostics
- Local-first card caching and image fallback handling

Recent large areas of coverage include:
- modal/split card face selection
- deterministic replay stability
- protection, prevention, and replacement edge cases
- trigger ordering metadata
- ordered continuous-effect layer traces for overlapping static effects
- deck import responses that include resolved cached card metadata for imported lines
- combat and planeswalker damage correctness
- stronger archetype-aware AI behavior

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
- Batch runs are used for matchup analysis and regression checks
- Replay logs are normalized for deterministic comparison
- Verbose logs can be exported into training examples

## Known Limitations

- The rules engine covers a large subset of Magic, but not every Oracle edge case yet
- Some long-tail card interactions still rely on heuristic inference
- Sideboarding and BO3 flow exist, but remain less complete than core one-game testing
- AI quality is strong on common archetypes, but still improves as more replay data and rules coverage are added

## Changelog

Historical milestone notes now live in [CHANGELOG.md](./CHANGELOG.md).
