# Dictionary-copy preflight

The exact-dictionary key check uses an explicit loop instead of `all(generator)`.
It still checks every key before allocating a result, changing the memo or copying
values; the first unsupported key falls back to the real `deepcopy` with the
original memo. No AI policy, search limit, RNG, scoring, trace or resource ceiling
changes.

## Observed checks

The new six-test module first ran unchanged code: five semantic passes and one
operation-count failure (three helper-local generator entries instead of zero).
The same module passes all six after the loop change. Four whole copy modules
then pass 47 cases, preserving the original 41 node identities and assertions.
They cover memo overrides, nested aliases/cycles, custom protocols, history/RNG,
registered set behavior and actual payment-plan comparisons. The local harness
redirects only existing media-cache configuration into its workspace for a
transitive app import; it does not start a lifespan or permit SQLite/network I/O.
The earlier blocked source-cache creation remains a separate failed harness run.

A matched unprofiled pair of the unchanged 158-case AI suite passes 158 ordinary
cases and 474 phases on each version. Runtime, system and protected input pins
match across the pair. The original elapsed metric is 139.788878 seconds before
and 136.346215 after, 2.46% lower in this one pair. It contains 102 synthetic cases
and 56 variants from two protected recorded positions, not 56 independent games.
N=1 is not statistical speed proof, expert strength or a natural-game comparison.
Raw private inputs are not committed; they remain protected regression inputs.

An earlier profiling run passed its 158 tests but failed the enclosing unchanged-
system check because host package metadata changed. It remains rejected as a
qualified benchmark. Its function-count telemetry motivated this small change;
its instrumented elapsed time is not the baseline used above.

Complete hosted regression is still required. The rejected 110-series evaluation,
its 12 resource stops, contextual/matchup data gaps and RC acceptance remain open.
This change does not fix the same-prefix game-log limit or upgrade an installation.
