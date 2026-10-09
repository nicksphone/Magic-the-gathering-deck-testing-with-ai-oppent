# MTG Deck Testing Lab Finish Plan

Updated: 2026-10-09 UTC. This is the execution index, not a release certificate.
The complete previous plan and its evidence remain in
[historical plan](docs/history/finish-plan-through-b81862a.md). Historical pass
counts belong to their exact source revisions; they do not certify current HEAD.

## Goal And Constraints

Finish a reliable two-player Magic deck tester with real rules, human and AI
pilots, custom and built-in decks, BO3 play, reproducible simulation, canonical
card knowledge and measured seasoned-player AI across deck styles. The original
full rules/arbitrary-deck ambition remains open beyond a bounded local beta.

- Rules, legality, costs, layers, replacements, combat and stack live in code.
  SQLite/PostgreSQL are replaceable storage, never gameplay stored procedures.
- Use complete verified card data and provenance. Never fabricate Oracle text,
  force match winners or tune toward an arbitrary 50/50 matchup expectation.
- Unsupported mechanics must be visible, not silently approximated as supported.
- Work in isolated sources/local SQLite; keep main/live/user data unchanged
  until a separately validated deployment. Archive verified evidence to RCHFiles.
- Test actual actions, choices, responses and restarts; parser recognition and
  passing characterization tests are not proof of correct gameplay.
- Preserve baseline failures, setup errors and timeout ledgers. No hidden skips,
  expected failures or weakened assertions to make a release gate look green.

## Latest Verified Milestones

- [x] Strict sideboard core entry/quantity validation and per-card inventory
  conservation: three whole modules / 49 passes on fresh isolated SQLite.
  Public quantities were already strict; internal coercion is now rejected.
  Seeded native interactive BO3 is qualified in the checkpoint below;
  complete browser games remain open.
  [Scoped acceptance](docs/testing/sideboard-quantity-current.md).
- [x] Shared creature self-tap readiness and effective haste query guard:
  eight whole modules / 277 passes. Separate unchanged canonical Scout/Atlas
  plus decline hook: 48 passes. Scope: [tap readiness](docs/acceptance/tap-source-readiness-20261006.md).
- [x] Private optional hand-land selection/decline, supported paid optional
  trigger costs, retained source self-pumps and generic hand-land ramp roles:
  27 complete modules / 800 passes, 390.20s, plus a separate whole-view audit
  of 25 passes. Frontend tests/lint/build pass. Scope:
  [shared composition](docs/testing/optional-paid-current-composition.md).
- [x] Unchanged supplemental bare-helper and actual paid-cast HTTP regression:
  eight passes, 18.78s; cold restart and atomic immediate sick-tap rejection.
  Scope: [HTTP supplement](docs/testing/activated-handland-paid-sickness-supplement.md).
- [x] Supported nontoken entry observers, unconditional global flash permission
  and deck-identity opening-quality metrics: ten whole modules / 293 passes,
  60.41s. [Current composition](docs/testing/observer-flash-simulator-current-composition.md).
- [x] Fixed source counter costs and supported complete targeted basic-land
  searches: 22 whole modules / 749 passes, 85.34s; separate prior-feature gate
  293 passes, 56.61s; frontend checks pass.
  [Current search composition](docs/testing/counter-targeted-search-current-composition.md).

These gates overlap. They are not one summed full-suite run, an expert-AI
measurement, live deployment, or universal MTG certification. The historical
plan links earlier hydration, face, actor, replacement, graveyard, combat,
knowledge, replay and frontend milestones without recertifying them here.

## Current Parallel Backend Batch

The workers use immutable published source, disjoint ownership and surgical
patches. Parent composition must preserve newer source and qualify interactions.

1. [x] Compound source counter costs: integrate fixed positive source +1/+1
   and charge removal with mana/tap costs. Preserve shared readiness, reservations
   and source references; reject unknown composite costs in full. Adapt obsolete
   unsupported-cost characterizations separately; retain genuine search failures.
2. [x] Generic creature observers: first distinguish already-supported cast
   clauses from missing nontoken entry admission. Preserve copied-spell behavior,
   ability suppression, controller predicates, optional choices and source LKI.
3. [x] Historical deck provenance: preserve existing IDs/template identities,
   verify historical event records and canonical import facts. Historical success
   is not current format legality or a promise that an old deck is competitive.
4. [x] Global as-though-flash permissions: implement generic continuous timing
   grants with controller, ability suppression, departure and prohibitions.
   Do not grant extra land plays, off-turn loyalty or override card restrictions.
5. [x] Targeted library-search compilation: complete anchored instruction
   grammar with explicit targets and existing filters; preserve canonical cards
   and reject unsupported suffixes without partial rewards.
6. [x] Targeted search resolution: separate original effect controller from
   library/choice owner; private fail-to-find, actual selected-card validation,
   destination/entry handling and genuine shuffle causality through restart.
7. [x] Compose the completed slices once, run affected whole-module and cross-
   family gates on captured unchanged source, fix failures, refresh docs/Graphify,
   archive verified evidence and publish the qualified milestone.

Checked items are complete only for the scoped families in their linked
acceptance reports. Conditional timing/observer grammar, arbitrary search/cost
clauses and broader source-departure/continuation episodes remain open. Catalog
provenance and canonical seed now have current scoped acceptance in
[catalog composition](docs/testing/catalog-canonical-seed-current-composition.md).
Full corpus, lifecycle and release acceptance remain unfinished.

## Next Backend Batch

### Current Evidence-Driven Priorities

- [x] Repair Ray's actual-resolution-controller and superseded temporary-control
  cache bugs; retain physical announcing provenance separately from the actual
  popped copied-spell frame. Current composition passes 199 pure checks, then
  322 checks across 17 whole isolated-SQL modules and 12 dedicated HTTP cases.
  The eight actual desired copy cases pass unchanged. Preserve delayed-trigger
  priority, counterability and immutable historical ledgers. The later corrected
  Ray149 v6 gate passes all 149 checks on its separately pinned component; it is
  not a qualification of the current full backend. General control layers and
  full browser games remain open.
  [Current acceptance](docs/testing/control-source-frame-current-composition.md).
- [x] Qualify bounded temporary characteristics through checked HTTP actions and cold
  SQLite restore. Published `7dfbd51` passes seven whole pure modules / 232 checks;
  the exact parent source-only HTTP copy passes all 40 checks, including eight
  cold-process continuations and actual native-turn mana activation. Broader
  layers/copies remain open. [Current acceptance](docs/testing/suspend-and-characteristics-http-current.md).
- [x] Align bounded fixed-cost Suspend readiness with runtime admission and
  canonical context, not a name allowlist. Frozen7f audit: 61 passes / six
  blanket-warning failures; variable costs, unknown layouts/clauses and legacy
  context-free callers remain conservative. Current composition passes four whole
  modules / 136 checks. Do not declare whole decks ready or general Suspend complete.
- [x] Execute bounded printed exile time-counter bodies independently of the
  Suspend keyword: canonical Aeon draw and Detritivore land destruction use real
  trigger priority, targeting and retained object references. Parent current-source
  acceptance passes 403 cases across 17 whole modules, preserving graveyard-cast
  receipts. Multi-counter removal, unknown clauses/layouts, HTTP and whole-card
  readiness remain open. [Acceptance](docs/testing/exile-counter-current.md).
- [x] Integrate bounded canonical Soul-Scar conversion into affected-player
  replacement ordering, prevention and re-evaluation. Current source-controller,
  numeric-prevention and heroic union passes 1,133 checks across 46 whole modules,
  including original replacement/query and hydrated preflight action witnesses.
  Complete-clause diagnostics and native damage-source validation are included;
  this is not arbitrary replacement-clause or browser-game certification.
  [Current acceptance](docs/testing/source-controller-heroic-current.md).
- [ ] Establish complete graveyard clause/zone/permission inventory before
  broader relaxation of conservative combat leaves. Current bounded inventory,
  canonical self-return and public combat cohorts pass 323 checks across four
  whole modules; the older zone and 40-failure ledgers are historical, not current
  defects in this cohort. Arbitrary clauses, layouts and AI strength remain open.
  Absence of offered moves is not proof of inertness. Preserve hidden information.
  [Current acceptance](docs/testing/graveyard-combat-current.md).

These are distinct frozen audit and current-composition ledgers, not a summed
suite. Soul-Scar and Suspend audits used no SQLite/network; the natural App still
  stops at preflight with zero match-start/action requests. Searing Blaze has
  [actual paid-entry witnesses](docs/testing/linked-damage-real-land-entry.md):
  four whole current modules / 146 passes; broader admission/copy/target coverage
  remains under investigation. No unsupported-warning bypass or natural-game retry is
authorized by these scoped repairs.

1. [x] Qualify phase-aware tactical combat scoring against actual checked
   damage/winners, preserving response and crackback uncertainty. Tactical
   fixtures are not a natural-game strength measurement.
   Scoped animation composition: 64 focused passes; natural previous-stage
   actions remain identical. Broader blocking/crackback planning stays open.
2. [ ] Audit and implement canonical land-animation admission and continuous
   characteristics, including summoning sickness, cleanup and source incarnation.
   Product and real Cloudshift reentry execute. Complete single-target
   nontoken-permanent Flicker now passes 78 core/HTTP cases in the current
   whole30 composition. Ghostly Flicker's two-target body remains unsupported;
   old exile-only and empty-pool characterizations require separate reconciliation.
   [Current scope](docs/testing/animation-strategic-current-composition.md).
3. [ ] Verify targeted search source departure/reentry and partial target loss
   through actual response spells, private choices and cold restart.
   Supported ordinary activation/bounce reference retention is now qualified;
   [current acceptance](docs/testing/retained-reference-current-composition.md).
   Immediate exile/return and independent clause binding now execute in the
   [current stage](docs/testing/blink-clause-exporter-current-stage.md). Shared
   announced-target identity now closes four original Favor blink cases and
   two Act blink cases unchanged. Current whole30 integration executes 730 cases,
   including all 62 Favor lifecycle/HTTP/clause checks passing. Browser,
   Ray of Command and dedicated activation paths
   remain open; see [target acceptance](docs/testing/announced-target-current-composition.md).
4. [x] Audit full 155-record seed regeneration for non-lossy canonical and
   approved derived facts, without weakening the historical 119-record fixture.
   Eight whole modules / 194 passes; real CLI idempotence and unchanged SQL.
   Cross-file interruption/recovery remains separate release work.
5. [x] Resume deterministic natural play only after storage checks; preserve
   failed resource-exhaustion runs separately from gameplay outcomes.
   Before/after seat-swapped replay has zero deterministic failures; all 2610
   recorded action entries are identical. No AI-strength improvement is measured.

## Gate 1: Reliable Local Human Playtesting

Existing implementations have scoped evidence in the historical plan. Remaining
items below require current-source acceptance, not another rewrite of working
features or claims based on helpers alone.

1. [ ] Requalify canonical hydration/views across live API, sideboarding,
   simulation and replay. Faces, effective stats/keywords, counters, damage and
   characteristic values must agree with combat and survive reload/restart.
2. [ ] Complete interacting draw/discard replacement, cleanup, repeat-cleanup,
   trigger-order and human replacement-choice fixtures through actual HTTP/UI.
3. [ ] Complete full human-vs-human and human-vs-AI browser games: both seats,
   mulligans, ordered bottoms, phases/priority, target/face/mode/resource choices,
   activated/crew/equip/zone plays, combat, cleanup and game completion. Every
   supported action must be reachable; unsupported controls must warn explicitly.
   One normal actual-App attempt with Mono Red Aggro versus Burn stopped at
   support preflight: Soul-Scar Mage counter replacement, Rift Bolt suspend,
   and Searing Blaze linked targets/conditional land-entry damage were flagged.
   There was one preflight POST and no match/action POST; no warning bypass or
   complete-game claim. Trace coverage classification against engine semantics
   and close the real gaps before repeating that acceptance path.
4. [ ] Requalify malformed/stale/wrong-actor requests across new actions with
   full state/controller/SQLite equality on rejection, including failed writes.
5. [ ] Complete refresh, backend restart, ambiguous timeout and manual/autoplay
   overlap acceptance. Reconcile before retry; preserve revisions/idempotency.
   Published checkpoint browser evidence covers refresh, a lost accepted HTTP
   response, duplicate land intent and real backend restart. Manual/autoplay,
   full natural human games and broader restart paths remain acceptance work.
6. [ ] Verify seeded interactive BO3 transitions, loser play/draw selection,
   sideboard inventory and restart parity. Implement deliberate AI sideboarding
   or label it unavailable, never silently substitute an untested policy.
   Current441 native/API acceptance now passes eleven whole modules / 100
   cases, including real three-game human series, deliberate different-card
   swaps, play/draw readiness and cold restoration. Controls callbacks and
   frontend checks pass; actual browser series and broader policy strength
   remain open. See `backend/docs/testing/human-bo3-readiness.md`.
7. [ ] Run clean-checkout offline assets, API/runtime contracts, frontend tests,
   lint/build and the configured browser flow without developer-only cache files.
   Current441 cold ASGI fallback qualified all 155 shipped names without
   network access, followed on the same database/cache by eight whole warm
   modules / 73 passes. Prior pinned-source harness failures remain immutable.
   See `docs/testing/offline-assets-cold-component.md`. Later compositions,
   actual browser/proxy fallback and full clean-checkout release remain open.

Exit: reliable supported-card local human games and BO3/recovery work through
actual UI/API, with no silent legal-action gaps or unexplained internal errors.
UI redesign is later; functional access to backend choices is not optional.

## Gate 2: Rules, Knowledge And Competitive AI

1. [ ] Maintain a provenance-backed supported corpus with faces, rulings,
   legalities, image/token metadata and explicit mechanic/effect-clause gaps.
   Complete all-card sync/cache coverage separately from semantic certification.
2. [ ] Expand reusable effect/ability handlers and modular unusual-card support.
   Verify static/triggered/activated abilities, replacements and prevention,
   continuous layer/timestamp/dependency fidelity, can't overrides, ownership,
   incarnation/LKI, simultaneous events and durable choice continuations.
   Admitted temporary creature-characteristic bodies and effective subtype
   readers now pass 232 pure checks on the current composition. Printed data,
   counters, real paid spell/response outcomes and cleanup/reentry are covered;
   actual HTTP/cold SQLite qualification remains outstanding.
   Next observed corpus seams: noncombat damage-to-counter replacement,
   suspend/free-cast continuations, and controller-linked conditional damage.
   Preflight flags are evidence of admission gaps, not by themselves proof of
   failed effect execution; canonical action goldens must establish each cause.
3. [ ] Expand canonical fixtures for combat/protection/landwalk/multiple blockers,
   damage/deathtouch/trample/first strike, bands, mana and restricted costs,
   legendary/planeswalker rules, tokens, graveyard/exile/library interactions,
   alternative win/loss, empty-library draws and uncommon historical mechanics.
4. [ ] Make knowledge affect production AI decisions and trace why. Validate
   actual decisions across aggro, burn, midrange, control, tempo, ramp, drain,
   aristocrats, reanimator, tokens, tribal, combo and interaction-heavy decks.
5. [ ] Improve combat/racing, blocking, resource reservations, removal/counter
   timing, threat assessment, mana efficiency, mulligans, dynamic faces and
   multi-turn planning. No blind attack, power-zero or named-card policy fixes.
   Intrinsic-mana dual-land combat admission is composed: 225 pure checks pass.
   The historical 316-case cohort retained 40 graveyard decision failures.
   Current schema drift was reproduced in four whole modules / 323 cases as
   269 passes and 54 failures. Explicit reviewed metadata coverage now passes
   all 323 unchanged cases plus 104 new boundary controls (427 total), without
   weights/depth or hidden-information policy changes. Natural-game strength
   and final composed-source qualification remain open; see
   `docs/testing/public-graveyard-reviewed-context.md`.
6. [ ] Define decision-quality benchmarks and before/after comparisons under
   hidden information. Training/data tooling needs legal-action traces, causal
   anomalies and evaluation; storage or a neural net alone does not prove skill.
7. [ ] Run predeclared seed/seat-balanced archetype matrices with full hand/board
   and decision traces, uncertainty intervals, timeout/deck-out policy and
   first-diverging replay diagnostics. Verify API/simulator/restart parity.

Exit: no unexplained cost/target/rules stalls in the declared supported corpus,
reproducible replay, and measured AI decision improvement across deck styles.
Continue expanding toward full rules and arbitrary-deck seasoned-player strength;
the supported-corpus exit does not redefine that larger goal as achieved.

## Gate 3: Packaged Release And Operations

1. [ ] Requalify actual built HTTPS API/media routing and explicit cross-origin
   configuration, then trusted-certificate LAN deployment on supported topology.
2. [ ] Document/enforce local single-user/single-worker limits. Before broader
   exposure, add authorization, restricted origins and measured resource limits.
3. [ ] Complete bounded job admission/queues, cancellation, byte/row retention,
   crash/restart recovery and stale concurrent mutation acceptance. Existing
   single-process controls are not distributed-worker certification.
4. [ ] Review current frontend/backend dependency advisories and compatible
   upgrades; run clean installs, dependency consistency/security checks and gates.
5. [ ] Verify clean-machine install, offline fallback, backup/restore, saved-game
   reconstruction, long-session browser soak, accessibility and actionable errors.
   Two-output seed export needs explicit restart recovery: the real 12-case
   fault audit has eight passes and four immediate-publication failures. A local
   rollback-journal/recovery implementation now passes 245 checks across ten
   modules, preserving original bytes without source inputs and refusing
   altered outputs. Real SIGKILL/new-process recovery is covered. Recovery is
   not atomic two-file visibility, and the stricter historical failures remain.
6. [ ] Reconcile features/limitations with current source, record changed files,
   checks, evidence, risks and manual review; publish and deploy only after the
   appropriate gates pass. Git pushes alone are not running-server updates.

## Completion Checklist

Current component evidence and remaining acceptance work are reconciled in
`docs/testing/release-acceptance-status.md`. Natural native browser BO3 and the
browser-origin security component have passed on their documented source pins;
neither result qualifies the final combined source or closes all three gates.

The current pending-stack privacy integration has an exact 22-whole-module pure
qualification of 950 passes on the `db16186` composition, with applied-byte
equality. See `docs/testing/pending-stack-privacy-current.md`; mixed HTTP/SQL,
complete private hand-to-library responses and final release remain open.

Current native next-cast and entry-counter integration has one 36-whole-module
834-pass qualification on the composed `91c40e2` application baseline. Parent
applied bytes match the actual tested archive. See
`docs/testing/native-entry-current.md`; copied-bind, broader native APNAP,
historical aggregate diagnostics and full release acceptance remain open.

- [ ] All current batch items and all three release gates have authoritative
  evidence for their declared scope, on the actual composed source.
- [ ] Builds/runs succeed and no obvious broken page, action or data flow remains.
- [ ] Manual full-game/LAN/accessibility review and remaining risks are recorded.
- [ ] Original broader all-rules/arbitrary-card/expert-AI objectives are proven,
  or explicitly remain unfinished; do not mark the overall project complete
  merely because the scoped local release is finished.

## Known Limitations and Next Upgrades

Alpha, bounded card semantics and heuristic AI. Full rules coverage, arbitrary-
card correctness and seasoned-player strength are not established. Current
backend work takes priority over cosmetic UI changes. Full-suite, browser/LAN,
long-session, dependency/security and statistical AI acceptance remain open.

## 2026-10-07 Pull and Mass-Exile Checkpoint

Scoped current-base composition repairs mass-exile incarnation/PRE-leave lifecycle
and admits complete Pull from Eternity with retained native frames and explicit
owner replacement continuation. Same-source 26 whole modules: 524 passes; see
`docs/testing/pull-mass-exile-current.md` for evidence and guard limits. Existing
numeric-prevention transport is preserved. This is not a live deployment or a
full backend/game/AI release gate; the completion checklist remains open.

## 2026-10-07 Source-Controller and Heroic Checkpoint

Current-base composition adds complete source-controller counter-conversion
clauses, correct spell/ability replacement-query controller projection, early
native damage-frame validation, closed-instruction preflight diagnostics and
actual-reference heroic cast-target recognition. Same-source 46 whole modules:
1,133 passes in 302.49 seconds; original assertions unchanged. See
`docs/testing/source-controller-heroic-current.md` for the earlier harness-only
failure ledger and isolation limits. No live deployment or broader release
completion is claimed; the completion checklist remains open.

## 2026-10-07 Locked Frontend Checkpoint

Fresh isolated locked install, complete configured npm test chain, lint and build
pass on application source `6f9e29e`; full and production-only advisory scans
report zero findings. The missing Python prerequisite on the first attempt is
preserved separately, not treated as an application failure. See
`docs/testing/frontend-locked-current.md`. Backend offline assets, actual browser
games, BO3/recovery and deployment remain open; this does not close Gate 1.7 or
Gate 3 in full.

## 2026-10-07 Fable Linked-Discard Checkpoint

Complete optional self-discard/up-to-N/If-you-do draw-that-many instructions now
reuse the existing private selected-count continuation, including the full Saga
chapter envelope used by admission checks. Parent isolated published-source
qualification: five whole pure modules, 92 passes in 96.18 seconds, with source
hashes unchanged during execution. See
`docs/testing/fable-optional-linked-discard-current.md`. HTTP/SQLite/browser,
Reflection's copy ability and broader release gates remain unverified here.

## 2026-10-07 Native Type-Note Control Checkpoint

The existing mechanic button route now exposes explicit offered creature-type
choices for both seats. Actual backend public views and React-rendered callbacks
pass the configured frontend test chain, typecheck, lint and production build.
See `docs/testing/native-type-note-controls.md` for the fixture failure ledger
and scope. This closes the identified control-routing gap, not manual browser,
full-game, BO3, copied-bind/APNAP or overall release acceptance.

## 2026-10-07 Pinned Offline Warm Checkpoint

The preserved `6f9e29e` backend now has an independently checked eight-whole-
module warm result: 73 passes, exact original node identities, 23 paired
lifespans, strict runtime stub provenance and quiet resource closure. Earlier
cold and failed warm ledgers remain distinct. See
`docs/testing/offline-assets-cold-component.md`. This does not close current-
source offline/browser fallback, full Gate 1.7 or overall release acceptance.

## 2026-10-07 Resource-Scaled P/T Checkpoint

Current native-backend composition now admits the complete named-artifact-token
resource-scaled debuff and resolves its count after actual responses. Five whole
pure modules passed all 103 cases in 81.81 seconds; applied product/dependency
bytes match the tested source and native bindings remain intact. See
`docs/testing/resource-scaled-pt-current.md`. The mixed HTTP neighbor cohort,
broader variable P/T families, browser and full release remain unqualified.

## 2026-10-08 Fresh Runtime And Natural-Game Checkpoint

Fresh isolated installation on immutable `9f50190` completed the configured
frontend checks and the unchanged thirteen-whole-module backend AI/entry cohort:
655 passes in 234.43 seconds. Installation, exact wheel/lock provenance and
native pure-gate closure are recorded in
`docs/testing/current9f-fresh-dependency-runtime.md`. Fresh mixed SQL/ASGI,
HTTPS, browser and clean-machine deployment are still separate acceptance work.

Four predeclared White/Tempo natural games on immutable `349a5d2` completed with
2,832 checked decisions and 8,496 verified checkpoints. All four rows use one
correlated seed; one existing bad-block diagnostic remains recorded. Its four
checked immediate-combat alternatives do not establish strict domination; see
`docs/testing/current349-block302-causal-review.md`.
See `docs/testing/current349-white-tempo-natural-four.md`. These rows do not
establish thirteen-style, multi-seed or expert-strength acceptance.

Published `1c3fbbd` repairs the App response-window prerequisite to use the
actual human controller rather than seat 1. The actual-source 36-check regression
and candidate frontend checks pass. Live both-seat countdown/pause/pass behavior
still needs affected browser qualification; see
`docs/testing/human-response-controller-role.md`. None of these components closes
the full release gates or the original full-rules/arbitrary-deck objective.

## 2026-10-08 Fresh HTTPS Checkpoint

Immutable `1c3fbbd` with the exact tested frontend build completed actual
owned-CA loopback HTTPS/auth/Origin/API/media/lock/restart qualification on the
restored fresh runtime. All 205 reported instances pass: the same 111 stable
contract instances as the older gate plus 94 process-identity polls. Independent
source, dependency and native resource closure verified the slot release. See
`docs/testing/current1c-fresh-https-qualified.md`. Live browser, trusted LAN,
clean-machine deployment and the full release gates remain open.

## 2026-10-08 Complete Printed-Body Composition

The isolated composition over `6c5c62b` passes 823 checks across 22 whole modules;
all 400 original corpus/consumer cases pass unchanged. Shared cast preflight now
rejects unsupported complete bodies before payment, and shipped loyalty ability
availability is restored through complete instruction compilation. Raw energy,
Aura, land-setting, untap-preview and target-fizzle fixes compose together.
Separate resolution/entry neighbors pass 179 checks across seven whole modules.
See [scope and historical ledgers](docs/testing/complete-body-rules-composition.md).

Ten historical loyalty fixtures assumed unsupported casts would succeed; their
unchanged early-rejection ledger is preserved separately from the strengthened
repository checks. General hand-entry/Aura/land-choice interactions and public
emblem visibility are explicit follow-ups. Full browser acceptance, arbitrary
cards, expert AI and all three original release gates remain open.

## 2026-10-08 Locked Dependency Advisory Refresh

Exact published `bf6731c` Python/frontend locks were queried against OSV at
23:24:27 UTC: all 28 PyPI and 214 npm unique locked versions, including optional
platform packages, returned no affected package. Exact inventory, input hashes,
response cardinality and absent pagination were independently verified. See
[the advisory scope and evidence](docs/testing/current-locked-dependency-advisories.md).
This changes no dependency and does not replace final-source clean installs,
runtime gates, application security review or deployment qualification.

## 2026-10-08 Loyalty Entry And Public Emblems

The current-source composition over `8b2078c` executes 31 whole backend modules:
1,003 passes in 183.20s. Pytest exits zero; the wrapper's separate inventory
assertion exits one for four generated SVG cache appends, with every original
inventoried source path unchanged. Exact output hashes and the failed wrapper
ledger remain preserved. Complete configured frontend test/lint/build exit zero.
Actual paid Ugin land/Aura/planeswalker entry and public command-zone emblems
now have existing-pattern human selection/display controls, strict response
validation and both-seat component checks. See
[the scope, ledgers and remaining work](docs/testing/loyalty-entry-emblems-current.md).
No HTTP/browser, arbitrary entry rules, expert AI or final release gate is
certified by this scoped composition.

## 2026-10-09 AI Loyalty And Replay Input Safety

Composition over `9d519b5` passes the same 13 declared whole modules: 392 passes
in 62.19s. Actual AI uses live offered loyalty card/Aura references and the
correct distinct choice fields. Replay artifact paths reject equal, symbolic
and hard-linked aliases before simulation or evidence creation. The corrected
baseline reproduced 15 unsafe alias cases; the first combined run's 26 denied
repository-fixture setups remain archived separately. Only declared owned SQL
fixtures were subsequently admitted, with source equality and physical closure.
See [scope and evidence](docs/testing/ai-loyalty-replay-artifact-safety.md).
This is conservative legality and artifact protection, not optimal AI,
13-archetype natural-match evidence or completion of any original release gate.

## 2026-10-09 Bounded Spells And Entry Strategy

Current composition over `9b86ca2` passes 30 whole modules / 981 cases in
177.82s, retaining the original 400 corpus/consumer nodes and assertions.
Full frontend test/lint/build passes. Complete bounded removal uses retained
target references; malformed linked/X-token bodies reject before payment even
with embedded unknown parentheses or leading whitespace. Human target drafts
respect the offered maximum and clear stale scalar fields. Actual AI compares
known Aura-entry and decline outcomes at the same completed stack boundary.
See [scope and preserved baselines](docs/testing/bounded-spells-and-entry-strategy.md).
This does not certify alternative pitch costs, noncreature copy/retarget paths,
full browser acceptance, maximum-width planner latency or seasoned-player AI.
All original release-gate requirements remain unchanged and open.
