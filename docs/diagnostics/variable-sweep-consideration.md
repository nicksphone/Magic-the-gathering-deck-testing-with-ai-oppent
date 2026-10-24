# Whole-Effect Variable Sweep Consideration

The early AI variable-sweep filter previously searched for one debuff clause
anywhere in a card's Oracle text. If no opposing creature would die, it removed
the entire cast before ranking. That also excluded compound permanents with
continuing abilities, rather than letting the existing scorer consider them.

The filter now applies only when the selected cast face/variant has a complete,
sole-effect variable-debuff body. It reuses the existing reminder-text remover
and debuff matcher, with one optional terminal period. Compound, ETB-prefixed
and unrecognized bodies bypass this early heuristic prune, not legality checks.

There are no card-name branches. X selection, scoring coefficients, downstream
penalties, resource planning, checked actions, RNG and resource limits are
unchanged. The ranker may still pass; no test requires casting or choosing X=0.

## Verification

The new whole module has 15 cases: two both-seat full-canonical Meathook
consideration regressions and 13 anonymous parser-protocol cases. The latter
strings are not fabricated physical card prints or engine-support evidence.

On unchanged main `6f6e8372`, both real consideration regressions failed because
the offered compound cast was absent from the actual ranker input. The thirteen
parser cases separately failed their missing-helper assertions, without import
errors or skips. On the candidate, the same 15 cases passed in 3.72 seconds.

The two-whole-module cohort, including the unchanged original Meathook ETB test,
passed all 16 cases in 4.30 seconds. That original test retains the announced-X
debuff, actual deaths, both continuing death clauses, and snapshot assertions.
Source/runtime hashes and independent process/resource closure were verified;
no unexpected native I/O, SQLite, HTTP or new full game was involved.

Complete hosted CI remains required for this new production composition.

## Limits

The observed diagnostic position had no creatures on either battlefield.
Holding a sweeper there can be reasonable. Restoring consideration is not proof
that casting was better, nor a fix or waiver for the rejected full-match resource
gate. No strength, matchup, training-data or RC-ready claim follows. Archived
synthetic game state and traces remain private and are not repository fixtures.
