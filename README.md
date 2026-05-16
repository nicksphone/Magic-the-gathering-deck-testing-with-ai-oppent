# MTG Deck Testing Lab

A professional desktop-first Magic: The Gathering deck testing application focused on rules correctness, repeatable AI testing, and fast iteration.

This project is designed for serious deck validation workflows:
- Human vs AI playtesting
- AI vs AI live match playback
- Batch simulation and diagnostics
- Deck import and archetype testing
- Rules engine-first architecture (database is storage only)

## Core Principles

1. Rules correctness first
2. Stability and deterministic debugging
3. Playability and iteration speed
4. Strong tactical AI with archetype-aware behavior
5. Extensible architecture for future rules/mechanics

## Tech Stack

### Frontend
- React
- TypeScript
- Vite

### Backend
- Python
- FastAPI

### Storage
- SQLite (default local)
- PostgreSQL-ready persistence abstraction (upgrade path)

## Architecture

Gameplay logic is implemented in application code, not SQL.

### Layers
- `backend/card_data`
  - Card sync/cache, fuzzy lookup, image cache hydration
- `backend/rules_engine`
  - Turn structure, priority, stack, combat, targeting, timing, state-based checks
- `backend/effects`
  - Modular effect handlers and resolver registry
- `backend/game_state`
  - Canonical state model and serialization
- `backend/persistence`
  - DB models/repository (storage only)
- `backend/ai`
  - Deck-aware tactical AI and decision policies
- `backend/analytics`
  - Batch simulation, diagnostics, anomaly scanning
- `backend/decks`
  - Deck parser/import, built-ins, expansion top decks, sideboarding
- `frontend/src`
  - Board UI, controls, logs, analytics, testing flow

## Current Feature Set

### Gameplay Engine
- 2-player game state and turn loop
- London mulligan flow
- Manual phase progression and priority passing
- Stack casting/activation + resolution
- Trigger processing with APNAP ordering
- Spell-cast trigger support (`whenever you cast ...` patterns)
- Combat system with attacker/blocker legality
- Correct `can't attack alone` enforcement (with proper distinction from global `can't attack`)
- Menace / multi-block requirements
- Flying/reach and unblockability checks (including landwalk patterns)
- Summoning sickness and tap/untap handling
- Mana payment and color requirement checks
- State-based actions (including death handling and zone replacement hooks)
- Legend rule enforcement
- Draw-from-empty-library loss condition

### Oracle/Effect Interpretation
- Pattern-based oracle interpretation for common effects
- Replacement hooks for key interaction patterns
- Delayed trigger support (including delayed sacrifice marker flows)
- Modular effect handlers for damage, draw, life, counters, tokens, exile, destroy, etc.
- Target legality checks now include protection + `hexproof` + `shroud`

### AI System
- Difficulty levels: `casual`, `strong`, `master`, `master_plus`
- Archetype-aware behavior (aggro/control/ramp/tempo/etc.)
- Mulligan logic by land window + hand quality
- Land-development prioritization safeguards
- Tactical attack/block selection
- Counterspell/interaction hold-up heuristics
- Improved late-game control behavior: deploys major castable threats instead of over-holding interaction
- Limited lookahead and rollout scoring at higher difficulties

### Deck Workflows
- Paste/import deck text
- Upload deck files
- Built-in deck library
- Expansion top-deck catalog import
- Sideboard swap endpoint and between-game BO3 flow

### UI Workflows
- Desktop-first board layout
- Match controls for phase progression and autoplay ticks
- AI-vs-AI autoplay progression
- Priority stop controls
- Between-game sideboard panel
- Match log / stack visibility
- Analytics panel

### Diagnostics / Simulation
- Batch simulation endpoint
- AI diagnostics across deck pool pairs
- Replay endpoint for match logs
- Deterministic start seed support
- Overnight round-robin scripts
- Anomaly clustering report generation
- Stall and land-window anomaly counters in diagnostics

## API Overview

Base backend default: `http://0.0.0.0:8000`

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
- `POST /matches/start`
- `GET /matches/{match_id}`
- `GET /matches/{match_id}/legal-moves`
- `POST /matches/{match_id}/action`
- `POST /matches/{match_id}/autoplay`
- `GET /matches/{match_id}/replay`
- `POST /matches/{match_id}/sideboard`
- `POST /matches/{match_id}/next-game`
- `POST /simulate/batch`
- `POST /ai/diagnostics`
- `GET /analytics/history`

## Setup Instructions

## 1) Clone
```bash
git clone git@github.com:nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent.git
cd Magic-the-gathering-deck-testing-with-ai-oppent
```

## 2) Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 3) Frontend
```bash
cd ../frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 4) Open UI
- `http://<server-ip>:5173`

## Testing

### Backend tests
```bash
cd backend
pytest -q
```

### Frontend build check
```bash
cd frontend
npm run build
```

## Card Data + Image Cache

Card cache and image metadata are stored locally via backend card sync service.
- Card hydration is performed at deck/match workflows.
- Missing cards attempt sync, then fallback metadata when needed.
- Card images are served from backend static mount:
  - `/card-images/...`

## Deck Import Format

Supports deck text like:
```text
4 Lightning Bolt
3 Counterspell
20 Island

Sideboard
2 Negate
2 Dispel
```

Parser behavior:
- Quantity + card name parsing
- Sideboard section parsing
- Validation + suggestions for bad names
- Archetype guess support downstream

## Rules Engine Notes

Rules logic is intentionally isolated from persistence. SQL never decides legality or resolution.

Important implementation behaviors:
- Legal moves are generated from live state
- Action execution mutates state through rules engine only
- Stack/effect resolution is centralized
- Trigger collection and APNAP ordering happen at event boundaries
- State-based checks and win/loss checks run through engine flow

## AI Notes

AI selects actions from legal move sets only.

Key mechanics:
- Archetype-scored move ranking
- Forced land development guardrails during own main phases
- Combat biasing by board state and race pressure
- Defensive stall-loop prevention
- Difficulty-based deeper evaluation (`master`, `master_plus`)

## Simulator + Diagnostics

### Batch simulation
Use `/simulate/batch` for matchup rate sampling.

### AI diagnostics
Use `/ai/diagnostics` for pairwise anomaly scans across decks.
Current anomaly signals include:
- invalid target patterns
- mana/cost failures
- repeated error bursts
- no-legal-move anomalies
- repeated pass-priority stall streaks
- missed land-play window markers

### Overnight verbose runs
Scripts in `backend/scripts` support long-form diagnostics and anomaly clustering output.

## Adding Cards

Preferred path:
1. Import deck or call card sync endpoints.
2. Backend hydrates card metadata from cache/sync.
3. Fallback metadata is used only when live/cached data is unavailable.

For custom local additions, extend fallback payloads in:
- `backend/card_data/fallback_cards.py`

## Adding Decks

Options:
- Import text through API/UI
- Add built-ins in:
  - `backend/decks/builtin_decks.py`
- Add expansion catalog entries in:
  - `backend/decks/expansion_top_decks.py`

## Development Workflow Rules

- If rules/AI/endpoint behavior changes, update this README in the same push.
- Keep gameplay rules in application code only.
- Keep persistence schema and gameplay logic decoupled.

## Roadmap (Priority)

1. Expand comprehensive rules coverage (layers/replacement/legacy mechanics)
2. Deepen oracle interpretation for complex multi-clause text
3. Improve tactical AI for high-skill control/combo lines
4. Add stronger explainability for AI decision rationale
5. Expand sideboard UX and full tournament-style BO3 flows
6. Increase property/regression test coverage for edge interactions
7. Improve large-scale simulator analytics and replay diff tooling
8. Expand historical/top-tier deck library breadth
9. Harden card sync retry/version/invalidation behavior
10. Add stricter benchmark gates for release quality

## Known Limitations and Next Upgrades

Known limitations:
- Full Comprehensive Rules parity is not complete yet.
- Oracle effect interpretation is still pattern-based for many complex cards.
- AI remains heuristic + tactical (not full strategic search/planning engine).
- Matchup tuning is ongoing and still deck-dependent in edge cases.
- Some rare legacy mechanics and old-edition corner interactions are not fully implemented.

Next upgrades:
- Broader rules/mechanics coverage with stronger replacement/layer fidelity.
- Deeper tactical/strategic AI planning under complex board states.
- Larger regression matrix with long-run deterministic replay validation.
- Improved simulator diagnostics and anomaly root-cause attribution.
- Continued UX polish for long-session competitive deck testing.
