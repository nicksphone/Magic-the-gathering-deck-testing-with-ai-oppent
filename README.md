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
- Copy effects now distinguish copied spells from copied activated/triggered abilities
- Split-card metadata now exposes face-name hints for downstream validation/rendering
- Continuous-effect diagnostics now include deterministic layer traces for static-order debugging

### AI System
- Difficulty levels: `casual`, `strong`, `master`, `master_plus`
- Archetype-aware behavior (aggro/control/ramp/tempo/etc.)
- Mulligan logic by land window + hand quality
- Land-development prioritization safeguards
- Tactical attack/block selection
- Counterspell/interaction hold-up heuristics
- Counterspell target selection now evaluates all stack objects and prefers highest-threat spells
- Improved late-game control behavior: deploys major castable threats instead of over-holding interaction
- Additional X-spell safety guards in AI selection to prevent invalid `X=0` cast loops
- Late-game attack progression policy in declare-attackers to reduce pass-loop timeouts
- Limited lookahead and rollout scoring at higher difficulties

### Deck Workflows
- Paste/import deck text
- Upload deck files
- Built-in deck library
- Expansion top-deck catalog import
- Expansion catalog mainboards normalized to 60-card minimum for clean import-all runs
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
- Deterministic card-instance IDs for replay-stable duplicate-card tie-breaking
- Overnight round-robin scripts
- Anomaly clustering report generation
- Stall and land-window anomaly counters in diagnostics
- Head-to-head debug traces now include `legal_non_pass` and `legal_has_land` markers
- Card-play analytics script for per-matchup action/cast/pass profiling:
  - `backend/scripts/card_play_analytics.py`
- Round-robin script startup bug fixed (`_write_anomaly_clusters` call order)

## Recent Improvements (2026-06-07)

- Replay determinism is now clean on the current 8-deck regression slice:
  - Duplicate card copies now receive deterministic per-match instance IDs instead of runtime UUIDs.
  - Replay normalization still strips transient UUID noise from logs and stack events.
  - Latest verification run: `28 games`, `0 determinism failures`.
- Wider replay verification also passed:
  - `66 games`, `0 determinism failures` on the 12-deck replay matrix slice.
- AI duplicate-copy tie-breaking is now stable:
  - Equivalent cards with the same name no longer drift because of random instance identifiers.
  - This removes false replay divergence from choosing between identical copies of the same land or spell.
- Oracle/rules coverage tightened:
  - Copy-spell inference now resolves stack targets and activated/triggered ability copies.
  - Copy effects now execute through the resolver instead of being a no-op.
  - Protection handling now recognizes additional noncreature/nonland style protection tokens.
  - Split-card identities are surfaced explicitly for downstream validation/rendering paths.
  - Continuous-effect traces now expose ordered layer application for diagnostics.
- Diagnostics and UI polish:
  - Live replay responses now include log fingerprint metadata for faster debugging.
  - Battlefield card stacks render more compactly for long board states, with stronger hover emphasis.
- Deterministic replay matrix script remains the primary regression gate:
  - `backend/scripts/regression_matrix_replay.py`
  - Normalized log hashing continues to catch true gameplay drift while ignoring transient IDs.

## Recent Improvements (2026-05-16)

- `/decks` response now deduplicates by normalized `(name, source)` and returns newest entries.
- Local deck DB cleanup path validated (stale historical duplicate deck rows removed from runtime DB).
- AI counterspell logic improved:
  - Better stack threat scoring for interaction timing.
  - Counter target selection prefers highest-impact opposing stack spell.
- Combat decision quality improved:
  - Aggro/tempo attack selection now avoids obvious suicide attacks into larger blockers unless race/lethal pressure justifies it.
- Continuous rules coverage expanded:
  - Added support for self-scaling buffs from graveyard counts (for example, "gets +X/+Y for each ... card in your graveyard").
  - Added support for self-scaling buffs from battlefield counts (for example, "gets +X/+Y for each other ... you control").
- Land tapping logic improved for dual/multi-color lands:
  - `tap_land_for_mana` and bulk tap now accept optional requested color.
  - Color inference now reads both known land names and oracle mana symbols.
- Training run completed after fixes:
  - Run: `backend/training_runs/overnight-20260516-175903`
  - 45 deck pairs x 2 games each, anomaly outputs generated (`summary.json`, `anomaly-clusters.json`).
- AI matchup behavior scaffolding added:
  - `backend/ai/matchup_profiles.py` defines archetype-vs-archetype proactive/hold-up bias knobs.
  - `backend/ai/endgame_policy.py` centralizes late-game closure thresholds by matchup.
  - `backend/ai/agent.py` now consumes those profiles for pass/interaction pressure decisions.
- Token image support improved:
  - Token creation now attempts Scryfall token-art resolution by token name/P/T.
  - If exact token art is unavailable, a local generic token image is used.
  - Supports DFC face-name cache aliasing (e.g., `Delver of Secrets` matching `Delver of Secrets // Insectile Aberration`).
  - Token art now caches to local `/card-images/...` paths when available, reducing remote hotlink failures during long sessions.
  - Guaranteed local placeholder card art now applies when external card sync/image fetch fails (including enchantments and other noncreature types), preventing blank card tiles.
- Log-driven AI priors:
  - Added `backend/ai/log_priors.py` to build/load card timing priors from replay/training logs.
  - Added `backend/scripts/build_ai_log_priors.py` to extract priors from local match history and `backend/training_runs`.
  - Added API endpoints:
    - `GET /ai/priors` returns current priors payload.
    - `POST /ai/priors/rebuild` rebuilds priors from available logs and hot-loads them into AI.
  - AI cast scoring now incorporates historical timing bias for noncreature spells, improving control/slow-deck hold-vs-cast behavior.
- Broader replacement + layer fidelity:
  - Added life-lock replacement support in effect resolution:
    - `players/your opponents can't gain life`
    - `you/players/your opponents can't lose life`
  - Added keyword removal layer handling in continuous effects:
    - `... lose flying/reach/...`
    - `... lose all abilities`
  - Keyword grant/removal ordering now applies in battlefield iteration order for more consistent layer-like behavior in static text interactions.
- Deeper tactical AI under complex boards:
  - Added crackback-risk filtering for attack selection to reduce overextension into lethal return swings.
  - Existing rollout/lookahead plus matchup profile logic now keeps more blockers back when race state is unfavorable.
  - Threat-based removal targeting now evaluates creature danger (power/evasion/key combat keywords/protection pressure), not only raw power.
  - Control hold-up logic now shifts proactive when opponent is tapped low, improving seasoned sequencing rather than over-passing.
  - Control cast heuristics now avoid low-value removal fire into empty boards and better convert windows where interaction risk is low.
- Improved simulator diagnostics:
  - Batch simulation now reports anomaly counters and top error lines in addition to win-rate stats.
  - Added deterministic replay fingerprint (`sha256`) per batch result for quick reproducibility checks.
- Larger deterministic regression workflow:
  - Added `backend/scripts/regression_matrix_replay.py`:
    - Runs deck-pair matrix games with fixed seeds
    - Replays each seed twice
    - Flags determinism mismatches (winner/turn/log hash drift)
- Board heuristic hardening:
  - `evaluate_inevitability()` now gracefully handles lightweight/fake state objects used by tests.
  - Full backend suite remains green after integration (`187 passed`).
- Head-to-head debug command note:
  - `scripts/debug_head_to_head.py` uses `--max-ticks` (not `--max-turns`).
  - Very low tick caps can produce artificial timeouts in priority-heavy control mirrors.

## Recent Improvements (2026-05-17)

- Fixed a high-impact AI timeout loop:
  - Root cause: repeated selection of stale/invalid `play_land` action in the same priority window.
  - Fix: added AI legality guard to skip obviously illegal land actions before final action commit.
  - Result: Blue Control vs Burn tuning run now reports `timeout: 0` in latest 10-game sample.
- Added explicit priority-pass logging in engine flow:
  - Match logs now include `passes priority on <step> (stack=<n>)` for direct pass-window diagnostics.
- Control-vs-burn tuning pass:
  - Added stabilization-first logic (remove pressure before greedy value lines) for control archetypes.
  - Added stack-threat and end-step card-advantage forcing hooks for control timing quality.
- Blue Control built-in deck reworked into a castable interaction shell:
  - Shifted from white-heavy, color-strained list to a Dimir-style control package with early black removal.
  - Runtime `deckrecord` rows for `Blue Control` updated to match the new shell.
- Fallback card metadata expanded for control/removal package:
  - Added/updated fallback entries for `Fatal Push`, `Go for the Throat`, `Drown in the Loch`,
    `The Meathook Massacre`, `Torrential Gearhulk`, `Sheoldred, the Apocalypse`, and `Swamp`.
- Knowledge graph refreshed:
  - `graphify update .` executed and `graphify-out/*` artifacts updated in-repo.
- Pass-overuse diagnostics refined:
  - `passed_with_options` now counts only meaningful own-main-phase pass decisions (active player, empty stack, actionable non-pass options).
  - This removes inflated counts from non-actionable priority windows.
- Oracle fallback signal quality improved:
  - Static/keyword-only text (for example haste/flying/prowess lines) is treated as resolver no-op without warning spam.
  - True unresolved action/trigger text still logs as inference misses.
- Added CI regression gate script:
  - `backend/scripts/ci_regression_gate.py`
  - Runs verbose round-robin + deterministic replay checks.
  - Fails on configurable thresholds for:
    - timeouts
    - `passed_with_options`
    - determinism failures
  - Latest smoke run outcome:
    - `timeouts: 0`
    - `passed_with_options: 0`
    - `determinism_failures: 3` (gate correctly fails and surfaces drift)

## Recent Improvements (2026-05-18)

- Deeper tactical/strategic AI planning under complex boards:
  - Added stack-only 2-ply tactical planner for counter-war windows.
  - Planner now only engages on complex states at higher turn thresholds.
  - Strategic search depth reduced in generic mode to avoid unstable overreach.
  - Counter/removal target quality improved for noncreature game pieces:
    - New threat scoring for artifacts/enchantments/planeswalkers with matchup-aware weighting.
    - Counter target selection now better prioritizes high-impact artifact/enchantment stack spells.
    - Noncreature permanent target hints (`artifact_targets`, `enchantment_targets`, `noncreature_permanent_targets`) are now threat-ranked instead of first-match picked.
- Control endgame conversion and long-game planning:
  - Added explicit inevitability policy (`should_force_inevitability_line`) for control/counter-heavy archetypes.
  - Added forced inevitability action selection in own main phase:
    - Prioritizes card-advantage lines (draw), pressure conversion (planeswalkers/threats), and resource denial (discard/mill) over idle passes.
    - De-prioritizes dead counterspell holding on empty stack in long-game windows.
  - Pass-bias and cast-bias now incorporate inevitability-plan signals in control mirrors.
- Regression validation for complicated deck states:
  - `tests/test_ai_decisions.py` expanded to 40 passing tests.
  - Added coverage for control inevitability planner behavior.
  - Ran 9-game complex matchup smoke matrix:
    - `Dimir Control vs Ramp`: `5-4`, `timeout: 0`
    - `Blue Control vs Midrange`: `5-3`, `timeout: 1`
    - `Blue Control vs Dimir Control`: `1-3`, `timeout: 5` (remaining mirror stall hotspot)
    - `Tempo vs Blue Control`: `5-4`, `timeout: 0`
  - Result: broad improvement outside pure control mirrors; mirror timeout reduction remains a priority item.

## Recent Improvements (2026-06-06)

- Combat priority handoff fix:
  - After blockers are declared, priority now returns to the active player immediately.
  - This prevents repeated `declare_blockers` loops where the defender was being asked to block again before combat could advance.
- Combat regression coverage:
  - Added a unit test that verifies blocker declaration hands priority back to the active player.
- Combat window closure fix:
  - The block-declaration window is now single-use per combat step, so the defender cannot re-enter `declare_blockers` after submitting blockers.
  - This closes the last observed `Tempo vs Drain` timeout loop.
- Retest result:
  - `Tempo vs Drain` rerun completed with `timeout: 0` in the latest master-difficulty sample.

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
uvicorn main:app --host 0.0.0.0 --port 9999 --reload
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

## Tournament Data Ingest (Training Corpus)

The project now includes a local tournament data ingest module for importing full event decklists into the database.

Backend module:
- `backend/data_ingest`

New tables:
- `TournamentEvent`
- `TournamentDeck`

New API endpoints:
- `POST /ingest/tournaments/import-json`
- `GET /ingest/tournaments/events?limit=50`
- `GET /ingest/tournaments/events/{event_id}/summary`

Expected JSON payload:
```json
{
  "source": "mtgtop8",
  "event": {
    "external_id": "event-123",
    "name": "RCQ Springfield",
    "format": "modern",
    "event_date": "2026-05-01",
    "url": "https://example.com/event/123"
  },
  "decks": [
    {
      "player_name": "Alice",
      "archetype": "Burn",
      "placement": 1,
      "wins": 8,
      "losses": 1,
      "draws": 0,
      "mainboard": [
        { "quantity": 4, "card_name": "Lightning Bolt" },
        { "quantity": 56, "card_name": "Mountain" }
      ],
      "sideboard": [
        { "quantity": 2, "card_name": "Roiling Vortex" }
      ]
    }
  ]
}
```

Validation:
- mainboard minimum `60` cards is enforced during ingest.

CLI helper:
```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/import_tournament_json.py --input /path/to/event.json
```

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

1. Expand comprehensive rules coverage for remaining legacy mechanics and Oracle corner cases
2. Expand deterministic replay drift tooling with first-divergence root-cause snapshots
3. Expand sideboard UX and full tournament-style BO3 flows
4. Increase property/regression test coverage for edge interactions
5. Improve large-scale simulator analytics and replay diff tooling
6. Expand historical/top-tier deck library breadth
7. Harden card sync retry/version/invalidation behavior
8. Add stricter benchmark gates for release quality
9. Continue archetype-specific AI tuning on newly surfaced matchup anomalies

## Known Limitations and Next Upgrades

Known limitations:
- Full Comprehensive Rules parity is not complete yet.
- Oracle effect interpretation is still pattern-based for many legacy/special-case cards.
- AI remains heuristic + tactical (not full strategic search/planning engine).
- Matchup tuning is ongoing and still deck-dependent in edge cases.
- Some rare legacy mechanics and old-edition corner interactions are not fully implemented.

Next upgrades:
- Broader rules/mechanics coverage with stronger replacement/layer fidelity.
- Larger regression matrix with long-run deterministic replay validation.
- Improved simulator diagnostics and anomaly root-cause attribution.
- Continued UX polish for long-session competitive deck testing.
- Deck-type-specific AI tuning from replay and tournament-like logs.
