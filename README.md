# MTG Deck Testing Lab

Professional desktop-first web application for serious Magic: The Gathering deck testing.

This project delivers a modular 2-player simulator with:
- Player vs AI
- AI pilot mode for either deck
- AI vs AI testing mode
- Deck import from text
- Built-in master archetype decks
- Manual priority/phase progression controls
- Batch simulation analytics

## Project Structure

```text
mtg-deck-testing-lab/
  backend/
    main.py
    requirements.txt
    card_data/
    rules_engine/
    effects/
    game_state/
    ai/
    decks/
    analytics/
    persistence/
    tests/
  frontend/
    src/
    package.json
```

## Architecture Overview

Rules and gameplay logic are implemented in application code, never in SQL.

### Layer Map

1. Card Data Layer (`backend/card_data`)
- Scryfall sync service
- local card cache reads
- fuzzy name correction support

2. Rules Engine (`backend/rules_engine`)
- turn structure and step progression
- priority passing
- stack management
- legal move generation
- combat and state-based actions

3. Effect Resolution Layer (`backend/effects`)
- reusable modular effect handlers
- registry-based effect dispatch
- handlers for damage, draw, life, destroy, counter, exile, token creation, mana, counters, sacrifice, tap/untap, buffs, keyword grant

4. Game State Layer (`backend/game_state`)
- normalized state objects
- zones, cards, players, turn metadata
- serialization for API/UI

5. Persistence Layer (`backend/persistence`)
- SQLModel storage for cached cards, decks, matches, snapshots
- replaceable DB boundary via repository abstraction

6. AI Layer (`backend/ai`)
- archetype detection
- heuristic board evaluation
- difficulty levels: Casual / Strong / Master
- decision policy across legal moves

7. UI Layer (`frontend/src`)
- desktop-first battlefield layout
- deck import panel
- controls for phases/priority/autoplay
- stack + match log
- structured target allocation UI for divide-damage spells
- testing simulator analytics panel

## Setup Instructions

## 1) Backend

```bash
cd /home/nick/mtg-deck-testing-lab/backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn main:app --reload --port 8000
```

## 2) Frontend

```bash
cd /home/nick/mtg-deck-testing-lab/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## 3) Tests

```bash
cd /home/nick/mtg-deck-testing-lab/backend
.venv/bin/python -m pytest -q
```

## How the Rules Engine Works

- Match creation expands decklists into card instances and initializes zones.
- Turn order follows explicit MTG step sequencing:
  - Untap, Upkeep, Draw
  - Precombat Main
  - Beginning of Combat, Declare Attackers, Declare Blockers, Combat Damage, End Combat
  - Postcombat Main
  - End Step, Cleanup
- Priority is tracked per player; stack resolution occurs after both pass.
- Per-player priority stops are configurable by step and exposed in match controls.
- Spells/abilities are pushed as stack items and resolved via effect handlers.
- Spell effect selection is oracle-text-driven first, with fallback heuristics for uncached/unknown text.
- Oracle effect inference now parses multi-clause text into executable effect sequences (damage/draw/life/tap/counters/discard/token/mana patterns), including token count + keyword extraction.
- Configurable best-of flow (odd values, default 3) supports between-game sideboarding and explicit `next-game` transitions.
- London mulligan flow is implemented as pregame `mulligan`/`keep_hand` actions.
- Non-instant timing now respects active-player main-phase + empty-stack constraints.
- Combat validates legal attackers/blockers, then applies combat damage.
- Combat now supports multi-block assignment, first/double strike step handling, and trample spillover.
- Trigger event bus now pushes triggered abilities in APNAP order.
- State-based actions run after actions/resolution and enforce loss/death checks.

## How the AI Works

- Deck archetype is inferred from card-name signatures.
- AI policy changes by inferred archetype (Burn, Control, Tempo, etc.).
- AI scores legal moves using:
  - board evaluation (life delta, card advantage, creature power)
  - archetype-aware weighting (burn priority, counterspell timing preference, etc.)
- Master AI adds short-horizon tactical lookahead (own move + opponent best reply) to avoid obvious punts.
- Difficulty:
  - Casual: weaker action pick
  - Strong: top heuristic move
  - Master: top heuristic move with full priority/autoplay loops

## Card Data Sync and Cache

- `POST /cards/sync?name=<card>` pulls card data from Scryfall and stores local cache.
- Cache stores oracle-like fields, mana cost, types, stats, colors, legalities, image URI metadata.
- Deck parser uses fuzzy lookup against cached names for typo recovery.

## Deck Import and Built-in Decks

- Built-in master archetypes are available via `/decks/builtin`.
- User decks can be imported by text format:

```text
4 Lightning Bolt
3 Counterspell
20 Island
```

- Parser validates line format, mainboard size (60+), and produces suggestions for unknown names.

## API Summary

- `GET /health`
- `POST /cards/sync`
- `POST /cards/sync-bulk`
- `GET /cards`
- `GET /cards/suggest`
- `GET /decks/builtin`
- `GET /decks/builtin/{name}`
- `POST /decks/import`
- `POST /decks/import-file`
- `GET /decks`
- `POST /matches/start`
- `GET /matches/{match_id}`
- `GET /matches/{match_id}/legal-moves`
- `POST /matches/{match_id}/action`
- `POST /matches/{match_id}/autoplay`
- `POST /matches/{match_id}/sideboard`
- `POST /matches/{match_id}/next-game`
- `POST /matches/{match_id}/priority-stops`
- `POST /simulate/batch`
- `GET /analytics/history`

## How to Add Cards

1. Sync with Scryfall:
```bash
curl -X POST "http://127.0.0.1:8000/cards/sync?name=Lightning%20Bolt"
```

2. Card enters local cache table (`CardCache`) and becomes available for fuzzy deck validation.

3. To expand card behavior, add or update rules/effect mapping in:
- `backend/rules_engine/engine.py`
- `backend/rules_engine/oracle_effects.py`
- `backend/rules_engine/mana.py`
- `backend/rules_engine/cast_choice.py`
- `backend/rules_engine/hooks.py`
- `backend/rules_engine/events.py`
- `backend/rules_engine/costs.py`
- `backend/rules_engine/targeting.py`
- `backend/effects/registry.py`
- `backend/effects/handlers.py`

## How to Add Decks

1. Use UI deck import panel or call `POST /decks/import`.
2. To add new built-ins, update `backend/decks/builtin_decks.py`.
3. Saved decks are persisted in `DeckRecord` and available in match controls.

## Future Roadmap

- deeper oracle interpretation (remaining CR edge cases, layered continuous effects, complex replacement timing)
- richer targeting UX for complex multi-target cards (current divide/selection UX implemented)
- broader planeswalker and token rule automation
- true mulligan decision simulation and opening hand quality model
- MCTS / rollout AI for master-level tactical depth
- PostgreSQL production profile and migration tooling
- card image prefetch/cache worker and search indexing
- multiplayer-ready engine abstractions

## Known Limitations and Next Upgrades

- Current engine is rules-aware but not full comprehensive MTG CR coverage.
- Oracle-text inference now supports clause sequencing and more patterns, but is still not full CR-complete parsing.
- Replacement effects, layered continuous effects, and many triggered interactions are scaffolded but not exhaustive.
- Sideboarding is implemented between games; UI support for interactive swap builders is still minimal.
- AI is strong heuristic-based, not exhaustive game-tree search.
- Next upgrades should prioritize CR-level corner-case coverage, richer target-choice UX, and deeper search-based AI.

## Recent Improvements (2026-04-24)

- Configurable match length: best-of is now selectable (odd values), end-to-end API/UI support.
- Oracle effect interpretation expanded:
  - clause-based sequencing across multi-sentence effects
  - broader effect parsing for discard, counters, tap/untap, mana-symbol adds, and targeted life effects
- Effect resolution enhancements:
  - sequence execution (`effect_sequence`)
  - targeted draw/gain/lose life behavior
- Tactical AI improvements:
  - master two-ply lookahead (action + opponent best reply)
  - improved counterspell timing, attack pressure, and pass-priority posture logic
  - stronger board evaluation features (toughness/untapped/mana pressure)
- Expanded backend interaction tests covering oracle sequencing, discard targeting, and AI tactical choices.
- Advanced priority-stop system:
  - per-player stop configuration by step (`/matches/{id}/priority-stops`)
  - autoplay now pauses when configured stop windows have meaningful human decisions
- Richer targeting UX:
  - divide-damage targeting now uses structured per-target numeric allocation instead of raw JSON input
- Broader token automation:
  - oracle parsing now extracts token count + combat keywords for token creation clauses
  - token handler now supports multi-token creation with attached keywords
- Backend test environment verified in project venv: `33 passed`.

## Documentation Rule

- Any new feature, rule-system change, AI behavior change, or API contract change must be reflected in this README in the same push.
