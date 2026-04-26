# MTG Deck Testing Lab

Professional desktop-first Magic: The Gathering deck testing platform with a rules-aware game engine, AI pilots, and matchup diagnostics.

## Current Status (April 26, 2026)

### Working now
- 2-player MTG simulation with explicit turn/step progression
- Player vs AI, AI vs AI, and AI pilot controls
- Deck import from text + built-in archetype decks
- Stack, priority passing, legal move generation, combat flow
- State-based actions including legend rule and loyalty checks
- Oracle-text-driven effect inference (partial but functional)
- Card cache + image metadata via Scryfall sync
- Batch simulation + AI diagnostics endpoints
- Extensive backend test coverage for core logic paths

### Recently stabilized
- AI land-drop reliability and color-source preference
- AI step-enum normalization fixed (`Step.PRECOMBAT_MAIN` etc.), preventing missed forced land-drop windows in live games
- Backend autoplay now hard-enforces AI land drops on legal own-main windows (fallback to a legal `play_land` action even if AI returns pass)
- Backend autoplay now hard-overrides any non-land AI action during legal own-main land windows, ensuring land drop occurs first when available
- Additional fallback: if legal move generation ever omits `play_land`, autoplay derives land options directly from hand card identity and still forces land play
- AI core policy now includes the same synthesized land fallback, so forced land development also applies in non-autoplay code paths (batch simulations/diagnostics and direct AI action loops)
- Land heuristics now avoid false positives on mana creatures (e.g., `Llanowar Elves` style `{T}: Add ...` cards are no longer eligible for `play_land`)
- Added turn-level land-play invariant (`last_land_play_turn`) in engine and move generation to prevent any double-land same-turn bug even if counters desync
- Refined land-play invariant to be rules-compatible with future “play an additional land” effects via per-turn `max_land_plays_this_turn` while still blocking accidental double-land bugs
- Added dynamic additional-land-play parsing from battlefield oracle text (e.g., “play an additional land”, “play two additional lands”) to drive legal move generation and engine enforcement
- Combat keyword fidelity expanded:
  - `lifelink` life gain on combat damage
  - `deathtouch` lethal assignment/kill semantics (including trample interaction)
  - `double strike` damage in both first-strike and regular combat-damage steps
  - combat damage is now marked and removed at cleanup (instead of permanently reducing toughness)
  - blocker legality now enforces `flying`/`reach` and `menace` constraints
- Expanded trigger timing windows:
  - beginning-of-upkeep and beginning-of-end-step triggers are now emitted at step start
  - APNAP ordering is applied to simultaneous step triggers
  - “your upkeep/end step” vs “each upkeep/end step” oracle distinctions are enforced
- Added first continuous-effect stat layer support:
  - static anthem text (`creatures you control get +1/+1`, `other creatures you control get +1/+1`) now affects effective power/toughness in combat and lethal SBA checks
- Added first prevention/replacement-like damage shield support:
  - `prevent the next N damage` parsing for target player/creature
  - prevention shields are consumed by both spell damage and combat damage
  - non-combat spell damage to creatures now marks damage (CR-consistent), rather than permanently reducing toughness
- Added additional combat keyword correctness:
  - `vigilance` attackers no longer tap when declared
  - `defender` creatures cannot be declared as attackers
- Added legacy mechanics coverage:
  - `landwalk` unblockability checks against defending player land types (`islandwalk`, `swampwalk`, `mountainwalk`, `forestwalk`, `plainswalk`)
  - `protection from <color>` now affects block legality, target legality, and damage prevention from matching-color sources
  - “can’t be blocked except by two or more creatures” oracle wording is enforced as menace-equivalent blocking constraint
  - source-color propagation now carries through multi-clause `effect_sequence` resolution so protection checks remain consistent for composite spells
- Expanded static/continuous effect coverage for enchantments/artifacts and similar permanents:
  - generic parsing of battlefield static text for `get +/-X +/-Y` and `have <keyword>` clauses
  - supports `you control` and `your opponents control` scopes
  - supports `other creatures`, `creature tokens`, `artifact creatures`, and tribal creature groups (e.g., Elves)
  - static keyword grants now flow into combat legality and outcomes (e.g., global `reach`, `indestructible`)
  - static keyword grants now flow into targeting/protection validation and creature mana-tap legality (`haste` from static effects)
  - lethal SBA and combat death checks now respect static `indestructible`
- Land recognition is now resilient to partial card metadata:
  - land detection also keys off oracle mana-ability text (`{T}: Add ...`) when type metadata is missing
  - prevents nonbasic lands from being misclassified and skipped in AI land-drop windows
- Nonland mana-permanent payment support added (e.g., `Llanowar Elves`, mana rocks), including summoning-sickness tap restrictions for creature `{T}` mana abilities
- Combat decision heuristics tightened:
  - attack action now selects an attacker subset (avoids many low-value/suicidal 1/1 attacks into larger blockers)
  - blocking logic prioritizes damage prevention and better trade selection in defender role
- Topdeck creature-deployment effects (Collected Company-style) now resolve generically:
  - infer from oracle text pattern (`look at top N`, `put up to X creature cards with mana value Y or less onto battlefield`)
  - AI now values this spell class appropriately in creature-centric archetypes
- Land can no longer be cast as spell regression fixed
- Memory Deluge / X-target validation loop fixes
- Tokens AI now casts key enchantments more consistently
- Combat execution now includes meaningful combat deaths/trades in tested matchups
- AI blockers loop guard prevents endless empty `block` actions

## Project Structure

```text
mtg-deck-testing-lab/
  backend/
    ai/
    analytics/
    card_data/
    decks/
    effects/
    game_state/
    persistence/
    rules_engine/
    scripts/
    tests/
    main.py
  frontend/
    src/
```

## Architecture Overview

Rules live in application code, not SQL.

### Layer Map
1. Card Data Layer (`backend/card_data`)
- Scryfall sync/cache
- fuzzy card lookup
- local metadata/image references

2. Rules Engine (`backend/rules_engine`)
- turn/step flow
- priority windows
- legal move generation
- stack and resolution hooks
- combat and state-based actions

3. Effect Resolution Layer (`backend/effects` + oracle parsing)
- reusable effect handlers
- oracle-text pattern interpretation for common effects

4. Game State Layer (`backend/game_state`)
- zones, cards, players, match state
- serialization for API/UI

5. Persistence Layer (`backend/persistence`)
- SQLModel + SQLite storage for decks/cards/history
- DB boundary is separated from gameplay logic

6. AI Layer (`backend/ai`)
- archetype-aware decision policy
- difficulty modes (`casual`, `strong`, `master`, `master_plus`)
- tactical scoring + limited lookahead/rollout behavior

7. UI Layer (`frontend/src`)
- battlefield + hand + stack + controls + logs
- autoplay controls and pacing
- desktop-first layout

## Setup

### Backend
```bash
cd /home/nick/mtg-deck-testing-lab/backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd /home/nick/mtg-deck-testing-lab/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Access from another machine:
- `http://<server-ip>:5173`

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
- `POST /matches/{match_id}/priority-stops`
- `POST /matches/{match_id}/sideboard`
- `POST /matches/{match_id}/next-game`
- `POST /simulate/batch`
- `POST /ai/diagnostics`
- `GET /analytics/history`

## How Rules Engine Works

- Match initializes from parsed decklists into card instances and zones.
- Step order:
  - Untap, Upkeep, Draw
  - Precombat Main
  - Begin Combat, Declare Attackers, Declare Blockers, Combat Damage, End Combat
  - Postcombat Main
  - End Step, Cleanup
- Legal actions are generated from current step, priority owner, and board state.
- Actions can place spells/abilities on stack; stack resolves after both pass.
- State-based actions execute repeatedly to enforce loss/death/legend/loyalty checks.
- Continuous/static evaluation computes effective power/toughness and effective keywords from battlefield text each time rules checks run.
- Cleanup enforces hand size by default unless explicit effect grants no max hand size.

## How AI Works

- AI infers or uses provided deck archetype.
- Action selection uses board-eval + archetype-biased heuristics.
- `master` adds tactical lookahead; `master_plus` adds light rollout.
- AI now includes safeguards for:
  - mandatory land development windows
  - cast legality edge cases
  - blocker-loop prevention in declare blockers

## How to Add Cards

1. Sync card data:
```bash
curl -X POST "http://127.0.0.1:8000/cards/sync?name=Lightning%20Bolt"
```
2. Card cache is persisted and then available to deck validation and gameplay hydration.
3. Extend behavior in:
- `backend/rules_engine/oracle_effects.py`
- `backend/effects/handlers.py`
- `backend/rules_engine/events.py`
- `backend/rules_engine/engine.py`

## How to Add Decks

1. Import with text format:
```text
4 Lightning Bolt
3 Counterspell
20 Island
```
2. API:
- `POST /decks/import`
- `POST /decks/import-file`
3. Built-ins are defined in:
- `backend/decks/builtin_decks.py`

## Diagnostics and Simulation

### Quick matchup debug
```bash
cd /home/nick/mtg-deck-testing-lab/backend
PYTHONPATH=. .venv/bin/python scripts/debug_head_to_head.py \
  --deck-a "Dimir Control" \
  --deck-b "Ramp" \
  --matches 20 \
  --max-ticks 1500
```

### Round-robin anomaly scan
```bash
cd /home/nick/mtg-deck-testing-lab/backend
PYTHONPATH=. .venv/bin/python scripts/overnight_verbose_round_robin.py
```

## Priority Roadmap (Next)

1. Improve AI blocking quality beyond basic assignment
- better multi-block logic
- better trade/no-trade evaluation by archetype and race state

2. Expand enchantment and triggered interaction fidelity
- extend static parser beyond current common templates (attachments/auras, noncreature permanent stat/text modifications, multi-condition clauses)
- improve event-hook coverage for delayed/conditional triggers

3. Reduce matchup skew and tune deck-specific AI policy
- control vs aggro pacing and removal timing
- tempo and drain sequencing improvements

4. Improve combat telemetry and explainability
- clearer structured logs for attack/block decisions
- expose decision rationale in diagnostics output

5. Finish sideboard UX and between-game testing flow
- make best-of sideboard workflows easier to run from frontend

6. Continue rules-edge hardening
- replacement effects
- continuous/layered effects
- more comprehensive CR corner-case handling

## Contribution/Workflow Rule

If code behavior changes (rules, AI, endpoints, diagnostics), update this README in the same push.

## Known Limitations and Next Upgrades

- Not full comprehensive MTG Comprehensive Rules coverage yet.
- Oracle interpretation is pattern-based and incomplete for highly complex cards.
- AI is heuristic/tactical, not full MCTS or deep search.
- Matchup balance is still being tuned deck-by-deck.
- Sideboard and advanced test orchestration UX still needs expansion.

Planned upgrades focus on:
- deeper rules fidelity,
- stronger tactical AI,
- clearer diagnostics,
- and smoother competitive deck-testing workflows.
