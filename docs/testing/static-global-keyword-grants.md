# Static Global Creature Keyword Grants

Qualified base is exact `0a50a16b515e1478bdf0964a62f4b0231f08bdac`, not current
4ebcd5f or a scheduler/shuffle composition. Production scope is only
`backend/rules_engine/continuous.py`, seven inserted parser lines. No API,
AI, schema, zone, cost, metadata, provenance-field, cache, or group-handler
change is included.

## Semantics

The new route matches a complete unconditional clause of the form
`[All] creatures have <supported keywords>`. The whole instruction is parsed
with the existing strict `_attached_keywords` helper. Unrecognized residual
text does not become a partial recognized keyword. Existing static-text
filtering excludes activated, triggered, conditional, and temporary effects.
Controller-qualified routes remain unchanged.

Descriptors reuse scope `all`, the existing creature-subject check, active
battlefield sources, and source timestamps. Membership is queried dynamically:
both players' current creatures are included, including late entrants. A
source leaving removes its grant. Reentry gets a new existing incarnation and
timestamp; no per-recipient static record is created by a query.

Actual Ovinize resolution receives a later removal timestamp than an earlier
source, so protection is removed. A later reentered source then grants it
again. Cleanup removes Ovinize's temporary effect, not the static ability.
Temporary Heroic Intervention/Boros Charm group handlers retain their existing
resolution-locked membership and cleanup behavior. Immutable query-local
caches are reused; no persistent cache or invalidation mechanism is added.

## Qualification

The unchanged original desired module has 54 ordinary PASS after the fix,
versus 54 strict ordinary failures on the frozen audit. The original 14 whole
neighbor modules have 232 ordinary PASS. Twelve additional canonical controls
cover Mass Hysteria's paid global haste, both source seats and both attacking
seats, actual normal phase/turn progression, late creatures, checked attacks,
Disenchant departure, cached/uncached parser parity, Levitation's unchanged
controller-qualified flying, and Wonder/Bedlam clause boundaries.

Absolute Law/Grace contracts use full unchanged canonical raw objects and
cover both players, source casts, late entrants, source leave/reentry, actual
Ovinize, cleanup, targets, damage, blockers, Auras, black and colorless
Equipment, actual paid equip legality, HTTP atomic rejection, and durable
repository recovery. The audit's positive controls verify actor-private
views, hidden-order invariance, root/RNG purity and exact snapshots; their
original historical module remains archived unchanged rather than promoted
as a release module.

All test databases are synthetic and local. Actual HTTP here means in-process
production routes and repository restart, not a two-process or live service
qualification. Final whole-module results and exact source manifests are in
the accompanying archive report.

## Historical Diagnostic Transition

The original audit's `test_static_global_keyword_observations.py` is preserved
byte-for-byte. Its missing-grant/parser-empty assertions encode the old defect
and are intentionally NOT included in the release dependency patch or gate.
No assertion has been weakened or silently removed. If that diagnostic module
is ever promoted, review those historical expectations explicitly. The 54
desired rules contracts are unchanged and included in the release patch.

## Limits

Phasing is an explicit unsupported mechanic in this baseline, with no runtime
phased-out state or transition. This parser correction does not fabricate
phasing or certify its interaction. That needs separate ownership of actual
phasing state and transitions before an execution claim is possible.
Controlled source reentry is a zone/incarnation seam, not a claimed legal blink
or reanimation. Damage includes direct real effect-primitive coverage, not an
invented paid untargeted spell. Unrecognized global subjects, arbitrary granted
Oracle abilities, continuous-effect dependencies, and complete corpus support
are not certified. Metadata readiness remains distinct from execution support.

Rules basis is the archived official CR20260925: 611.2c, 611.3a-c, 613.7a-b/d,
and 702.16b-f. Fixture provenance retains full unchanged canonical objects and
saved corpus source hashes/lines, not invented names or Oracle text.
