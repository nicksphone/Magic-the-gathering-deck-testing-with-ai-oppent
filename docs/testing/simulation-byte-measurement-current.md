# Current Simulation Byte Measurements

Application source: `8cfcb4f4dbc06a96b59c2b992cc629131b18d275`.
The real `AnalyticsService.run_batch` runs canonical 60-Island and 60-Plains
decks, casual difficulty, 500 ticks, one and two matches. Only repository
snapshot persistence is spied; the simulator, agents, actions and outcomes are
not replaced. A read-only profile observes retained return-local logs.

The complete two-case cohort passes in 305.27 seconds. Both cases naturally
reach the tick limit: zero resolved games, one and two timeouts respectively.
This is resource instrumentation, not AI strength or complete-game evidence.

| Matches | Snapshot/result JSON bytes | Retained game-log text | Instrumented elapsed |
| --- | --- | --- | --- |
| 1 | 8,683 | 1,048 lines / 929,767 UTF-8 bytes / 500 traces | 101.743 seconds |
| 2 | 15,939 | Each of the first and second logs: 1,048 lines / 929,767 bytes / 500 traces | 202.435 seconds |

The final state log also has 929,767 bytes. These are text-length measurements,
not additive independent memory allocations: strings/references may be shared.
Process peak RSS is cumulative Linux KiB, including imports and instrumentation:
81,064 before the first case, 86,076 after it, and 87,284 after the second.
Profiling affects timing; no CPU/DB performance cause or exclusive job-memory
bound follows from these measurements.

Snapshot bytes are observed from the actual returned object at the snapshot
write boundary. Job-result serialization is only a source-audited estimate,
not an executed job write: duplicate snapshot/job result references would total
17,366 and 31,878 JSON bytes. Each reference request is 180 bytes. Serialized
result size alone does not bound per-tick trace construction or retained logs.

All 13 native SQL-alias/network/subprocess canaries are denied before collection;
no unexpected denial, database FD or non-main thread remains. All 2,418 source
files are unchanged. The first attempt's shared 120-second alarm interrupted the
second case after one pass; its failure ledger remains immutable. The complete
attempt changes only that alarm to 450 seconds, with a 480-second outer bound.
Neither attempt changes cases, ticks, profiling, gameplay or source.

Parent verification receipt and raw selected evidence:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/`
`combined905-and-simulation-bytes-current-8cf-20261007/`.
Full measurement/source archive:
`diagnostics/job-resource-contract/current-8cfcb4-pure-byte-qualified-20261007-vXc8kt/`
(manifest `728cfed5acec25c74bb2d9bdffc7322f06fdfaee2cbb29ac33b97aa1ccbc551e`).
Construction-time log/trace limits, both persistence boundaries, cooperative
deadlines, synchronous drain and load/crash/soak acceptance remain required.
