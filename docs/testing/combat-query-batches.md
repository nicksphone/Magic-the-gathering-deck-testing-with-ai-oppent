# Immutable Combat Query Batches

## Implemented Scope

Combat reuses the existing synchronous `rule_query_scope` while computing block
eligibility, damage-assignment options and queues, first-strike participation,
and pre-damage power. These batches only read the current game state. Their
scopes end before payments, pending-choice publication, damage, replacement
effects, triggers, state-based actions or other game-state changes.

No search depth, candidate count, legal move or action semantics were removed.
The cache is not retained between first-strike and regular damage, actions,
positions or exceptions. Existing query scopes remain unchanged.

## Current-Source Qualification

The frozen parent source is `d519d37`; the candidate adds only `combat.py` and
`test_combat_query_performance.py`. The composed gate passes **799 tests** with
136 existing datetime warnings in 74.84 seconds. Fifteen new cases cover both
seats, exact uncached snapshot parity, fewer underlying query evaluations,
counter changes, life thresholds, ability suppression/source departure,
devotion/type changes, payment/trigger boundaries and exception cleanup.

A retained Tokens-versus-Ramp Master blocking decision was executed sequentially
on base and candidate:

| Measurement | Base | Candidate |
| --- | --- | --- |
| Complete decision seconds | 116.025633 | 92.469217 |
| Legal intents | 625 | 625 |
| Combat finish projections | 532 | 532 |
| Engine actions | 3,997 | 3,997 |
| Engine next steps | 1,659 | 1,659 |

The complete actions, natural action, projection digest, input hash and
post-action snapshot hash are identical. Both inputs remain unchanged. The
measured reduction is **20.3% for this one retained position**. Timing is subject
to host load; this is not a general latency bound or strategic-quality claim.

Private parent evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/combat-query-optimization/parent-d519d37/`.
Tests use isolated local source/databases, not the running application's database.

## Remaining Work

Ninety-two seconds is still too slow for interactive play. Continue profiling
complete decisions and dense boards while preserving legality, private
information, deterministic replay and exact mutation boundaries. Broader
seasoned-player competence, current full-browser acceptance and unrelated
simulator entry-point parity are not established by these checks.
