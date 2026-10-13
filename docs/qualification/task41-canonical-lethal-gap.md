# Task 4.1 Canonical Behavior Checkpoint

Source: immutable `2f42a6eb352480fae1940018b70f4395c478c38e`.
Only NEW fixtures, tests, and this checkpoint are proposed. No production or
existing test changes are indicated by these results.

## Arithmetic Correction

The original Phase 4.1 example says a 5/5 plus a 1/1 first striker against
seven life is lethal. It deals six damage, not seven. Preserve that literal
position as a nonlethal control; use six life for the sibling lethal intent.
First strike does not also deal ordinary combat damage without double strike.
No original test or historical plan is rewritten by this checkpoint.

## Actual Results

The NEW whole module has 24 passes, zero failures/errors/skips (6.41 seconds).
Both seats and snapshot round trips cover these outcomes:

- Eight 5/5 Silverback Ape + 1/1 Tundra Wolves attacks: six damage, actual win
  at six life, no win at seven life.
- Four explicit checked X4 Volcanic Geyser casts are engine-positive controls,
  not AI certificates. Four separate actual AI choices also select X4, pay
  six mana, and resolve the genuine spell to an actual win.
- Four actual Go for the Throat choices pay two mana, remove a declared 3/3,
  and are followed by a legal same-turn attack that actually wins.
- Two genuine paid Counterspell responses preserve the blocker and prevent
  the assumed removal win. Two private-hand controls retain UNKNOWN combat
  completion instead of proving a response-free leaf.

These are 24 positives on existing implementation, not a fabricated failing
post-Phase-3 baseline. No redundant lethal planner is proposed.

## Knowledge and Bounds

All profiled cards use existing `derive_profile` / `merge_profile_payload` /
`snapshot_for` through `test_task23_checked_removal_baseline.add_profiled`.
That helper verifies a non-null `estimate_for`. Its canonical row is a
SQL-free fixture object, not a persisted database row or live cache edit.
The snapshots are genuinely eligible for the service's `persisted` tag
result, whose name describes match-frozen eligibility, not an SQL write.

The existing AI decision usage counters were captured without replacing its
policy: 22 actual decisions, ten with positive persisted usage; twelve
persisted lookups total, zero fallback/opaque counts. The twelve attack
decisions have zero tag lookups. Thus spell decisions consume eligible
knowledge, but these tests do not prove that all lethal behavior is caused
exclusively by tags. Existing X scoring also reads full Oracle and payability.

Observed cast candidate menus contain at most one spell. This is not a proof
of the plan's proposed four-spell cap: the existing master-only tactical
setup helper permits 16 candidates; strategic search uses a 4/6/8 beam.
The tested policy is `strong` / `Midrange`, not the master-only setup helper.
No cap, named branch, or strategy is changed to make this cohort pass.

## Fixture and Scope Limits

Three full official Scryfall RAW responses are pinned by URL, UTC, HTTP status,
and SHA256 in `fixtures/task41_lethal_canonical/PROVENANCE.json`. Existing
canonical Bears, Go for the Throat, Counterspell, and Islands retain their
full original bodies. There are no invented spell costs or fake StackItems.
Initial boards, the Bears' old +1/+1 counter, and mana pools are explicitly
trusted test poses, not paid-birth certificates. Geyser X4 starts with a
declared six-red pool and proves actual six-mana spending, not a five-mana
fiction. Actual checked actions and final states, not scores, qualify wins.

Offline tests deny SQL, network, process, and provider access before collection.
Three audit-event denial probes are not three attempted real IO operations.
No database is created. This Python fence is not an OS sandbox certificate.

The initial launcher collected zero tests and failed outside the owned
checkout in 90.09 seconds. Its log/XML is retained as a harness failure.
Only the NEW launcher was corrected to constrain cwd/rootdir/confcutdir.
An intermediate 24-pass counter export used the wrong test-module name and
produced no counter file; that ledger is retained separately. The final
export locates the collected module by its exact owned filename.

Full pytest, Phase A/B against the actual post-Phase-3 baseline, strength,
complete lethal coverage, and whole-matrix/runtime qualification remain
required separately. No D13 source/runtime/caps admission is inferred.
