# AI Public Mana Changes

## Implemented Scope

The AI pays and resolves supported basic-land type-changing spells and land
plays on disposable state before valuing their resource effects. The comparison
uses the shared mana planner, known own hand costs and public battlefield,
graveyard and face-up exile footprints. It does not read opposing hands or
libraries. Face-down exile is excluded for both players: ownership is not a
look permission. The subsequent Foretell foundation supplies explicit look
permissions, but this resource evaluator still excludes face-down exile pending
alternative-cost-aware integration.

Pure fixing/disruption spells are retained when their measured benefit is too
small or negative. They are reconsidered each decision as known resources
change. Creature bodies are not discarded by that pure-fixing filter. Aura
targets use actual paid resolution and resource changes; type-changing lands
are compared with ordinary land alternatives, not scored in isolation. The
same agent is used by live autoplay and simulation. Decision-local caching does
not survive mutation, reload or another decision.

Generic capacity probes are capped at eight; color and independent known-cost
probes are heuristics, not a claim that every cost can be paid together. The
ready-board comparison clears pools and restores readiness without advancing a
turn. It does not predict untap restrictions, future draws, cleanup expiry,
unknown replacements, future land drops or adversarial responses. Known X costs
are not valued by the new hand-access term. Alternate-face/permission planning
and weight calibration remain open.

Unknown choices, changed libraries, opposing-hand changes or unresolved
projections do not establish a resource outcome. The canonical Spreading Seas
check exposed missing self-entry subject aliases; Aura and Equipment (and other
self-reference subjects) now share the entry matcher. Actual Seas casting emits
and resolves its draw. Matching Giant's Amulet's self-entry subject alone does
not certify its optional payment/token clause or the whole card.

Quoted token entry abilities are excluded from the creator's entry matching,
without deleting their text from effect parsing. Canonical Dragonbroods' Relic
and Outlaws' Merriment exposed six false creator-entry regressions.

Supported standalone fixed draws at the next turn's upkeep now create durable,
one-shot delayed triggers instead of drawing immediately. Aura entry and instant
resolution share scheduling, normal priority, countering and snapshot recovery.
Fevered Strength retains its immediate printed pump, and spell copies schedule
independent draws. Vampirism's nonrecipient penalty no longer reduces its own
enchanted creature; effective stats and layer traces share that reference.
This does not implement arbitrary delayed instructions or upkeep conditions.

## Canonical Data and Honesty

Tests reuse canonical land, cost, scaling and mana fixtures. Two fresh Scryfall
records, Saw It Coming and Behold the Multiverse, are normalized in
`backend/tests/fixtures/public_foretell.json`; raw responses accompany evidence.
They are hidden-exile snapshot fixtures, not evidence of a Foretell action.
Foretell actions, later-turn costs/permissions and look permissions are still
unimplemented and now explicitly diagnosed as unsupported. Public-exile tests
use full canonical cards instead of relabeling Island instances.
Additional fresh canonical fixtures cover the two quoted-token creators and
Fevered Strength. Vampirism reuses the existing canonical scaling fixture;
its current Oracle text was checked against a fresh Scryfall response too.

## Checklist

- [x] Reproduce 80 harmful Moon casts, 84 redundant-fixing casts and 84 inferior
  shared-fixing land choices on the published base; preserve 84 useful choices.
- [x] Check both seats, all fourteen styles and Casual/Strong/Master decisions.
- [x] Fix shared public resource valuation, actual Aura targets and comparable
  land alternatives; actual casts/resolution, HTTP autoplay and SQLite restore
  pass focused acceptance.
- [x] Reproduce missing canonical Aura/Equipment self-entry matches and Seas
  draws; repair the shared event matcher and check original-object identity.
- [x] Correct the new evaluator's face-down-exile leak before final acceptance;
  verify private-state changes, restored snapshots and explicit Foretell warning.
- [x] Pass 550 expanded checks against the privacy/quoted-entry correction and canonical
  public-exile fixtures. Failed setup assertions and superseded runs are retained.
- [x] Reproduce ten timing/recipient failures on the published base; pass 131
  delayed-draw, Aura, combat-keyword and spell checks on the corrected engine.
- [x] Correct missing Oracle metadata handling; pass 504 focused AI, public
  resource and delayed-draw checks. Rerun frozen final-source acceptance below.
- [x] Pass all 6,134 backend tests across four final-source isolated
  source/database shards: zero failures, errors or skips; 279 files run once.
- [x] Pass frontend lint/contracts/build and the complete final-source browser
  harness. The pre-exile-correction harness passed but is not final acceptance.
- [x] Complete six-archetype replay: two seeds per pair, both seats, each
  repeated twice; 60 logical samples/120 executions, BO1, 2,400-tick cap.
  Pair jobs use four isolated source/database workers with verified identical
  seed schedules. The initial serial checkpoint is retained as partial evidence,
  not a completed additional sample or a resumed run.
- [x] Inspect all 60 samples: every series resolves, zero timeouts, anomalies
  or determinism failures. All fifteen pair sources match final source bytes;
  canonical data parity is verified for five fresh records and Vampirism.
- [x] Refresh Graphify and archive/verify closed acceptance evidence on NFS.
  Publish this verified milestone; retain the publication receipt with evidence.

Completed evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ai-public-mana-changes/20261004-working/`.
Active scratch and SQLite databases stay local. Dependency environments are
reused, not installed fresh. A passing small controlled decision matrix is not
expert-AI, statistical balance or arbitrary-card certification.

## Known Limitations and Next Upgrades

Calibrate resource weights and action opportunity costs, account for immediate
versus retained readiness/entry life payments, broaden complex source removal
and control decisions, and plan competing future actions under public response
likelihoods. Implement Foretell with durable costs, timing, permissions and
hidden-information ownership rather than assuming exile visibility suffices.
The deferred alpha UI redesign and broader release gates remain unfinished.
