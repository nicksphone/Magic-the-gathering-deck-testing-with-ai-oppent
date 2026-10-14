# Legacy Known-Deck Snapshot Fixture

Base source: `f102874ff5e7a1d9c77873054eb194e8261998d7`.

The legacy snapshot case removed `starting_decks` from a newly serialized
Factory state but retained newer `sideboard_facts`. Those facts bind the
original inventory, so the unchanged strict deserializer correctly rejected
the inconsistent wire before its legacy assertions could run.

The fixture now also omits `sideboard_facts` from that serialized legacy wire.
It does not clear live facts, change stock, reconstruct inventory, or alter a
validator. All 15 original assertions and all other original functions remain
unchanged. One new regression retains current facts while removing only
`starting_decks`, requires the existing inventory-mismatch ValueError, and
checks that the genuine Factory state is unchanged.

## Actual Pure Qualification

- Original whole module: 11 passed, 1 failed, 0 errors/skips, 8.07 seconds.
- Corrected whole module plus the new regression: 13 passed, 0 failures,
  errors or skips, 7.76 seconds; all 12 original test IDs retained.
- SQL, socket, and child-process denial was installed before collection.
  Eight native/public alias canaries were denied; subsequent unexpected I/O
  was empty. There were no SQL connections, database files, or new live threads.
- Original helper imports genuinely import `main` definitions. No App service,
  endpoint or lifespan was invoked. The nonthrowing App-call observer remained
  installed; prevention uses persistent audit denial, not a raising profiler.
- Source and borrowed runtime maps were unchanged within both runs. Disposable
  image-cache bindings and pytest logs point to owned local scratch, not source.

An initial pytest logging-sink guard stop and a subsequent existing-temp-directory
administrative stop occurred before collection. Both ledgers are retained and
are not counted as the qualified 12-case baseline.

This is a test-fixture correction, not a serializer/AI-policy change, a
sideboarding contract expansion, or a benchmark/strength certificate. No
fixture-SQL lease was used; measurement counters remain 10213 native / 3900
chooser.
