# Private Measurement Artifact Budgets

The fixed-game measurement pipeline retains complete private raw and normalized
logs. Those files are not HTTP responses or model-result payloads. The former
writer and reader incorrectly subjected the entire duplicated log envelope to
the 1 MiB result/snapshot limit. All eight arms of the retained experiment
stopped with `resource_limit_dimension=result_json`: 16 games planned, eight
attempted, eight unrun, zero eligible comparisons. Winners and unavailable
quality metrics are not inferred from those attempts.

## Unchanged Limits And Evidence

- API results, result metadata, snapshots, compact final packages and comparison
  inputs retain their 1 MiB limits. General `ResourceBudget.checked_result` and
  default `preflight_game_record` remain strict.
- Complete logs retain the original 4 MiB/32,768-entry per-game limits. Native
  trace entry, scalar, depth and node checks remain unchanged.
- The original live budget retains its 32 MiB/131,072-entry batch accounting
  and 600-second productive deadline, including packaging. It is not reset for
  serialization or packaging.
- Only known typed private game, row and producer artifact slots use the new
  private-file path. Other metadata remains bounded; a similarly named field
  or unknown filename is not an exception.
- Every emitted byte, including duplicate and escaped log representations,
  remains charged to the existing external 32 MiB arm artifact guard. Private
  encoding and reads also have that finite ceiling. A legal individual log is
  not a promise that every duplicated artifact will fit the aggregate budget.
- Raw/normalized data is preserved, not truncated or replaced with supplied
  counters. The packager retains actual file identity, hash, result, coordinate,
  row and complete-log joins, including late-mutation checks.

The shared BO3 writer and its caller retain their existing bodies. This change
does not requalify a BO3 execution or change a schedule, policy, metric, winner,
model, training input or any of the fourteen numeric resource limits.

## Verification

The new module reproduces 15 failures and one pass before the correction, then
passes all 16 cases. The full twelve affected modules pass 350 ordinary cases
and 31 subtests under a guard denying SQL, sockets, processes and model/provider
imports. Source/runtime and resource checks pass with zero unexpected denials.
A separate parent execution also passes all 16 new cases.

The earlier whole-suite invocation had passing test assertions but an invalid
guard receipt caused by resolving dir-FD-relative cleanup paths against the
wrong directory. Its ledger is retained separately. Correcting that harness
resolution does not change the product or remove a test.

These are boundary and writer/reader protocol checks, not new natural games or
AI-strength evidence. The failed experiment remains immutable. A new measured
source and completed comparison are required before claiming improvement.
