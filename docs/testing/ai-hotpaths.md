# AI Hot-Path Integrity and Keyword Prohibitions

## Implemented

Profiling a seeded Blue Control/Ramp game identified repeated planning copies and
continuous-effect parsing as significant costs. Flat built-in card lists, sets
and dictionaries containing only supported immutable scalars now bypass generic
deepcopy dispatch. The shared memo preserves cross-card/player aliases. Nested
metadata, cycles, mutable scalar/container subclasses and custom deepcopy
contracts retain the ordinary deep-copy path. Authoritative state is not shared
with speculative mutable containers; RNG and pending choices remain intact.

Five static-instruction parsers use bounded standard-library LRU caches keyed by
normalized Oracle text. Results contain immutable tuples/frozensets and no card or
state references. Each caller receives a fresh iterator. Controller, target,
counter, zone, attachment and timestamp checks still use current state; effective
power/toughness and keyword results are not cached. Updating active Oracle text
naturally changes the cache key. Each parser is bounded to 4,096 text entries.

Canonical tests exposed a separate semantic gap: supported composed "lose ... and
can't have or gain ..." clauses previously performed ordinary removal only. The
shared prohibition matcher now recognizes that wording and applies the can't
override after grants. All five Archetypes are tested with older/newer opposing
grants and source departure. There is no card-name-specific rules branch.

Search depth, candidate limits, heuristic weights and decklists were not changed.
The offline benchmark supports `card-fields` and `hotpaths` ablations, reverting
only these data paths while retaining the same agent/search policy.

## Verification

The independent standard final-source backend suite passes **2,133 tests** (292
existing deprecation warnings, 283.83 seconds). Twelve canonical Scryfall fixture
rows cover static instructions and keyword prohibitions. Existing canonical
attachment/ward scenarios and dedicated alias/cycle/subclass tests cover safety.
Frontend lint/build/unit and the complete Chromium harness pass, including normal
AI/AI, human/AI and human/human BO3 and backend restart recovery.
The focused regression set passes **259 checks**; 37 backend regressions were added.

The exact captured control/ramp decision is compared with alternating-order
paired runs. Decisions/reasoning and authoritative state must match; timing is
reported without a flaky pass/fail speed threshold. The instrumented complete
control/ramp game retains its parent result and full log. The eight seat-paired
archetype smoke games also retain actual parent results/logs and repeat across
sixteen executions without timeout or cast/target rejection. These are regression
and local performance samples, not professional-AI or balance certification.
For the captured decision, five runs per mode yield median **0.567 s optimized
versus 0.835 s ablated** (about 32% less time). The instrumented whole-game sample
changes from 29.45 to 24.65 seconds; these are different measurements, not a claim
that every game or decision becomes 32% faster.

Detailed timings, source hashes, parent reproductions and local logs are retained
in the companion `ai-hotpaths.json`. Existing dependencies were reused, not
freshly installed. Backend/API checks use independent disposable source/database
copies, never the live SQLite database.

## Diagnostic Failure

One extra full-suite run with `faulthandler_timeout=90` crashed with native
SIGSEGV while printing the timed stack dump. It is not counted as passing. A
fresh standard full suite passes; the isolated BO3 pair passes, and a timed
control/ramp test under GDB exits normally. The native crash was not reproduced
or proven fixed, and no interpreter upgrade was performed.

A [CPython report](https://github.com/python/cpython/issues/158200) describes a
similar timed-dump metadata race on a different tested branch. This is related
investigation context, not proof of this Python 3.12.3 run's cause. Preserve the
failed log and runtime follow-up rather than attributing it to gameplay or
claiming universal crash-free operation.

## Known Limitations and Next Upgrades

- Worst-case tactical decision/request latency, deep/master-plus search and
  additional complex positions require profiling and stronger operational bounds.
- Timing samples depend on interpreter, host load and cache warmth; no global
  speedup or response-time guarantee is established.
- Arbitrary static predicates, granted abilities, copy/type/ability suppression
  and full dependency/layer semantics remain incomplete. Parsing reuse is not
  evidence that an unsupported instruction has correct semantics.
- Long-session/LAN usability, fresh-install reproducibility, native diagnostic
  stability and broad statistical decision quality remain release work.
