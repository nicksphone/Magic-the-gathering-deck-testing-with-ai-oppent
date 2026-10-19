# Effective Battlefield Decision Evidence

The `cb80e360209202f4a0e933b25ce50c8ba70a630c` baseline records printed
battlefield types in decision-quality traces and uses them to exclude potential
blockers from its open-board lethal metric. Song of the Dryads therefore makes a
real noncreature land look like a blocker to analytics, although the engine can
complete the lethal attack.

## Correction

`analytics.decision_quality` uses the existing effective-type query both before
the attack simulation and after resolving its attack triggers. The verbose
round-robin script reuses the same battlefield snapshot and engine-based lethal
query instead of maintaining a second printed-type/power-sum implementation.
Its extra loyalty/face fields and deterministic snapshot ordering remain.
Unknown/paused engine outcomes remain unavailable (`None`), not certified false.
No AI weights, action choices, rules, canonical data or gameplay state change.

## Actual Qualification

The corrected NEW whole module has 24 cases: both seats, snapshot restoration,
effective battlefield trace equality, actual checked attack/block/priority passes
to a winner, original-root purity, real creature blockers and source departure.
It reuses unchanged committed canonical Royal Assassin and Song rows.
Baseline: **18 failures / 6 passes in 4.12s**. Candidate: eight whole modules,
**168 passes / 2 import deprecation warnings in 11.16s**, no skips/deselections or
expected failures. All selected source hashes before/after are equal.

Whole modules:

```text
test_effective_decision_quality.py
test_regression_matrix_sampling.py
test_card_play_analytics.py
test_pending_removal_traces.py
test_decision_taxonomy.py
test_replay_decision_metrics.py
test_basic_land_replacement_composition.py
test_printed_layer_four_fastpath.py
```

A native Python audit hook was installed before pytest/project imports and denied
SQLite, sockets, subprocesses and explicit process-launch events. The observed
forbidden-I/O ledger is empty. This is not an OS sandbox or child-inherited audit
claim. No live/retained database was opened. The first NEW draft's eight checked
combat-damage-action errors and its candidate 115-pass/8-failure ledger are
preserved separately; only that NEW test was corrected to use ordinary checked
priority passes. Original tests were not edited.

Verified evidence: RCHFiles
`parent-integration/effective-decision-quality-qualified-20261008/`.
This fixes a measurement defect, not a finding that the AI is now expert, that
all blockers are searched, or that the 13-archetype quality matrix is complete.
The metric deliberately remains limited to an effective creature-free board.
