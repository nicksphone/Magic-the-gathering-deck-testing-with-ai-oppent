# Recorded Game Resource Diagnostics

This component starts from immutable `136917284d963c076855d2452f86f8de74fbe9ff`.
Only `scripts.regression_matrix_replay.run_game` changes in production.

When a game evidence writer is supplied, results additionally record
`resource_limit_dimension` and `game_elapsed_seconds`. The dimension is populated
only for the exact `SimulationResourceLimit` type and ten source-defined labels;
unknown values, malformed values and subclasses remain null. Exception arguments,
messages, representations and private locals are not read or exported.

Elapsed time starts immediately before Factory construction and ends after the
loop or catch, before log normalization and evidence writing. Shared deadlines,
limits, RNG, decisions, outcomes and log hashes are unchanged. Without a writer,
the original output shape and exception propagation remain unchanged.

The final acceptance runs five whole modules: resource-metadata controls,
regression-matrix sampling, series resource continuation, resource budgets and
round-robin protocol. It passes 97 ordinary cases and 29 separately reported
subtests in 30.16 seconds, with no failures, errors or skips. Ten ordinary cases
and 21 subtests are new. Seven additional guardian protocol checks are separate,
not added to the cohort count.

Three unchanged controlled lethal-diagnostic tests require real copied-state
engine queries: their observed action calls are 1, 3 and 3 under finite per-test
limits of 16. Chooser, SQL, socket, child-process and provider calls remain denied.
The persistent function-object gates cover saved aliases and restore the original
code, defaults and globals afterward. This is a trusted-test fence, not a general
Python sandbox or natural-game certificate.

The existing recovered-original-AST test has a separate adaptation: it verifies
the exact five additive metadata shapes before removing them for the unchanged
original AST equality assertion. All original assertions and other methods remain.

Preserved earlier ledgers include a collection-root setup error, failed
neighbor epochs, and a profiler-fence weakness: raising from a Python profile
callback removes that profiler. Their blanket native-prevention claims are
withdrawn; their SQL/socket audit fences and recorded failures are not rewritten.
The final acceptance uses persistent gates rather than that profiler.

The older six stopped games in the `2b9f3a60` matrix still have unknown resource
dimensions and durations. No matrix or A/B run is repeated or retroactively
qualified by this component. It changes observability, not AI strength or gameplay.
