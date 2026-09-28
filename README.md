# MTG Deck Testing Lab

MTG Deck Testing Lab is a desktop-first Magic: The Gathering deck testing application for rules-aware playtesting, AI-vs-AI validation, and long-run matchup analysis.

It is designed for serious deck work:
- Human vs AI playtesting
- AI vs AI simulation
- Batch matchup analysis and replay diagnostics
- Persisted diagnostic-run browsing with bounded anomaly/root-cause snapshots
- Custom deck import and deck library management
- Rules-engine-first gameplay logic with local persistence

## Current Features

### Gameplay
- Two-player match flow with turn structure, priority, stack, combat, cleanup, and turn advancement
- London mulligans through zero cards, with deliberate ordered bottom-card selection for human seats
- Manual phase progression and autoplay
- Land drops, casting, activated abilities, combat actions, and response windows
- Seat-aware human hand and ability controls, including permitted exile/top-library spells, explicit crew selection and Ninjutsu; unhandled legal action kinds show a warning
- Bounded typed deck/action inputs, checked copy-on-write human actions, structured request errors and visible manual-action failure feedback
- Live match responses pass a runtime core-state/card-view/blocks-shape check before entering the UI; broader generated API contracts remain unfinished
- Public live-match responses hide AI-controlled hands while retaining hand counts; AI legal-move queries cannot expose their playable cards
- Testing Simulator job responses check status, progress and completed summary metrics at runtime; the result no longer crosses the UI boundary as `any`
- Saved-match discovery/refresh recovery, automatic-play pause/resume, one coordinated UI writer and durable revision/idempotency metadata for guarded match mutations
- Interactive BO3 matches persist a root seed and derive per-game seeds without exposing them during play. The prior game's human loser chooses play or draw between games; AI losers choose play by default. The choice and subsequent game survive match restore.
- Default spell timing: sorceries and non-flash permanents require an empty-stack main phase; instants and flash remain usable in response windows
- Damage, prevention, protection, replacement effects, trigger resolution, and state-based actions
- Continuous-effect and replacement ordering use deterministic battlefield tie-breaks when timestamps collide
- Multiple prevention/replacement candidates use one explicit or deterministic timestamp-ordered choice per event, with source metadata preserved for replay diagnostics
- Continuous and replacement sources carry persisted monotonic effect timestamps, with deterministic tie-breakers for legacy snapshots and same-timestamp entries
- Continuous-effect diagnostics expose explicit layer ordering for supported keyword and power/toughness effects
- Supported `can't have` keyword overrides remain authoritative even when a later effect grants the keyword
- Draw/life replacement chains preserve consumed sources to prevent repeated application loops
- Human-controlled matches pause supported top-level replacement events and present legal `choose_replacement` buttons; the pending stack item is snapshot-persisted and resumes after selection. AI/replay uses deterministic timestamp ordering.
- Human-controlled simultaneous trigger groups pause before stack insertion and expose validated `choose_trigger_order` moves; APNAP grouping and AI/replay fallback remain deterministic.
- Supported single-target ETB and self-cast abilities choose targets in their trigger window, separate from the permanent spell. Human choices survive snapshots; unattended play selects a legal target, and target legality is rechecked on resolution. Supported optional triggers offer a separate accept/decline decision at resolution. This is not yet a general triggered-ability target/mode model.
- Divided-damage spells recheck each announced recipient at resolution. Illegal recipients take no damage, legal recipients retain their original allocation, and a spell with no legal recipients does not resolve. Protection is checked for divided recipients at announcement as well as resolution.
- Human-controlled lethal creature deaths in state-based actions and combat cleanup pause for multiple die replacements and resume through the same ownership-correct zone-change path.
- Human-controlled legend-rule zone changes use the same resumable die-replacement choice contract; chained prevention choices and simultaneous SBA batching remain under active rules hardening.
- Damage prevention re-evaluates the modified event and applies remaining applicable sources once each; human matches receive follow-up choices for the chain, while AI/replay uses deterministic timestamp ordering.
- Common continuous `can't have` keyword overrides are applied after applicable grants through deterministic layer ordering.
- Simultaneous lethal creature state-based actions batch zone changes and deduplicate supported `one or more` death triggers before stack insertion.
- Saga chapters can create one-shot next-creature entry counters and transform a double-faced Saga through the stack; pending delayed entries survive snapshots and expire at cleanup.
- Master+ uses a bounded three-ply strategic search on late, developed boards with a reduced candidate beam; early states retain cheaper search.
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
- Look-at-top creature reveals with printed mana-value or power limits, optional human selection at resolution, deterministic AI selection, and random-order bottom placement where Oracle text requires it
- Shared cast-choice plumbing for modes, faces, X values, targets, and library-search selections across human and AI actions
- Generic conditional target legality for common type exclusions and mana-value ceilings, including nonartifact/nonland/noncreature, creature-or-planeswalker, controlled-basic-land, and controller-graveyard restrictions
- Conditional counterspell payment and noncreature stack-target legality, with explicit API payment choices and deterministic automated fallback
- Replacement candidates are queryable through `/matches/{match_id}/replacement-options`, and explicit source IDs can be carried through structured cast choices; deterministic timestamp selection remains the AI/replay default
- Replacement-option responses identify the deterministic policy as `latest_effect_timestamp` and suppress choices that a supported prevention override makes impossible
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
- Double-faced type lines use the front face until a legal transform selects the back face, avoiding premature creature/land characteristics from combined metadata
- Both battlefield transform paths normalize face power, toughness, loyalty and keywords through the shared face adapter; AI threat checks use effective power rather than raw printed strings
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
- Diagnostic replay scripts hydrate cards from the local cache before simulation; unknown cards retain unknown characteristics instead of being silently treated as generic 2/2s

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
- Combat AI evaluates resolved effective stats and blocker ownership, including counters, continuous buffs, temporary changes, and characteristic-defined values
- Complexity-bounded Master deep search: dense token boards fall back to deterministic heuristic/combat evaluation so long simulations remain responsive
- Combat search preserves blockers when a non-lethal line would only chump without removing an attacker, while retaining lethal-prevention and profitable-trade lines
- Engine-tagged control spell scoring now uses board-role context without crashing the head-to-head simulator

### Simulation and Diagnostics
- AI vs AI autoplay
- Batch simulation with progress tracking
- Replay inspection and deterministic regression checks
- Seeded best-of-3/5/7/9 replay validation with per-game hashes, legal-action traces, and timeout classification
- Match logs, anomaly output, and training trace export
- Stable AI decision-reason labels and legal-action summaries in verbose traces, analytics, and training exports
- Card-play analytics flag pass-with-unused-mana and main-phase land-not-first decisions with the surrounding hand/board context
- Card-play analytics excludes tapped blockers from attack-quality warnings and preserves hand/board context for missed-land investigations
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
- Testing Simulator can browse persisted diagnostic summaries without loading raw anomaly logs; selected runs show bounded samples and cluster metadata

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

The Vite development server proxies `/api` and `/card-images` to the backend on port `9999`. Production builds also default to same-origin `/api`, so a static deployment must proxy both `/api` (stripping that prefix) and `/card-images` to the backend. For a separate backend origin, copy `frontend/.env.example` to `.env.production` and set `VITE_API_BASE_URL` before building, for example `http://192.168.1.50:9999` on an HTTP-only LAN. Use an HTTPS backend origin when serving the frontend over HTTPS; the app no longer guesses an HTTP backend on port `9999`.

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

The dependency-free Chromium action regression is available through `npm run test:browser` after starting its isolated fixture API and browser. Setup and coverage limits: [human action browser tests](docs/testing/human-actions-browser.md).

To smoke the built frontend through an isolated HTTPS proxy and a separately configured HTTPS backend origin (requires `openssl`, Chromium, and the backend venv):

```bash
npm --prefix frontend run build
D=$(mktemp -d /tmp/mtg-routing-XXXXXX)
git ls-files backend | tar -cf - -T - | tar -xf - -C "$D"
python3 frontend/tests/production_proxy_smoke.py --backend-dir "$D/backend" --dist-dir frontend/dist --python "$PWD/backend/.venv/bin/python" --browser --cross-origin
```

The harness writes only to the disposable backend copy, uses a temporary self-signed certificate, and restores the original frontend build after its cross-origin variant. It checks the built page in Chromium plus HTTPS health, import, match start/action and card media in both modes. It is not a trusted-certificate LAN deployment or an authorization test.

The production frontend shows a backend health indicator and polls `GET /health`. A red/offline indicator means the page loaded but cannot reach the API; use the Retry control after correcting `VITE_API_BASE_URL` or the reverse-proxy route.

The rules engine exposes explicit choice contracts for supported tutor and top-library effects. Expressive Iteration-style effects accept one selected card for hand, one for exile, and an ordered list for the bottom of the library; invalid, duplicate, or incomplete selections are rejected before the spell reaches the stack. AI callers use deterministic value-based choices when no explicit choice is provided.

Common tempo bounce is also handled through the rules engine: nonland-permanent and creature returns use legal target hints, preserve ownership for stolen cards, emit battlefield-leave events, and return the permanent to its owner's hand. Master AI additionally evaluates small-board attack subsets through blocker search and combat resolution before committing attackers.

### Expanded keyword engine

Battlefield controls follow the acting human seat instead of assuming player 1. Legal-move responses include public card views for playable non-hand cards; exile/library/graveyard casting preserves its source flags. Ordinary permanent abilities offer target/mode controls and advanced JSON choices. Ability targets are checked before paying activation costs, and adjacent mana symbols are retained. Variable activated mana costs are explicitly unsupported and are not offered as legal actions.

Cleanup offers deliberate discard selection to human seats, persists that choice through snapshots, and emits the same discard events used by spells. Damage and turn-duration effects expire after discarding; resulting state-based actions/triggers open priority and force another cleanup. Normal cleanup cannot cast spells or activate abilities. The controls panel exposes pending cleanup, draw-replacement and mandatory sacrifice choices with the correct acting seat.

Live starts, sideboarding and diagnostics share face-aware cached-card hydration. Public views retain both faces and the selected face, expose effective battlefield stats separately from base stats, and include counters, damage and effective keywords. Hover previews display this information. The generic token fallback ships as a tracked asset and is installed into an empty image cache automatically; artwork retrieval still prefers real token images.

Dedicated core handlers now cover Infect/Wither damage, poison loss, Toxic combat damage, Ninjutsu, Annihilator sacrifice choices, Escape graveyard costs and Prototype alternative characteristics. Dredge is optional per draw; draw-step and spell draws share the replacement-aware handler. Pending draw/sacrifice choices and resolving spells survive snapshots, including multi-draw effect continuations. Activated abilities and cycling do not count as casting spells.

These are engine/API foundations, not all-card certification. Full human-game/browser acceptance, complex action choices, interacting replacement choices, Prototype copy/layer edge cases, and split first-strike priority windows still need integration work. Morph/Manifest, Suspend, Mutate, Discover, Craft, Banding and complete Battle rules remain unfinished. See `docs/rules/expanded-keywords.md` for contracts and coverage limits.

Master attack search is intentionally bounded to late-game positions with no more than three candidate attackers and two untapped blockers. Larger boards use the normal tactical heuristic so long-running simulator batches remain responsive.

Master two-ply and rollout search is also bounded by total battlefield permanents and legal-action count. This keeps token-heavy matchups responsive; it is a performance guard, not a claim of exhaustive search or pro-level optimal play on large boards.

Common Sagas now receive lore counters during precombat main, put matching chapter abilities on the stack, and are sacrificed by state-based actions after the final chapter resolves.

Vehicles expose explicit crew actions. The engine validates creature power and pays tap costs at activation, then puts a counterable crew ability on the stack. On resolution, the same battlefield Vehicle becomes a creature until cleanup; the AI selects a legal crew group but skips redundant repeat activations. Crewing an already-creature Vehicle remains legal for humans. Vehicle-specific "becomes crewed" triggers and unusual copy/layer interactions still need broader coverage. See [crew timing checks](docs/testing/crew-stack-timing.md).

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

### Canonical Card Knowledge

The knowledge database can ingest every unique Oracle card from Scryfall's official bulk dataset, including face data, keywords, legalities, image URLs and provenance. This stores metadata, not new rules implementations or trained AI behavior. Same-name token variants retain separate Oracle identities; their exact printed names remain in the canonical payload.

```bash
cd backend
./.venv/bin/python -m scripts.sync_all_card_knowledge
./.venv/bin/python -m scripts.sync_corpus_cards --out knowledge/data/corpus-sync-summary.json
./.venv/bin/python -m scripts.knowledge_gap_report --require-rulings
./.venv/bin/python -m scripts.card_mechanics_inventory --out knowledge/data/mechanics-inventory.json
```

The bulk command writes `CardKnowledge` in the application's SQLite database without replacing the gameplay/image cache. Repeated imports reuse the downloaded dataset and unchanged rows. Bulk download files and summaries live in ignored `backend/knowledge/data/`; rebuild them after a fresh checkout. Back up `backend/mtg_lab.db` before refreshing local data. Both sync commands accept `--database /path/to/isolated.db` for isolated ingestion.

Bulk data does not include downloaded rulings. The corpus command verifies them separately, treating a successful empty list as valid and marking failed fetches as errors. Use repeatable `--name "Card Name"` or `--query "f:standard" --limit 200` to verify additional cards; `--force` refreshes previously verified entries. Knowledge coverage does not certify gameplay support, and the current AI does not yet consume this table.

The September 27 local import contains 38,690 unique Oracle records and 6,433 faces. Rulings verification passes for the shipped/saved corpus (88 requested names, 87 verified canonical records). The mechanics inventory records metadata and explicit gap candidates, including Morph, Suspend, Infect, Ninjutsu, Mutate, Discover and Escape; it does not infer complete support from a keyword match. Counts and provenance are recorded in `docs/plans/baselines/2026-09-27-card-knowledge.json` and `2026-09-27-mechanics-inventory.json`.

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
Known cached art-series, token and emblem objects are reported as non-playable on import and rejected before a match starts. Unknown cards still require metadata sync before play.
The import panel shows a mana curve computed from cached Oracle mana costs, with lands and unresolved cards counted separately. For modal/transform cards the curve uses the front face; X is zero outside the stack. Spell-color counts use cached card colors and exclude lands, so they are not a mana-source analysis. Archetype analysis receives resolved metadata, but remains a heuristic rather than a verified deck strategy.

## Card Data and Images

The app syncs and caches card data locally.
- Card metadata is stored for repeatable testing
- Missing art falls back to local placeholder handling
- Cached double-faced cards reuse face-level art when the root image is missing
- Exact cached card names take precedence over face aliases; non-playable art-series records cannot masquerade as a land or other split-face alias
- Token art resolves when available, with a generic token fallback before blank placeholders
- Fallback card lookups normalize punctuation, spacing, and common transform-face import names

## API Overview

Base backend default: `http://0.0.0.0:9999`

`0.0.0.0` is a bind address; browsers use the host's real address. Operation is currently private, single-user and single-worker. Per-match locks coordinate this process only; they do not provide network authorization or multiworker consistency. Do not expose the dev service to the public internet.
Human-vs-human mode is a shared-device sandbox, not a private two-account game: both human hands remain available to the same unauthenticated client. Seat authentication and per-viewer redaction are required before claiming hidden-information privacy for separate human players.
The single-process API admits one batch simulation at a time across synchronous and background-job routes; additional requests receive `429 simulation_busy`. This bounds concurrent batch execution, not on-disk job retention, cancellation, multiworker coordination or total CPU used by the admitted job. Interrupted jobs are marked failed after backend restart.
The process keeps at most 20 completed/failed simulator jobs in memory; older results remain queryable from SQLite. Database retention and automatic cleanup are not yet configured.

Start/batch payloads accept `{quantity, card_name}` entries, resolving gameplay data from the card cache/source rather than arbitrary client Oracle text. Mainboards require 60-250 cards; `sandbox: true` permits 1-250. The upper bound is an application resource limit, not a Magic rule. Sideboards are capped at 15. See [input contracts](docs/api/input-contracts.md) for actions, errors and remaining guarantees.

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
- `GET /matches`
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
- `GET /diagnostics/runs`
- `GET /diagnostics/runs/{run_name}`
- `GET /diagnostics/compare`
- `GET /diagnostics/compare/replay`
- `GET /diagnostics/runs/{run_name}/games/{game_index}`
- `GET /ai/priors`
- `POST /ai/priors/rebuild`
- `GET /analytics/history`

## Current Status

The application currently supports:
- Rules-aware 2-player testing with turn structure, priority, stack, combat, cleanup, and turn advancement
- Shared cost-modifier handling for supported static spell taxes, including opponent-scoped taxes
- Human vs AI, AI vs human, and AI vs AI matches
- Manual phase progression and autoplay-driven simulation
- Built-in deck imports, expansion deck imports, file/text deck import, and deck saving
- Local card caching with image fallback handling
- Replay logs, batch simulations, matchup stats, anomaly diagnostics, turn-level AI trace summaries, and training trace export
- Compact first-divergence drilldown for replay drift analysis
- Bounded persisted-game replay comparison with categorized first-divergence context
- Paginated persisted game-log playback with bounded response pages
- Role-aware log priors derived from replay traces and training exports
- AI seat control with archetype detection, hand-profile mulligan logic, curve evaluation, interaction heuristics, attack heuristics, and keyword-aware battlefield evaluation
- Matchup profiles for control, ramp, tempo, token, and removal-heavy shells
- Responsive desktop UI with readable stack, priority, mana, and hover inspection

Current focus:
- expanding targeted trigger choices beyond bounded ETB/self-cast clauses, non-damage multi-target rechecks and broader face mechanics
- full-game browser acceptance, new-match creation recovery and successful-response runtime validation
- sideboard-aware interactive BO3 browser coverage and full response-contract acceptance
- expanding Oracle coverage for older and unusual cards
- improving replacement, prevention, and layer fidelity in edge cases
- deepening tactical AI for complex board states and matchup-specific heuristics
- broadening deterministic replay coverage across more representative deck pairings
- keeping the UI dense and readable during long sessions
- validating LAN and long-session UX, then adding richer state-by-state replay reconstruction

## Known Limitations and Next Upgrades

- The supported look-at-top creature-reveal pattern is tested with Recruitment Officer and Militia Bugler text. Other top-library effects still need an audit for resolution-time choice, hidden-information exposure, and full Oracle clause fidelity; a successful parser match is not proof of correct resolution.
- Conventional permanent spells compile separately from their later abilities: resolving them puts them onto the battlefield rather than executing activated or triggered Oracle text. Aura attachment and supported entry choices remain intact; modern "enters" wording uses the entry-event matcher. Bounded single-target ETB and self-cast triggers choose targets in the ability window, with an optional accept/decline decision at resolution where applicable. Other trigger families, modal/multi-target clauses and multiple ability clauses remain local-beta blockers. See [targeted trigger boundary](docs/testing/targeted-trigger-choices.md).
- Canonical modal spell faces have independent timing/cost/target moves, selected stack characteristics, snapshot restoration and correct spell/permanent resolution zones in the tested fixtures. Humans can select available faces; AI materialization and cast bias use the offered face. [Face-boundary tests and limits](docs/testing/modal-spell-faces.md) cover this narrow contract, not every face mechanic. Common modal land-face plays and Adventure resolution/exile permission paths are [tested separately](docs/testing/land-adventure-boundary.md). Divided-damage recipients now have bounded resolution-time legality coverage; non-damage multi-target spells, conditional land entries, split-card restrictions and full face-specific restart/browser acceptance remain open. Older cache rows need force-sync to acquire canonical layout.
- Guarded match writes persist history/snapshots together and restore memory on storage faults. Saved-match restore, overlap suppression and lost-response reconciliation have focused browser coverage; match creation is not yet idempotent and extended disconnect/soak acceptance remains open. Legacy headerless callers have no stale-version guarantee.
- New interactive matches persist root/per-game seed provenance and previous-loser play/draw choice. Existing saved matches without root seeds remain unseeded in later games; sideboard strategy, full BO3 browser coverage and drawn-game policy remain open.
- Human action browser fixtures cover fifteen paths, including both BO3 play/draw choices, but not a complete game or series. The crew scenario checks a responseable stack ability and the cast-trigger scenario checks target choice above a creature spell; variable activated mana costs remain explicitly unsupported.
- Target declaration checks cover supported patterns, not complete multi-role/controller-qualified Oracle targeting. Generic AI allocation is legal for tested clauses but not a complete tactical optimizer.
- Private single-user/single-worker operation only: authentication, bounded job admission, cross-worker coordination and production HTTPS/proxy validation remain release gates.
- Long-tail Oracle coverage is still incomplete for fringe older cards and uncommon wordings.
- Some replacement and prevention interactions still rely on heuristic inference instead of a fully generic rules model.
- Layer ordering and timestamp resolution still need more fidelity in obscure overlapping effects.
- The AI still needs more long-run tuning for control, tempo, ramp, token, and combo-lite matchups.
- Larger deterministic replay matrices and longer validation runs would improve confidence in balance and edge-case coverage.
- Persisted replay inspection is paginated and bounded; state-by-state card highlighting and full long-session/LAN validation remain future work.
- The UI still has room for more polished long-session deck-testing ergonomics.

## Development Notes

- Gameplay rules live in application code, not in SQL.
- `README.md` describes the current product state.
- `CHANGELOG.md` records milestone-level history.
- `plan.md` tracks the remaining finish work.
