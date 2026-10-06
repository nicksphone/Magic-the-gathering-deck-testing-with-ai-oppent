# MTG Deck Testing Lab Finish Plan

Updated: 2026-10-06 UTC. This is the execution index, not a release certificate.
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

These gates overlap. They are not one summed full-suite run, an expert-AI
measurement, live deployment, or universal MTG certification. The historical
plan links earlier hydration, face, actor, replacement, graveyard, combat,
knowledge, replay and frontend milestones without recertifying them here.

## Current Parallel Backend Batch

The workers use immutable published source, disjoint ownership and surgical
patches. Parent composition must preserve newer source and qualify interactions.

1. [ ] Compound source counter costs: integrate fixed positive source +1/+1
   and charge removal with mana/tap costs. Preserve shared readiness, reservations
   and source references; reject unknown composite costs in full. Adapt obsolete
   unsupported-cost characterizations separately; retain genuine search failures.
2. [ ] Generic creature observers: first distinguish already-supported cast
   clauses from missing nontoken entry admission. Preserve copied-spell behavior,
   ability suppression, controller predicates, optional choices and source LKI.
3. [ ] Historical deck provenance: preserve existing IDs/template identities,
   verify historical event records and canonical import facts. Historical success
   is not current format legality or a promise that an old deck is competitive.
4. [ ] Global as-though-flash permissions: implement generic continuous timing
   grants with controller, ability suppression, departure and prohibitions.
   Do not grant extra land plays, off-turn loyalty or override card restrictions.
5. [ ] Targeted library-search compilation: complete anchored instruction
   grammar with explicit targets and existing filters; preserve canonical cards
   and reject unsupported suffixes without partial rewards.
6. [ ] Targeted search resolution: separate original effect controller from
   library/choice owner; private fail-to-find, actual selected-card validation,
   destination/entry handling and genuine shuffle causality through restart.
7. [ ] Compose the completed slices once, run affected whole-module and cross-
   family gates on captured unchanged source, fix failures, refresh docs/Graphify,
   archive verified evidence and publish the qualified milestone.

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
4. [ ] Requalify malformed/stale/wrong-actor requests across new actions with
   full state/controller/SQLite equality on rejection, including failed writes.
5. [ ] Complete refresh, backend restart, ambiguous timeout and manual/autoplay
   overlap acceptance. Reconcile before retry; preserve revisions/idempotency.
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
