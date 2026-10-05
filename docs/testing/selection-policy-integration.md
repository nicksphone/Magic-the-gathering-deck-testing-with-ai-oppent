# Paid Selection And Simulator Action Integration

## Production Policy

The agent consumes the generic paid-selection plan during ranking, strategic
horizons, interaction reservation and proactive anti-stall conversion. A
reconciled own-deck inventory supplies a fractional probability of acquiring
one eligible card, not a hypothetical known card or legal future play.

Verified zero-hit inspections cannot receive a flat draw bonus or forced
anti-stall activation. Missing, inconsistent or conditioned inventories remain
unknown: they retain the existing heuristic fallback rather than being treated
as zero hits. That fallback must not override known interaction reservation.
The first parent run found this distinction missing; the repaired policy has
explicit both-seat regression cases, without changing existing card data.

Only complete, engine-admitted clauses are evaluated. Recruitment Officer is
qualified; Duskwatch Recruiter and transformed Azcanta are explicit unsupported
witnesses pending separate engine work. Generic recognition does not certify
all paid selection abilities.

## Unknown Selection Projections

Supported whole-clause unfiltered look/hand/bottom/exile effects can contribute
opaque hand counts and count-only exile opportunities to planning. Their
unknown exile placeholders have executable permissions removed on the planning
copy only. Known-card/root permissions remain authoritative and unchanged.
No unknown card is fabricated or treated as a playable spell.

This resolves a projection gap, not every Tempo ranking problem. The previously
retained Expressive Iteration positions still need strategic evaluation; having
one hand acquisition and an exile opportunity does not require casting when
the remaining line ranks below passing.

## Simulator Action Boundary

`AnalyticsService.run_batch`, `run_ai_diagnostics` and deterministic replay use
the shared complete-action conversion and copy-on-write `checked_action`.
Malformed or illegal AI actions raise a diagnostic failure instead of silently
becoming a priority pass. Accepted trace entries retain pre-action information
and ordering; rejected actions do not alter the input state or save statistics.

This aligns these entry points with live autoplay action acceptance. It does
not establish universal hydration, sideboarding, starting-player or controller
parity across every tool. Other independently implemented runners remain an
explicit follow-up audit, not silently covered by this change.

## Evidence And Limits

The final combined gate passes **1,055 tests** with 21 existing datetime warnings
in 185.27 seconds across 21 affected modules. It includes the production policy,
opaque projections, inspection flow, action contracts, live autoplay safety,
training/dataset choices, combat, strategic query reuse, analytics and replay.
This is not a full repository/browser suite or an expert-play certificate.

The repaired focused policy gate passes 285 checks. The independent simulator
boundary gate passes 129 checks. Both use isolated local source, never live
SQLite. Seeded Strong Burn/Aggro games finish in both deck seat assignments,
with exact repeated replay equality; these two logical games are legality and
repeatability smoke checks, not balance measurements or expert-play evidence.

The policy tests exercise actual production-agent calls, not dynamically
installed test-only hooks. They cover both seats, four archetype styles,
Strong/Master, deployment, zero-hit/unknown inventories, reserved interaction,
lethal response, hidden-information invariance and snapshot replay.

Three pre-existing AI tests fail on unchanged base because their test doubles
omit Oracle text. Their bookkeeping helper now supplies the same empty default
as `CardInstance`; canonical card fixtures and production mana logic are not
changed. Earlier failed runs are retained, not represented as passing evidence.
