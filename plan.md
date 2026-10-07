# MTG Deck Testing Lab Finish Plan

Updated: 2026-10-07 UTC. This is the execution index, not a release certificate.
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

- [ ] Repair Ray's independent actual-resolution-controller and superseded
  temporary-control cache bugs. Eight paid copy episodes reproduce two defects;
  two separate paid Dominate episodes expose persistent-control reversion.
  Keep the immutable witnesses and distinguish delayed-trigger priority from
  obsolete first-cleanup expectations. No current HTTP qualification follows.
- [ ] Retain genuine physical source provenance and deliver the actual popped
  resolving frame for Ray copies. A normal-cast receipt alone is insufficient;
  a copied spell remains independent when its original is countered. Shared
  resolver changes require producer/consumer qualification before Ray149.
- [ ] Qualify temporary characteristics through checked HTTP actions and cold
  SQLite restore. Published `7dfbd51` passes seven whole pure modules / 232 checks;
  the separately scoped 40-case HTTP gate remains pending actual execution.
- [ ] Align fixed-cost Suspend readiness with bounded runtime admission and
  canonical context, not a name allowlist. Frozen7f audit: 61 passes / six
  blanket-warning failures; variable costs, unknown layouts/clauses and legacy
  context-free callers remain conservative. Do not declare whole decks ready.
- [ ] Integrate Soul-Scar conversion into affected-player replacement ordering,
  prevention and re-evaluation. Canonical audit: 43 passes / six desired failures.
  Clearing the misrouted warning alone would conceal a real rules defect.
- [ ] Establish complete graveyard clause/zone/permission inventory before
  relaxing conservative combat leaves. Inventory audit: 22 passes / two explicit
  graveyard-activation zone failures; current AI cohort retains 40 strict failures.
  Absence of offered moves is not proof of inertness. Preserve hidden information.

These are distinct frozen audit and current-composition ledgers, not a summed
suite. Soul-Scar and Suspend audits used no SQLite/network; the natural App still
stops at preflight with zero match-start/action requests. Searing Blaze remains
under investigation. No unsupported-warning bypass or natural-game retry is
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
7. [ ] Run clean-checkout offline assets, API/runtime contracts, frontend tests,
   lint/build and the configured browser flow without developer-only cache files.

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
   Intrinsic-mana dual-land combat admission is composed: 225 pure checks pass;
   the 316-case public combat cohort has 276 passes and 40 retained graveyard
   decision failures. No weights/depth or hidden-information policy changes.
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
