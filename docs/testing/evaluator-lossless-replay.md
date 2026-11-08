# Lossless custom-evaluator replay

The November 8 RC matrix exposed two different diagnostic formats. Quality traces
sort hands, contain structured battlefield snapshots and compact actions; the
strict replay reader expects ordered name lists and complete execution choices.
The first saved matrix game therefore fails at decision zero (`hand`). Some
quality actions also omit mechanic selections and other parameters. The original
private mismatch remains recorded; those old receipts are not repaired by guessing.

Custom `regression_matrix_replay.run_game` traces now add a version-one `replay`
envelope before the checked transition. It records original ordered roots, legal
action types and a detached complete action. The quality projection, contextual
announcement binding and default legacy trace format retain their behavior.
`action_replay.reconstruct_game` validates the envelope and shared outer identity
and action fields, then performs the existing root, rejected-action, complete log,
hash and terminal comparisons. `card_name` is display metadata. A custom builder
cannot supply the reserved envelope key. Unknown or incomplete envelopes fail
closed; old compact records remain unsupported.

Independent review found a construction-boundary gap in the initial draft:
some complete action collections were copied before their final trace size check.
`ResourceBudget.trace_inputs` now preflights the entire completed action with its
existing bounded walker. Both production callers already separate display hints
with `complete_action`. The final combined trace still has its original size,
depth, node, log and deadline limits; none was widened.

The final complete seventeen-module pure cohort passes **287 tests and 31
subtests** in 85.08 seconds. SQL, network and child-process operations are denied
before project imports; zero such operations are attempted, and all 22 named
source/test/seed inputs have identical before/after hashes. Twelve existing
`datetime.utcnow` deprecation warnings remain visible. This is bounded component
qualification, not a complete backend or natural-game result.

The separate whole legacy replay module, including its real subprocess CLI and
private decision-export controls, passes 30 tests in 15.22 seconds after the
final resource correction. It is separate from the seventeen pure modules.

Public canonical Island/Mountain controls exercise real Factory, custom quality
builder, contextual trace binding and strict replay for both starting seats,
including ordered two-card mulligan bottoms. Corruption controls cover envelope
version/shape, actor, phase, hand, battlefield, legal types, action and conflicting
outer fields. Valid-but-oversized hybrid/band operands are rejected before builder
or checked execution. The legacy producer AST control and existing exact quality
field assertions remain in the whole neighboring cohorts.

Original red runs, the initially mis-sized budget fixture, subsequent corrected
red/green controls and initial 285-case cohort remain private evidence. Independent
review approves the correction after its Important finding is fixed and reruns
59 affected tests; its earlier overlapping 116 checks are not added to the total.
No raw game traces, hidden hands or model data are committed.

A separately declared production Master comparison uses one fresh Tempo/Tribal
coordinate, physical seat one on play, on frozen old `a4f8df9` and candidate
`705936b2` sources. Both games finish naturally with Tempo winning on turn eleven,
321 checked actions and 749 normalized log lines. Removing only the additive
`replay` object leaves every quality projection and event line equal. The
candidate's complete recorded actions reconstruct successfully with matching
roots, logs, hash and terminal metadata. This does not prove equality of old
operands that the compact format never recorded.

Independent receipt/hash/trace-count checks verify both games, every bound source
file (2,691 old; 2,692 candidate), unchanged identical deck inputs, zero denied
operations, result-size bounds and both reaped children. These are two actual
games at one same-seat coordinate, not seat-balanced strength, BO3 or full-matrix
acceptance. Private evidence is retained under
`/home/nick/mtg-rc-evidence-20261108/lossless-replay-natural-comparison/`.

The full matrix remains bound to its frozen earlier source and has its own
[status and limitations](full-master-matrix-20261108.md). It was not restarted
for this component change. All release gates remain open.
