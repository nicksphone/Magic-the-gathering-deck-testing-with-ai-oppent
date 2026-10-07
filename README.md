# MTG Deck Testing Lab

Latest scoped backend qualification: retained Ray copied-spell frames and
counterable control-loss taps, alongside sourced fixed-cost Suspend readiness
and temporary-characteristic HTTP/persistence checks. See
[control acceptance](docs/testing/control-source-frame-current-composition.md)
and [prior acceptance](docs/testing/suspend-and-characteristics-http-current.md).
This remains an unfinished playtesting app, not unrestricted rules certification.

A desktop-first React/TypeScript and Python/FastAPI application for two-player
Magic deck testing, human play, AI matches and reproducible gameplay diagnostics.

Shared activated-cost validation enforces summoning sickness for effective
creature self-tap costs and honors effective haste. See
[bounded acceptance](docs/acceptance/tap-source-readiness-20261006.md) for tested
scope and remaining limitations.
SQLite stores cards, decks, snapshots and results. Gameplay rules live in code,
not SQL functions, triggers or stored procedures.

This is an alpha with **bounded rules support and heuristic AI**, not a certified
implementation of every Magic card or a trained professional-level opponent.
Known-gap diagnostics are useful, but an absent warning does not prove support.
See [the finish plan](plan.md) for remaining acceptance work and
[the changelog](CHANGELOG.md) for historical changes.
The previous detailed gate timeline is preserved in
[the historical plan](docs/history/finish-plan-through-b81862a.md).

This branch is an **unreleased integration candidate**, not necessarily the
version running on the live servers. Scoped acceptance and remaining work are
recorded in [the finish plan](plan.md) and `docs/testing/`. Full-suite, browser,
LAN deployment and broader AI-quality qualification remain open.

Strict preflight currently flags cards in the built-in Mono Red Aggro and Burn
decks, including suspend, damage-to-counter replacement and linked conditional
damage. A natural UI game with those decks has not passed acceptance; warnings
are not bypassed to claim support.

## Current Features

- Supported battlefield/hand `activate_ability` frames capture the announced
  source incarnation before costs change zones. Their supported shuffles retain
  that reference through responses, private choices and snapshot recovery, rather
  than attributing the ability to the source's later object. Older frames without
  the field retain legacy behavior; dedicated cycling/loyalty paths are not
  covered by this change. See [retained-reference acceptance](docs/testing/retained-reference-current-composition.md).

- Supported complete immediate exile/return instructions reuse entry handling
  and retain object identity rather than treating exile alone as completion.
  Supported complete nontoken-permanent instructions offer legal noncreature
  permanents, reject tokens and preserve owner/entry choices. Current composed
  core and HTTP coverage: 78 passing cases; broader blink bodies remain open.
  Search/counter children use independent target clauses. Announced card targets
  retain object identity through resolution and supported copy/retarget choices.
  The original four Favor blink and two Act of Treason blink failures now pass;
  Ray of Command subsequently has bounded control-loss/copy/HTTP qualification
  in the linked current control acceptance. The prior thirty affected modules executed
  730 cases: 692 passes and 38 retained failures, not an all-green release. See
  [current target acceptance](docs/testing/announced-target-current-composition.md).

- Supported self-land animations use source-bound continuous type, subtype,
  color, P/T and keyword records, with real payment, sickness and cleanup.
  The conservative tactical combat leaf uses checked damage/winner outcomes;
  Canonical intrinsic-mana dual lands also qualify without Basic-label or
  card-name heuristics. Broader graveyard-response planning and expert-level
  play remain unverified; 40 desired attack cases are still failing. See
  [animation/AI scope](docs/testing/animation-strategic-current-composition.md).
- Static color predicates and convoke resource queries receive the current
  state rather than relying only on printed colors. The bounded color/resource
  composition passes 85 checks; this is not full color-mechanics certification.
- Admitted complete temporary-creature instructions compose native ability
  loss, color, creature subtype and base-stat records without overwriting printed
  data or counters. Subtype-sensitive cost readers and cleanup/reentry pass pure
  qualification; HTTP acceptance is pending. See
  [temporary characteristics](docs/testing/temporary-characteristics-current-composition.md).

- Generic supported nontoken-creature entry observers distinguish tokens and
  preserve controller predicates and ability suppression. Unconditional global
  as-though-flash grants follow their source and controller without bypassing
  priority, costs, prohibitions or explicit casting restrictions.
- Batch opening-hand quality is attributed to deck identity when seats alternate,
  rather than always assigning player 1 to deck A. Scoped combined acceptance:
  [observer, flash and simulator checks](docs/testing/observer-flash-simulator-current-composition.md).

- Supported complete fixed source +1/+1 and charge-counter activation costs
  combine with mana and tapping, validate before payment, and reject unknown
  cost clauses without partial payment.
- Supported targeted basic-land searches preserve the original effect controller
  while the affected player privately chooses cards or fails to find. Complete
  admitted search-then-counter instructions retain their ordered continuation;
  genuine stack context supplies shuffle attribution. Public prompts omit
  private library and continuation data. See
  [current counter/search acceptance](docs/testing/counter-targeted-search-current-composition.md).

- Supported optional own-hand land deployment uses private, explicit identity or
  decline choices, retains the original controller and resumes entry choices
  after snapshots/restart. The existing GUI handles this choice without allowing
  an empty selection for mandatory land placement.
- Supported paid optional triggers validate and pay actual available resources
  before granting their compiled reward. Unknown clauses remain diagnostics,
  not free rewards. Shared printed-role metadata recognizes hand-to-battlefield
  land deployment in spells, entry triggers and activated instructions.
- Complete self-pump cast/copy instructions retain their printed P/T amount and
  original source incarnation. A pending old self-trigger cannot buff a source
  that leaves and reenters. This is bounded support, not all magecraft effects.

- Complete unconditional self-cast/self-entry draw and life-then-draw instructions
  use shared replacement-aware handlers. Unknown suffixes in these newly
  admitted instructions produce diagnostics without partial rewards. Optional,
  targeted and search routes retain their existing bounded behavior.
- Fixed positive source +1/+1 and charge-counter activation costs are validated
  and paid once on announcement. Ability target hints do not inherit the source's spell
  mana cost; genuine chosen-X ability values and source/LKI protection are retained.
  Other counter kinds, variable removals and unsupported cost clauses remain
  outside this admission.
- The offline seed contains 155 canonical records, preserving every property of
  the original 119 and appending 36 verified full records for historical imports.
  The original eight two-faced cards retain ten canonical and six
  provenance-backed derived color facts. Metadata admission is not rules support.
  Generic exact-printing loyalty recovery avoids named exceptions.
- The offline exporter preserves all 155 records and the explicit 17-fact
  preservation ledger through validated cache/bulk and cache/knowledge routes.
  Repeated CLI outputs are byte-identical. Interrupted publication has explicit
  journal-based recovery using `--recover-publication` without original inputs;
  this is not atomic two-file visibility. Historical 119-record fixtures retain
  their separate contract. See [recovery](docs/testing/export-publication-recovery.md).
- The 53-entry expansion catalog distinguishes archetype templates from sourced
  historical OTJ and MH3 tournament lists. Historical imports preserve published
  60-card mainboards and 15-card sideboards, stable identity and event provenance.
  They do not certify current legality or competitive strength; current-format
  imports fail closed. See [catalog acceptance](docs/testing/catalog-canonical-seed-current-composition.md).
- Backend human legend keeper choices require an explicit offered card. Whole-view
  training intents accept legend context only when it exactly matches current
  authoritative state; supplied context cannot select or replace the keeper.
- AI valuation uses the selected casting face and authoritative available costs
  when reserving supported Adventure interaction. These policies and role tags
  are not professional-level AI certification.

- The local corpus diagnostic uses shared hydration and runtime card facts,
  including verified knowledge and faces. It reports data admission, parser
  paths and choices without equating parser recognition with rules correctness.
  Alternate faces are listed, not independently certified.

- Supported simultaneous mill and selected sacrifice instructions publish genuine
  graveyard-entry receipts only after all selected moves commit. Mill retains its
  original top-card set through replacement shuffles; wider simultaneous event
  handling and competing-replacement continuations remain separate.

- Illegal noncreature Aura departures capture battlefield last-known information
  before shared graveyard/replacement handling. Simultaneous multi-Aura behavior
  remains a separate acceptance task.
- Deck imports project available offline seed and canonical knowledge metadata
  without implicit card-cache writes or invented database IDs. Import analysis
  and cache inventory are separate; art, rulings and explicit synchronization
  remain independently reported.

- AI spell materialization checks harmful friendly damage against legal targets
  while preserving demonstrated beneficial sacrifice/death interactions. This
  is a bounded tactical safeguard, not an expert-policy or balance guarantee.
- Card and token presentation rechecks local image availability after cache
  eviction and selects honest offline fallback art. Repair occurs on resolver
  access; previously stored match image URLs can still return 404 until refreshed.

- Queued extra turns and additional combat/main phases for the currently admitted
  complete clause families, with persisted phase visits and ordinary successor
  tracking. Other turn-changing mechanics remain unsupported.
- Saved matches are discovered from persisted summaries and loaded on first
  match-ID access, rather than eagerly constructing every game at startup.
  This is a local single-worker design, not distributed-worker coordination.
- Supported global static keyword grants affect both players' creatures and
  follow source lifetime and layer ordering.

- Strict Mulligan, Suspend and keep-hand training intents, with explicit source/bottom
  choices and current-actor validation before normalization. Supplied Suspend
  display metadata must match the current offered action. Supplied Mulligan
  counts must match the current actor's offer and cannot override engine state.
- Complete temporary group keyword grants for supported creature/permanent
  clauses. Recipients are fixed at resolution; later entrants and reentered
  objects do not inherit the grant. Canonical Boros Charm and Heroic Intervention
  casts have both-seat HTTP, layer-order, cleanup and snapshot coverage.
- Human versus AI, AI versus AI and shared-device human versus human play.
- Manual turn steps and priority, response windows, stack inspection, combat,
  action logs, life totals and public/private zone views.
- Best-of-three series, between-game sideboarding, play/draw choices and seeded
  setup for newer matches. Older saved matches may lack seed provenance.
- Text/file deck import, saved decks, built-in archetypes, expansion examples,
  fuzzy lookup, curve/color analysis and readiness diagnostics.
- Cached canonical card data, face-aware hydration, local image reuse and
  offline fallback art. Modal land/spell choices and supported Adventure flows
  have both-seat browser and restart coverage.
- Ordinary mana, generic versus colorless requirements, supported restricted,
  snow, hybrid and life payments, explicit resource selections and whole mana
  output vectors. Manual choices are not silently replaced with inferred ones.
- Supported cast/activated costs, graveyard/exile permissions, tokens,
  attachments, counters, planeswalkers, keywords and state-based actions.
- Ninjutsu preserves explicit source/return choices and the activated source's
  hand-zone identity through snapshots. Pending abilities do not move a card
  that left and reentered hand; legacy missing-reference payloads fail closed.
  This correction is qualified in the unreleased candidate, not yet deployed.
- Supported modern and legacy entry observers retain source/controller receipts
  and dispatch complete draw, life, counter and article-mill instructions.
  Ninjutsu entry uses the ordinary zone transition, so entry counters and
  duplicate observers apply consistently. Unknown compound bodies remain diagnostic.
- Bounded replacement and continuous-effect layers, effective combat statistics,
  source-incarnation/last-known-information handling and live color predicates.
- Supported printed self-graveyard replacements on shared discard, mill and
  selected sacrifice/discard cost routes preserve owner-library destinations,
  pre-departure identity and genuine static shuffle causes. Supported handler,
  keyword-sacrifice and shared lethal/legend SBA routes use the same entry plans;
  combat deaths reach that shared SBA path. Public per-cost competing replacement
  selection remains unqualified.
- Supported from-anywhere graveyard triggers, including the canonical Kozilek
  shuffle instruction, retain real source references and owner identity through
  responses and restart. Source departure does not erase an already-triggered
  ability; a legal counter can stop it. Genuine simultaneous discard entries
  are collected after the whole validated batch commits. Other simultaneous
  death/mill/sacrifice publication remains separate work.
  See [current lifecycle acceptance](docs/testing/graveyard-lifecycle-current.md).
- Supported self-cycling, combined cycling/discard and self-death triggers.
  Dynamic death quantities use the retained source receipt; ordinary spell
  instructions are separated from supported cycling-trigger paragraphs.
- Bounded nth-spell triggers for supported complete draw/token clauses, with
  both-player turn resets and cast-versus-copy distinction. Complex rewards
  remain explicitly unsupported; this addition is in the unreleased candidate.
- Artifact/enchantment creature-token descriptors retain their types, subtypes,
  colors, statistics and keywords rather than treating a card type as its name.
- Seat-aware legal-action controls, offered cycling-X selection, private card
  inspection, saved-match recovery, visible errors and unsupported-choice warnings.
- Autoplay, cancellable background simulation, progress diagnostics, saved
  results, deterministic replay checks and decision/anomaly traces.
- Archetype-aware tactical heuristics, combat/resource forecasts, private
  observations and versioned training-environment/trajectory groundwork.
  Regression tests are not neural training or evidence of expert play.
- Provenance-backed local archetype classification for admitted built-ins and
  identity-preserving representative cohorts. Missing facts remain unknown;
  duplicate display names do not merge distinct imported inventories.

Support applies to the qualified clause families, not every card sharing a
keyword. The [rules/choice/color scope](docs/testing/rules-choice-color-composition.md),
[input contracts](docs/api/input-contracts.md),
[training groundwork](docs/plans/learned-policy-groundwork.md) and
[qualification documents](docs/testing/) explain the boundaries.

## Setup

Use Python 3.12 and Node 22 as tested by the current development workflow.
From the repository root, start the backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9999 --reload
```

In another terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

Open `http://<server-ip>:5173`. `0.0.0.0` is a bind address, not a browser
address. The development proxy forwards `/api` and `/card-images` to port 9999.
Production defaults to same-origin `/api`; configure a reverse proxy for that
path, stripping its prefix, and `/card-images`. For a separate API origin, set
`VITE_API_BASE_URL` before building; use HTTPS when the page uses HTTPS.

Operation is **private, single-user and single-worker**. Human versus human is
a shared-device sandbox, not an authenticated two-account game. Do not expose
the development servers publicly. Per-match process locks are not distributed
coordination or authorization. `MTG_DEBUG_HANDS=1` plus the UI's debug toggle can
reveal AI hands for trusted testing; leave it off outside that context.

## Architecture

| Layer | Directory | Responsibility |
| --- | --- | --- |
| Card data | `backend/card_data` | Sync, cache, faces, images and canonical hydration |
| Rules | `backend/rules_engine` | Timing, legality, priority, stack, combat, layers and events |
| Effects | `backend/effects` | Reusable effect handlers and resolution |
| State | `backend/game_state` | Authoritative objects, snapshots and public views |
| AI | `backend/ai` | Private observations, deck profiles and action evaluation |
| Decks | `backend/decks` | Parsing, imports, templates, sideboards and cohorts |
| Analytics | `backend/analytics` | Simulations, diagnostics and statistics |
| Storage | `backend/persistence` | SQLite models/repositories and saved data |
| Knowledge/training | `backend/knowledge`, `backend/training` | Provenance, observations and trajectory contracts |
| UI | `frontend/src` | Deck setup, battlefield, actions and diagnostic views |

Actions are validated against authoritative state, timing, targets and costs.
Checked projections preserve the original state. The live write boundary adds
revision/idempotency coordination and snapshot persistence. Events queue
supported triggers; effects resolve through shared handlers, replacements and
state-based checks. Continuous queries provide effective characteristics without
rewriting printed card facts. SQL stores those facts/results; it does not decide
what an action means. PostgreSQL and multiworker deployment are not certified.

The AI analyzes admitted deck data, enumerates legal actions and evaluates
resources, threats, combat and supported future opportunities. It does not read
unseen opposing hands or hidden library order. Master search can still be slow
and strategically imperfect. Offline mechanic metadata and tournament/deck
priors do not by themselves teach full Oracle semantics or prove play quality.

## Testing

Complete look/reorder instructions support explicit topmost-first ordering and
optional shuffle followed by a replacement-aware draw, as qualified with canonical
Index and Ponder. Choices survive fresh-process restart. AI sees inspected cards,
not the remaining hidden library, and uses known resource/deck priors to choose.
Nonmodal spells cannot substitute client mode text for their printed instructions.
See [library reorder](docs/testing/library-reorder.md) for scope and limitations.

Land and priority-pass training intents validate explicit public fields before
normalization. Supplied land display metadata must match the acting player's
currently offered move; unsupported fields are rejected rather than dropped.
Basic-land views are qualified; special-land metadata remains under audit.
State-based actions check zone and loyalty before querying planeswalker types,
without changing rule ordering or AI search breadth. See
[the query-order checks](docs/testing/sba-planeswalker-query-order.md).

Private library-choice intent handling preserves explicit selections and order
from owned legal views for the audited scry, surveil and look/select families.
Server continuation metadata must match the current pending state exactly;
it cannot be supplied as new client execution instructions. See
[the bounded contract](docs/testing/library-choice-context-correction.md).

**Do not run backend tests against the live checkout/database.** API fixtures
use source-relative SQLite. Run a disposable local copy without a physical
`.git` directory; never execute SQLite on NFS. From the repository root:

```bash
PY="$PWD/backend/.venv/bin/python"
scratch=$(mktemp -d)
git archive HEAD | tar -xf - -C "$scratch"
printf '%s' "$scratch" > "$scratch/.private-choice-audit-source"
(cd "$scratch/backend" && \
  PYTHONPATH="$scratch/backend" MTG_ISOLATED_TEST_ROOT="$scratch" \
  "$PY" -m pytest -q)
```

This tests committed `HEAD`, not uncommitted work. Preserve results before
removing your disposable checkout. Cold child-process probes require the shown
`PYTHONPATH`. Large suites can take substantially longer than a smoke test.
Keep the complete source tree: backend contract checks also inspect frontend
sources. The exact-path marker belongs only in that disposable, Git-free copy;
it does not authorize testing against a live database.

Frontend gates use the external backend interpreter for canonical fixtures:

```bash
export MTG_TEST_PYTHON="$PWD/backend/.venv/bin/python"
cd frontend
npm run lint
npm run build
npm test
```

`npm test` includes API/runtime contracts, mutation/combat selection, manual mana,
mechanic warnings, cycling controls and Suspend checks. Dedicated browser scripts
exercise actual App/HTTP flows in isolated runtimes; use their documented
interpreter/dependency settings. Some scripts need an external Git inventory to
capture source, while isolation-sensitive backend fixtures reject physical Git
metadata in their runtime. Read each qualification's command before execution.

Scoped green gates are not a whole-suite or release certificate. The recent
queued/global/lazy-recovery composition passes all 3,904 checks across its 133
declared complete modules, with no failures, errors or skips; frontend lint,
tests and production build pass with reused installed dependencies. See the
[coupled acceptance record](docs/testing/queued-global-lazy-current.md) for
source preservation, prior failures and remaining release limits.
The recent
declared Python dependency upgrade passes 600 coupled checks across 13 complete
API, private-choice, library, recovery, session, sideboard and image modules.
The refreshed requirements advisory scan is clean; remaining TestClient/httpx
and datetime deprecation warnings are not silently suppressed.
The earlier
six-patch composition passed 2,024 checks across 83 modules. Separate token/cold
classification and trigger-context compositions passed 153 and 123 checks.
Human-flow qualification passed 212 assertions across 16 actual-App scenarios.
Counts overlap and are not independent matches. Fresh declared Python/npm
installation passes the 157 affected backend checks and complete frontend
tests/lint/build; the source-map-js 1.2.2 lockfile has a clean refreshed npm audit.
The older 12,890-check full-suite attempt exceeded its two-hour bound at 85%,
without a terminal summary. Full current-source release acceptance remains open.

For deterministic matrix work, prepare a supported local catalog separately or
supply a pinned deck manifest to `backend/scripts/regression_matrix_replay.py`.
The catalog consumers are read-only. Identified v2 manifests preserve distinct
same-name records; legacy name-only manifests keep their seed convention.
Record seeds, seat ordering, time limits, incomplete games and uncertainty.
A small winning streak is not evidence of balance or seasoned-player strength.

## Card And Deck Development

Card data comes from cached Scryfall/canonical facts and local knowledge.
Syncing/importing data does not implement its rules. Faces, Oracle text, mana,
types, keywords, provenance and images must survive hydration and serialization.
Use the existing compiler/handler for a supported clause; for new semantics, add
a reusable handler or scoped adapter and canonical fixtures. Test timing, costs,
targets, replacements, ownership, privacy and restart through HTTP/UI, not only
helper functions. Report unresolved clauses instead of inventing an effect.

Decklists use counts and card names, for example `4 Lightning Bolt`; optional
sideboards are supported. Import via the UI/API or add a curated template in
`backend/decks/builtin_decks.py`. Validate the genuine inventory and mana base,
then run admitted hydration, analysis and legal-play tests. Labels and template
names are not evidence of tournament strength. Import validation is not a
comprehensive tournament-format/copy-limit judge.

Use `/docs` on the backend for current OpenAPI endpoints. Core surfaces include
`/cards`, `/decks`, `/matches`, `/simulate/batch`, `/diagnostics` and
`/analytics/history`. Active match/job IDs allow local recovery; job cancellation
is cooperative at the next action. Interrupted jobs fail after backend restart,
and partial results must not be reported as completed win rates.

Keep active code/dependencies and SQLite local. Back up SQLite consistently,
including uncommitted/user data separately from Git. Store verified cold logs,
exports and backups on mounted archival storage; GitHub restores committed code,
not user matches or databases. Preserve existing snapshots when deploying and
start fresh matches when comparing newly compiled rule behavior.

## Known Limitations and Next Upgrades

- Canonical audits expose incomplete immediate exile/return compilation,
  missing self-land animation and temporary-control admission, and missing
  independent counter-clause legality in a targeted search sequence. These are
  active generic rules fixes, not supported-card certificates. Current milestone
  gates preserve their strict failures rather than silently skipping them.

- Observed unsupported spell instructions and selected compiler fallbacks reject
  before payment, rather than resolving as successful no-ops. Coverage diagnostics
  identify known gaps; an empty gap list is not certification. Bounded complete
  extra-turn and additional combat/main clauses are supported; other turn-ending,
  player-turn control and unadmitted turn-changing instructions remain unsupported.
  See [admission safety](docs/testing/spell-admission-safety.md).
- Unadmitted shuffle observers/replacements and broader reorder grammars remain
  unqualified; supported Probe/Cosi/Tomb episodes do not certify arbitrary effects.
- Illegal Aura departure LBF bookkeeping, deliberate human legend keeper choices,
  other simultaneous entry batches and full stack-face lifecycle remain open.
- Arbitrary Oracle interpretation, complete layer/replacement interactions,
  uncommon mechanics and all formats are not implemented or certified.
- Paid optional-trigger continuations, Delver's optional private reveal/timing,
  multiple matched cast abilities and remaining small-choice guards are active
  work; see [plan.md](plan.md) for precise acceptance status.
- Post-mana Escape witnesses are not a complete atomic cast-transaction fix.
- Generic-import classification/admission, full corpus application and broader
  face/condition/choice composition still need qualification.
- Expert-level tactical/strategic play, representative seat-balanced matchup
  matrices, long-run replay and credible improvement measurements remain open.
- Interactive AI latency, long-session ergonomics, disconnect/LAN/HTTPS soak,
  accessibility and full current-source release gates remain unfinished.
- Network authorization, worker coordination, storage quotas/retention and
  operational security review are required before broader deployment.
