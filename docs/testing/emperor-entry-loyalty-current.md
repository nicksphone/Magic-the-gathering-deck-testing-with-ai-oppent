# Entry-Turn Loyalty And New Incarnations

Current source integrates the shared complete printed entry-turn timing
predicate in legal moves and execution, plus a copy-on-write reset of the
once-per-turn loyalty-use record when a new battlefield incarnation is assigned.
There is no card-name timing branch and Flash alone grants no loyalty timing.
Priority, controller, battlefield membership, printed-ability suppression,
split second, cleanup restrictions and the ordinary once guard remain required.

The reset assigns a new set instead of mutating the existing set. This matters
because prospective-entry queries shallow-copy state: an in-place discard
would alter the live match's used-loyalty record. Both-seat actual paid Emperor
states prove snapshot, record identity/content, absent second-activation offer
and atomic rejection remain unchanged during prospective queries.

Current-parent qualification: 12 whole pure modules, 276 ordinary passes,
35.67 seconds, exit 0. This is one combined cohort, not a sum of overlapping
gates. It includes all 232 prior Veil checks and 44 timing, effect, lifecycle
and query checks. Native SQL/socket/child controls ran before collection;
application I/O was empty, descriptor maps matched, extra threads were absent,
all 2,405 source hashes matched, and the existing local database hash stayed
unchanged. No original test assertions or markers were adapted.

Real paid Flicker returns a new incarnation with fresh loyalty and permits
one new activation; another activation on that incarnation rejects. Natural
entry-turn expiry and paid Leyline/Jace Flash-only controls pass. Effect-target
fixtures are canonical declared battlefield state, not certified target casts.

Evidence under the MTG NFS archive:
`parent-integration/emperor-veil-current276-20261008/`.
Prior immutable timing audit, stage, lifecycle failure and reset evidence are
under `gate2-emperor-timing/`; their results are not retroactively changed.
The reset's isolated 250-node neighbor run retained one failure and two errors
at native SQLite-denied HTTP fixtures; it is not a completed mixed gate.

Native HTTP/SQLite, browser choices, inventory admission-warning review, all
ability-suppression/layer interactions and final release-source acceptance are
still separate. This does not certify arbitrary planeswalker/card semantics.
