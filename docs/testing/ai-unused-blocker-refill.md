# Reusing Retained Blockers

A completed Ramp/Midrange game exposed an unused blocker after Strong's
retention pass. The initial greedy allocation put both blockers against larger
attackers. Retention correctly removed a losing block, but never reconsidered
that blocker against an unblocked, smaller attacker.

`AIAgent._choose_blocks` now tries checked augmentations with those freed
blockers. It reuses the existing combat projection and material score. Unknown,
unresolved, losing and equal-valued alternatives do not replace the incumbent.
There is no named-card or archetype exception.

## Checked Evidence

The new 20-case module reproduced **4 failures / 16 passes** on the parent
before the correction. The coupled parent qualification then passed **1,230
tests and six subtests across 38 whole modules in 356.14 seconds**, including
the modal-target fixes and their native/AI neighbors. There were no failures,
errors, skips or I/O denials. All 2,651 backend input hashes match before/after.
SQLite, sockets and subprocess creation were denied before project imports;
real image helpers used owned scratch rather than the source cache.

Both-seat compact controls retain full printed Arboreal Grazer, Topiary
Stomper, Tarmogoyf and Llanowar Elves data. Seven actual controlled lands enable
Stomper; four graveyard card types make the unmodified Goyfs 4/5. Attack and
block declarations and the subsequent combat use checked engine actions.
These are declared battlefield poses, not claims of paid creature births.

Reassigning the retained Stomper to Elves removes Elves and saves one life,
with the same Grazer loss. Checked continuation reaches the next upkeep before
draw: Stomper survives with damage cleared and both Goyfs remain. Tests also
cover the six-land restriction, hidden-identity changes, root/RNG purity,
unknown projections, menace/flying, difficulty fallbacks and the existing
large-board boundary.

Independent worker checks passed 386 tests plus six subtests across 20 whole
modules. Their search runner extracted unchanged native helper bodies from an
unselected mixed HTTP helper module; that module's HTTP tests were not run.
The parent coupled suite did not use that extraction and ran the selected
whole modules under its native I/O guard.

## Limits

The correction adds only 23 lines inside `_choose_blocks`. All bytes and AST
outside that method are unchanged. The existing small-board Strong gate
limits new work to at most five blockers times four attackers: 20 additional
checked probes. Existing search-return paths, weak/normal behavior and larger
boards are unchanged. This is not an exhaustive combat solver or a measured
full-game strength improvement. The recorded private game remains protected;
it is not a public fixture. No experimental learned weights are activated.
