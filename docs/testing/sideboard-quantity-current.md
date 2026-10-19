# Sideboard Quantity Boundary

Qualified on isolated source from `07305a188`, with only the sideboard core
validation changed. Invalid quantities are no longer coerced or ignored: bools,
fractional values, strings, zero, negative and missing quantities raise
`SideboardError`. Malformed entries and blank names also raise that structured
error. Valid duplicate requests retain their existing aggregation semantics.

The public `DeckEntry` contract already rejects these quantities. This repair
hardens internal callers; it is not evidence of a public HTTP validation bypass.

Baseline new pure audit: 24 passes and seven strict failures. The unchanged
31-case audit passes after repair. Final fresh-local-SQL gate: three complete
modules, 49 passes, 72 warnings, 7.38 seconds. Existing sideboard and AI-sideboard
tests are unchanged. Coverage includes per-card conservation, JSON roundtrip,
inverse swaps, rejection input purity, sideboard restore, next-game deck contents
and existing public-information AI policies. No skips or expected failures.

The gate permits only the isolated source-local SQLite database and in-process
AF_UNIX streams; external sockets and child processes are denied. It ended with
no guard violations, a disposed engine and only the main thread. No live data or
main checkout was used. Evidence is archived under RCHFiles parent integration.

Seeded interactive BO3 transitions, loser play/draw choices, complete browser
games and general AI sideboarding quality remain separate acceptance work.
