# Outcome-Based Trample Blocking

## Observed Defects

On `9de19f03`, the same expanded 48-case declaration has 44 passes and four
strict failures: strong AI chooses a losing single block against lethal trample,
both with deathtouch and after its effective removal, in both seats. Independent
checked combat proves a surviving multi-block alternative. The original smaller
30-case declaration has 28 passes and two failures.

The first remedy passes those 48 cases and 345 cases across 15 whole neighboring
modules. Independent review then identifies an additional double-strike case.
Four checked regressions fail for both strong and master: a one-power-step
screen misses lethal damage, and the existing nonlethal-chump pruning discards
the legal surviving multi-block. These historical results are retained, not
rebranded as qualification of the final correction.

## Shared Correction

Only `AIAgent._search_block_assignments` changes. Strong AI admits the existing
bounded search for actual declare-blockers positions with effective trample
attacking the defender. Its existing cloned checked combat must establish that
the no-block line loses; unknown or nonlethal outcomes keep the legacy fallback.
Next-combat forecasting is disabled for this strong emergency path.

For effective double strike, the same no-block projection also corrects lethal
classification in master search. A demonstrated loss prevents the old
nonlethal-chump pruning; the adjustment is not a damage amount or rules override.
Existing scoring coefficients, legal intent enumeration, payment handling,
four-attacker/five-blocker caps and the 4096-node enumeration budget are unchanged.
No card-name exceptions or separate combat rules are introduced.

## Qualification

The corrected three-module focus passes 52 cases. The final combined declaration
passes **487 ordinary cases across 25 whole modules**, 97 warnings, 161.68s,
exit 0, without skips, deselection or expected failures. It includes the unchanged
14 canonical outcome goldens, 36 production/admission block controls, four
double-strike regressions, existing combat/racing/allocation/resource controls,
the existing knowledge tests, 21 new estimate-transport tests and 14 unchanged-
policy paid-removal baselines. The recorded JUnit has 487 cases and zero failures,
errors or skips. No extra subtest count is claimed in this parent runtime.

All 3002 nongraph executed source/input files are byte-equal before and after.
The precollection harness denies physical-file SQLite, sockets, subprocesses,
providers and alias creation, while permitting explicitly wrapped in-memory
SQLite. This run opens zero SQLite handles and records no unexpected denials.
It uses the existing read-only Python 3.12.3 / pytest 8.3.3 environment.

Complete canonical Oracle data is unchanged. Creature births, counters and
effective keyword grants are declared old-board fixtures, not paid acquisition
or natural-game evidence. Actual checked combat, production full-menu choice
and root purity are tested. Protocol-unknown and capacity controls are labeled.

## Remaining Work

The numerical estimates are validated private advisory transport, not scoring
inputs or legality. This correction does not complete Task 2.3, its required
before/after archetype benchmark, learned matchups, sideboard policy or release
qualification. The existing bounded search can still evaluate thousands of
cloned positions; worst-case latency is not certified here. Larger boards,
unknown projections, and broader natural-game strength remain separate work.
