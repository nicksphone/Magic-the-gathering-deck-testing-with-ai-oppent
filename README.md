# MTG Deck Testing Lab

MTG Deck Testing Lab is a desktop-first Magic: The Gathering deck testing application for rules-aware playtesting, AI-vs-AI validation, and long-run matchup analysis.

It is designed for serious deck work:
- Human vs AI playtesting
- AI vs AI simulation
- Batch matchup analysis and replay diagnostics
- Custom deck import and deck library management
- Rules-engine-first gameplay logic with local persistence

## Current Features

### Gameplay
- Two-player match flow with turn structure, priority, stack, combat, cleanup, and turn advancement
- London mulligan handling
- Manual phase progression and autoplay
- Land drops, casting, activated abilities, combat actions, and response windows
- Damage, prevention, protection, replacement effects, trigger resolution, and state-based actions
- Continuous-effect and replacement ordering use deterministic battlefield tie-breaks when timestamps collide
- Multiple prevention/replacement candidates use one explicit or deterministic timestamp-ordered choice per event, with source metadata preserved for replay diagnostics
- Human-controlled matches pause supported top-level replacement events and present legal `choose_replacement` buttons; the pending stack item is snapshot-persisted and resumes after selection. AI/replay uses deterministic timestamp ordering.
- Human-controlled simultaneous trigger groups pause before stack insertion and expose validated `choose_trigger_order` moves; APNAP grouping and AI/replay fallback remain deterministic.
- Human-controlled lethal creature deaths in state-based actions and combat cleanup pause for multiple die replacements and resume through the same ownership-correct zone-change path.
- Human-controlled legend-rule zone changes use the same resumable die-replacement choice contract; chained prevention choices and simultaneous SBA batching remain under active rules hardening.
- Damage prevention re-evaluates the modified event and applies remaining applicable sources once each; human matches receive follow-up choices for the chain, while AI/replay uses deterministic timestamp ordering.
- Common continuous `can't have` keyword overrides are applied after applicable grants through deterministic layer ordering.
- Planeswalker loyalty abilities, including X-cost loyalty abilities
- Explicit `{C}` mana handling separate from generic mana
- Ownership-aware zone movement for stolen permanents
- Support for common Oracle patterns such as reanimation, graveyard recursion, tutor effects, and battlefield-tutor resolution
- Explicit library-search candidates and validated player-selected tutor choices, with deterministic fallback selection for AI/replay callers
- Canonical Ramp tutor handling for Cultivate and Migration Path, including basic-land counts, shuffle, and tapped battlefield placement
- Fixed, variable, and alternate cycling, including draw replacement, discard/cycle triggers, optional trigger choices, and basic-landcycling searches
- Broader support for artifact, enchantment, permanent, and combined artifact-or-enchantment trigger wording
- Generic named self-counter triggers for common cast/combat/ETB payoff patterns
- Resolution-time counted creature-type effects for tribal ETB payoffs
- Structured top-card hand/exile/bottom choices with temporary play permissions
- Shared cast-choice plumbing for modes, faces, X values, targets, and library-search selections across human and AI actions
- Generic conditional target legality for common type exclusions and mana-value ceilings, including nonartifact/nonland/noncreature, creature-or-planeswalker, controlled-basic-land, and controller-graveyard restrictions
- Conditional counterspell payment and noncreature stack-target legality, with explicit API payment choices and deterministic automated fallback
- Replacement candidates are queryable through `/matches/{match_id}/replacement-options`, and explicit source IDs can be carried through structured cast choices; deterministic timestamp selection remains the AI/replay default
- Generic noncombat-damage replacement to -1/-1 counters, power-based death triggers, self-cast X triggers, and X-counter entry handling
- Realmwalker-style chosen creature-type persistence and legal casting of the matching creature from the top of the library
- Modal target generation selects the mode before materializing targets, and `Choose two` modes resolve through ordered structured effect sequences
- AI tutor decisions now materialize validated library-search selections instead of retrying malformed search casts
- Graveyard spell targets are legal AI actions for recursion effects such as Torrential Gearhulk-style abilities
- Legacy combat keywords such as `shadow`, `fear`, `intimidate`, and landwalk in blocking logic
- Manual and autoplay-driven best-of-three matches with sideboarding support

### Card Data
- Local card cache synced from live card data
- Oracle text, mana cost, type line, colors, rulings, legalities, and image metadata
- Double-faced, split, modal, adventure, and token-aware card handling
- Generic upkeep top-card transform handling for double-faced cards
- Core day/night state transitions from per-turn spell counts, including daybound/nightbound battlefield transformations
- Day/night transition triggers use the normal stack and APNAP ordering path
- Reusable Aura and Equipment attachment legality, target-choice exposure, and state-based cleanup for invalid Auras
- Generic temporary control-change effects with ownership-safe battlefield movement, cleanup restoration, and snapshot persistence
- Shared battlefield-leave events for destruction, exile, sacrifice, lethal combat, and state-based actions, including common leave-trigger resolution
- Token-aware death replacements that distinguish nontoken clauses from token permanents
- Dynamic characteristic-defining power/toughness for graveyard card-type counts
- Corpus audit distinguishes structured cast effects, structured event/replacement paths, and static/no-op cards; the shipped 81-card corpus currently has zero parser-fallback or missing-Oracle classifications
- Fuzzy matching for deck import correction
- Cached fallback metadata when remote lookups fail
- Token art fallback handling and face-aware image reuse for double-faced cards

### AI
- Archetype-aware AI with difficulty levels: `casual`, `strong`, `master`, `master_plus`
- Hand-profile-aware mulligan decisions, curve evaluation, interaction timing, threat assessment, attack selection, and combat math
- X-spell value selection that trades off board pressure, archetype pressure, and mana efficiency
- Modal, split, and transform-face selection based on board state and matchup pressure
- Board-role-aware planning for stabilize, convert, race, control, and related board states
- Matchup-aware scoring for control, ramp, tempo, tokens, midrange, aggro, and attrition lines
- Replay-prior tuning and training exports for deeper decision analysis
- Adaptive bounded two-ply Master planning on developed boards, including spell sequencing and resource-preserving proactive actions
- Master-level bounded blocker-assignment search on small combat boards, resolving cloned combat states to compare lethal prevention, trades, and post-combat board value
- Complexity-bounded Master deep search: dense token boards fall back to deterministic heuristic/combat evaluation so long simulations remain responsive
- Combat search preserves blockers when a non-lethal line would only chump without removing an attacker, while retaining lethal-prevention and profitable-trade lines
- Engine-tagged control spell scoring now uses board-role context without crashing the head-to-head simulator

### Simulation and Diagnostics
- AI vs AI autoplay
- Batch simulation with progress tracking
- Replay inspection and deterministic regression checks
- Match logs, anomaly output, and training trace export
- Stable AI decision-reason labels and legal-action summaries in verbose traces, analytics, and training exports
- Card-play analytics flag pass-with-unused-mana and main-phase land-not-first decisions with the surrounding hand/board context
- Tactical analytics record effective keywords, attacker/blocker assignments, evasion-aware bad attacks, lethal misses, block trades, and resource-preservation decisions
- First-divergence drilldown with compact trace context for both sides
- Per-game batch results and matchup summaries
- Diagnostic scripts for head-to-head runs, replay regression, anomaly clustering, and training-data extraction
- Corpus audit script for ranking parser fallbacks and missing Oracle metadata across built-in and expansion decks
- SQLite cache resolution is stable across launch directories; API, sync jobs, and diagnostics use `backend/mtg_lab.db`

### UI
- Desktop-first battlefield layout with readable stack, priority, mana, and hand presentation
- Explicit interrupt-window state in the controls panel
- Hover inspection and card zoom for readable long-session testing
- Density-aware battlefield scaling for crowded boards
- Match simulator panel with progress and first-divergence reporting

## Architecture

Gameplay logic lives in application code. SQL is for storage only.

### Backend Layers
- `backend/card_data` - card sync/cache, image cache hydration, and fuzzy lookup
- `backend/rules_engine` - turn structure, priority, stack, combat, timing, state-based checks, and rules inference
- `backend/effects` - modular effect handlers and resolver registry
- `backend/game_state` - canonical state model and serialization
- `backend/ai` - tactical AI, archetype detection, matchup policies, and endgame behavior
- `backend/decks` - deck parser/import, built-ins, expansion decks, and sideboarding support
- `backend/analytics` - batch simulation, replay summaries, diagnostics, and anomaly analysis
- `backend/persistence` - storage layer only
- `frontend/src` - match UI, deck UI, controls, logs, and simulator views

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

The Vite development server proxies `/api` and `/card-images` to the backend on port `9999`. For a separate static frontend deployment, copy `frontend/.env.example` to `.env.production` and set `VITE_API_BASE_URL` to the reachable backend origin, for example `http://192.168.1.50:9999`. If the frontend and backend are served behind one reverse proxy, keep the default `/api` routing and proxy both `/api` and `/card-images` to the backend.

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

The production frontend shows a backend health indicator and polls `GET /health`. A red/offline indicator means the page loaded but cannot reach the API; use the Retry control after correcting `VITE_API_BASE_URL` or the reverse-proxy route.

The rules engine exposes explicit choice contracts for supported tutor and top-library effects. Expressive Iteration-style effects accept one selected card for hand, one for exile, and an ordered list for the bottom of the library; invalid, duplicate, or incomplete selections are rejected before the spell reaches the stack. AI callers use deterministic value-based choices when no explicit choice is provided.

Common tempo bounce is also handled through the rules engine: nonland-permanent and creature returns use legal target hints, preserve ownership for stolen cards, emit battlefield-leave events, and return the permanent to its owner's hand. Master AI additionally evaluates small-board attack subsets through blocker search and combat resolution before committing attackers.

Master attack search is intentionally bounded to late-game positions with no more than three candidate attackers and two untapped blockers. Larger boards use the normal tactical heuristic so long-running simulator batches remain responsive.

Master two-ply and rollout search is also bounded by total battlefield permanents and legal-action count. This keeps token-heavy matchups responsive; it is a performance guard, not a claim of exhaustive search or pro-level optimal play on large boards.

Common Sagas now receive lore counters during precombat main, put matching chapter abilities on the stack, and are sacrificed by state-based actions after the final chapter resolves.

Vehicles expose explicit crew actions. The engine validates creature power and tap costs, makes a crewed Vehicle a creature until cleanup, and lets the AI choose a legal minimal crew group.

Targeted actions are validated against the current candidate set before entering the stack. Stale, cross-zone, or restricted-card IDs are rejected, while broad “any target” effects continue through protection and hexproof checks.

Farewell-style mass exile of creatures is handled separately from destruction: ownership is preserved, battlefield-leave triggers are emitted, and creatures move to their owners' exile zones.

### Diagnostics
```bash
cd backend
python3 scripts/debug_head_to_head.py --deck-a Tempo --deck-b "Blue Control" --matches 1
python3 scripts/regression_matrix_replay.py --matches-per-pair 1 --max-decks 2
python3 scripts/ci_regression_gate.py --matches-per-pair 1 --max-decks 2
```

The `debug_head_to_head.py` smoke path now completes cleanly for Tempo vs Blue Control in local verification.

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

The parser accepts common `Mainboard`, `Maindeck`, `Sideboard`, and `SB:` section headers, set annotations such as `[M11]`, `4x` multiplier notation, and common comment lines.

## Card Data and Images

The app syncs and caches card data locally.
- Card metadata is stored for repeatable testing
- Missing art falls back to local placeholder handling
- Cached double-faced cards reuse face-level art when the root image is missing
- Token art resolves when available, with a generic token fallback before blank placeholders
- Fallback card lookups normalize punctuation, spacing, and common transform-face import names

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

## Current Status

The application currently supports:
- Rules-aware 2-player testing with turn structure, priority, stack, combat, cleanup, and turn advancement
- Human vs AI, AI vs human, and AI vs AI matches
- Manual phase progression and autoplay-driven simulation
- Built-in deck imports, expansion deck imports, file/text deck import, and deck saving
- Local card caching with image fallback handling
- Replay logs, batch simulations, matchup stats, anomaly diagnostics, turn-level AI trace summaries, and training trace export
- Compact first-divergence drilldown for replay drift analysis
- Role-aware log priors derived from replay traces and training exports
- AI seat control with archetype detection, mulligan logic, curve evaluation, interaction heuristics, and keyword-aware battlefield evaluation
- AI seat control with archetype detection, hand-profile mulligan logic, curve evaluation, interaction heuristics, attack heuristics, and keyword-aware battlefield evaluation
- Matchup profiles for control, ramp, tempo, token, and removal-heavy shells
- Responsive desktop UI with readable stack, priority, mana, and hover inspection

Current focus:
- expanding Oracle coverage for older and unusual cards
- improving replacement, prevention, and layer fidelity in edge cases
- deepening tactical AI for complex board states and matchup-specific heuristics
- broadening deterministic replay coverage across more representative deck pairings
- keeping the UI dense and readable during long sessions

## Known Limitations and Next Upgrades

- Long-tail Oracle coverage is still incomplete for fringe older cards and uncommon wordings.
- Some replacement and prevention interactions still rely on heuristic inference instead of a fully generic rules model.
- Layer ordering and timestamp resolution still need more fidelity in obscure overlapping effects.
- The AI still needs more long-run tuning for control, tempo, ramp, token, and combo-lite matchups.
- Larger deterministic replay matrices and longer validation runs would improve confidence in balance and edge-case coverage.
- The UI still has room for more polished long-session deck-testing ergonomics.

## Development Notes

- Gameplay rules live in application code, not in SQL.
- `README.md` describes the current product state.
- `CHANGELOG.md` records milestone-level history.
- `plan.md` tracks the remaining finish work.
