# Card-copy latency follow-up

Date: 2026-09-30 UTC. Builds on [projection reuse](ai-projection-performance.md).
This is generic planner performance work, not a Control-only heuristic or a
claim that AI now plays at expert level.

## Evidence and implementation

Two offline shipped Blue Control/Ramp games, in both seat orders with seed 111,
Master difficulty and a 2,400-tick cap, completed 1,108 decisions without a
timeout. Profiling the five slowest captured decisions identified card-instance
deepcopy reconstruction/dispatch as the main remaining cost. The slowest
profile had 43 planning copies, taking 1.064 of 1.805 instrumented seconds;
profiling overhead is not representative decision latency.

Planning clones now preallocate exact `CardInstance` copies and their attribute
dictionaries in the shared deepcopy memo. Immutable string/numeric/boolean/None
and Zone values are reused. All mutable fields, including nested face metadata,
keywords, counters, dynamic attributes and cross-card references, are still
deep-copied. Shared aliases/cycles survive, source state stays unchanged, and
nonstandard card subclasses retain ordinary deepcopy behavior. This does not
share mutable metadata with the authoritative state or change search limits.

Five alternating iterations per mode compare this copy path with the previous
history-free generic deepcopy, retaining projection caching in both modes:

| Archetype | Turn/Step | Permanents | Reference median | Optimized median | Shorter |
| --- | --- | ---: | ---: | ---: | ---: |
| Control | 26 / draw | 16 | 0.669269s | 0.553719s | 17.3% |
| Control | 26 / draw | 16 | 0.520107s | 0.425990s | 18.1% |
| Control | 13 / draw | 13 | 0.487327s | 0.397115s | 18.5% |
| Ramp | 15 / precombat main | 12 | 0.322191s | 0.258379s | 19.8% |
| Ramp | 10 / precombat main | 10 | 0.322978s | 0.212436s | 34.2% |

All full decisions/reasoning match; planning-clone snapshots match the reference
except omitted historical logs, and authoritative snapshots stay unchanged.
These are local measurements on an x86-64 Ryzen 7 2700X environment, not CI
thresholds or guarantees. Other host load and runtime warmup affect timing.

## Reusable commands

```bash
cd backend
.venv/bin/python scripts/benchmark_ai_decisions.py \
  --snapshot /path/to/private-engine-snapshot.json --player 2 \
  --archetype Control --opponent-archetype Ramp \
  --reference-mode copy-only --iterations 5
.venv/bin/python scripts/profile_ai_match.py \
  --deck-a 'Blue Control' --deck-b Ramp --seed 111 \
  --max-ticks 2400 --target-seconds 1 \
  --output training_runs/blue-ramp-latency.json
.venv/bin/python scripts/profile_ai_match.py \
  --deck-a Ramp --deck-b 'Blue Control' --seed 111 \
  --output training_runs/ramp-blue-latency.json
```

The benchmark's default `full` reference disables projection caching and restores
the original full agent copies. `copy-only` leaves caching enabled and compares
only the card-copy fast path. Both include opponent-archetype provenance and
fail on full-decision mismatch or authoritative-state mutation.

The profiler uses offline built-in metadata, not a Scryfall sync or live match.
Run it in a dedicated process: it temporarily instruments the diagnostic agent
method and restores it even on exceptions. Output records public actor/turn/
step, board/action/history counts and timings, not hands, card identities, full
logs or snapshots. Percentiles use nearest rank; no-decision percentiles are
null. The one-second target is a configurable diagnostic alert, **never a
gameplay cutoff**. A tick-cap timeout still produces a nonzero command exit.

## Validation and remaining work

Final gates: 1,765 tests pass in a fresh isolated tracked-source/database copy;
frontend lint, TypeScript/Vite build, unit contracts and the complete Chromium
action/recovery/BO3 harness pass. Tests additionally verify percentile boundaries,
empty samples, invalid targets, diagnostic non-cutoff behavior, private-data
omission and instrumentation restoration after exceptions. Live storage was
not used for these tests.

After the change, both Control/Ramp games retain their earlier complete-log
hashes. The 372-decision game has p95 0.025205s, p99 0.157176s, max 0.435836s;
the 736-decision game has p95 0.038120s, p99 0.196768s, max 0.547823s. Neither
exceeds the diagnostic target. Eight other seeded, seat-paired archetype games
retain identical full results and traces from the preceding milestone. Repeats
are not independent statistical samples, and concurrent game timings are not
used for speedup claims. Compact [measurement evidence](ai-card-copy-evidence.json)
contains the local paired medians and game hashes, not snapshots or full hands.

The target is not yet a certified release budget across the supported corpus.
Broader seeds/complex boards, p99/max tails, end-to-end API/serialization costs
and long-session soak remain necessary. The distinct timeout-diagnostic
interpreter crash remains unresolved; these successful runs neither reproduce
nor establish its cause. No arbitrary-card correctness or win-rate claim is
made.
