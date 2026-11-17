# Python versus a native engine: measured spike — 2026-11-17

**Start with Python representation/copying work and timing-balanced CI; prototype
one native kernel only if the measured bottleneck remains. A full Rust rewrite
is not justified for finishing this RC by these data.** A hypothetical 5× speedup
of copy plus move services gives **2.12×** for the isolated AI choice, but only
**1.27×** for the sampled generation-plus-verification path, before conversion.
These are conditional bounds, **not achieved Rust/Cython gains or whole-game
forecasts**. No native kernel was built. A measured full-state JSON/native-buffer
round trip is already slower than the existing selective copy it would replace.

Measured archive/report base:
`e964503e9bb1c55f38dcbf21d8949c7bc55919eb`. This is **analysis only**: no
repository code, rules, AI, dependencies, pins, tests, workflow or acceptance
policy changed. No full suite, complete game, pilot or health run was launched,
resumed or rerun. Only one cell/prefix and one isolated choice are sampled;
none supplies a new game outcome or acceptance result. Private traces, hands,
actions, reasons, snapshots and DBs are not published.

## Method: preserve the optimized path while measuring it

- Existing local CPython 3.12.3 environment, **not a fresh locked installation**;
  disposable Git archive, one-core affinity, 2-GiB address-space limit,
  100-CPU-second bound and 125-second alarm per diagnostic. The maintainer's
  six-clone timing run was underway; these are process-CPU measurements, not
  unloaded-host latency promises, cgroup reservations or confidence intervals.
- Retained generation measurement: unchanged v3 `play_game`, first **128 actions
  of resolved health cell 000**. All non-timing record fields match the original
  prefix, including snapshot/hash, choices, legal/RNG/log and explicit order
  evidence. Comparison costs **0.108 CPU seconds** and is excluded from
  the generation totals below. Stop is after action 127, not a forged outcome.
- Verification measurement: unchanged `replay_trace`, the same 128 actions,
  every-action serde, and real selected handler/SQLite checks at steps 0 and
  100, then a diagnostic stop without a final game result. Two recorded
  selected boundaries pass; this is not HTTP/browser parity.
- AI measurement: the earlier slow **cycle decision at c2 action 214**, restored
  with a fresh master agent as in that diagnostic. The normalized action matches;
  source state/order is unchanged. Production engine/state/AI bodies are
  byte-identical from `93bd5971` through this archive. A separate observational
  pass measures candidate cache keys; it applies no cache and accepts no action.
- **Important correction:** wrapping `AIAgent`/`RulesEngine` methods makes
  `_native_planner_snapshot` reject its identity guard and may select fallback
  work. That initial profiling approach and its interim figures are discarded.
  The retained measurements use Python 3.12 monitoring: code-local start/return
  events and filtered global unwind events, with **no method replacement**.
  Guard eligibility is asserted before/during/after monitoring, and all tracked
  stacks/AI depth must close. Monitoring still adds callback/clock overhead.
  [Python monitoring API](https://docs.python.org/3.12/library/sys.monitoring.html).
- This caveat also applies to the older c2 wrapper-profile timing tables: do not
  treat them as the normal fast-path baseline for a port decision. It does **not**
  reclassify the original worker/pilot/health results, which did not run those
  diagnostic wrappers. Setup binding/normalization mistakes and unsupported
  local-event wiring were corrected before retaining the measurements here.
- Timers are nested/exclusive; inclusive parents are not added to their children.
  Selective state copy, snapshot building and serde are distinct scopes, not
  a claim to have timed every generic `deepcopy` separately. Generic deepcopy
  and native copier bindings were not replaced. Microprobes run **after all
  monitoring events/callbacks are disabled**, with the guard still eligible.
- Generated trace bytes go to a discard sink: no original trace file is copied,
  and this does **not** measure disk/fsync CPU. Real selected parity uses only
  owned temporary diagnostic SQLite DBs, retained privately. Import/input
  preparation is separate: bootstrap through the v3-prefix input is about
  **2.1 CPU seconds**. The isolated choice also loads its older before-state
  and obtains initial legal moves outside the timer; these are not cold-process
  end-to-end latency measurements.

## 1. Normal engine/AI work versus harness work

Generation takes **14.663 CPU / 14.680 wall seconds**, or **14.555 CPU
seconds** without evidence comparison. It makes **385 captures**: initial plus
three per accepted action. Every serializer call in this sample belongs to those
captures; there is no extra serializer call inside the AI parent bucket.

| Non-overlapping generation component | CPU seconds |
| --- | ---: |
| Real transition/validation, excluding timed copy/move children | 0.122 |
| Real move generation outside AI | 0.838 |
| State copy outside AI | 1.093 |
| AI state copying | 3.236 |
| AI move generation | 0.227 |
| AI simulated rules actions | 0.228 |
| AI evaluation/orchestration and other queries | 1.984 |
| Harness full capture/build/encode/decode/hash | 6.456 |
| Other encoding/orchestration, including setup/timer overhead | 0.370 |

The AI-inclusive parent is **5.675 seconds**. Its copy contribution is derived by
subtracting the other three exclusive AI children; copies are not counted twice.
The **engine + AI subset costs 7.728 CPU seconds**, including actual transactional
copy/validation. The small transition-only row does not mean accepting an action
costs only that row: copy and legality are necessary parts of acceptance.

A normal user-facing game does not pay the extra verifier or three harness
captures per action. It still pays transactional copies, rules/legality and AI
on AI turns, plus app persistence, public-view serialization, HTTP/autoplay and
rendering. Those app/UI costs are **not measured here**; the engine subset is
not total request latency. This sample selects for both seats, unlike a human
turn with no AI choice.

The extra verification prefix costs **14.435 CPU / 14.767 wall seconds**:

| Extra verification work | CPU seconds |
| --- | ---: |
| Repeated engine move/transition/state-copy services | 2.386 |
| 385 full captures | 6.523 |
| Caller-side snapshot deepcopy/order wrapper | 1.913 |
| Deserialization | 1.922 |
| Two selected handler/SQLite checks, including their setup/closure | 1.247 |
| Other hashing/checking/orchestration | 0.444 |

It verifies 128 transitions/serde restarts; it reruns real engine services for
assurance, not just bookkeeping. The combined sampled path is **28.989 CPU
seconds**, with engine/AI generation about a quarter. Do not scale that early-
prefix ratio to entire games: expensive later decisions differ.

Cheaper harness candidates include not decoding a capture whose value is unused
after the AI mutation fingerprint, and reusing already-built canonical bytes.
The capture's **1.010-second** decode/other bucket is only an upper bound on
what avoiding decode can save; it cannot recover the entire **6.456** seconds.
Do not remove mutation/order checks, fields, logs or per-action replay. Larger
printed-metadata sharing needs a representation/fidelity change, not weaker
verification. Compression alone addresses bytes, not the measured object walks.

## 2. AI search, caching and a realistic native boundary

The matched cycle choice costs **6.192 CPU seconds** (6.191 inside
`choose_action`), excluding post-choice evidence checks:

| Exclusive AI service | CPU s | Fraction of choice, rounded independently |
| --- | ---: | ---: |
| State copy | 2.400 | 38.8% |
| Move generation | 1.695 | 27.4% |
| Simulated rules actions | 1.772 | 28.6% |
| Other evaluation/orchestration | 0.324 | 5.2% |

Counts are **277 planning copies, 284 state copies, 733 simulation calls,
740 engine actions and 167 AI legal calls**, with seven checked actions inside
simulation. Earlier 285/169 counts included the outer real action and legality.
Copying is substantial, but moving the copier does not remove the other rules
and move-generation work. Nor does a language rewrite remove search branches.

### Structural sharing / COW and native service ceilings

The existing copier already shares immutable atoms, uses one memo and exact-
native fast paths with Python-protocol fallback. Planning copies already omit
diagnostic history. “Share strings” or “drop logs” is not a new optimization.
COW requires isolated writes to card/list/dict state and a genuinely immutable
printed-definition layer, preserving aliases and custom-copy fallbacks.

For target fraction `f` accelerated by `k`, the conditional Amdahl factor is
`1 / (1 - f + f/k)`. All other work is unchanged; conversion is zero here.
A **2–5× target-service improvement is a scenario to test**, not an achieved
Python, Rust or Cython gain:

| Region / accelerated target | Fraction | Target 2× | Target 5× | Free target: absolute sample ceiling |
| --- | ---: | ---: | ---: | ---: |
| AI choice: copy | 38.8% | 1.24× | 1.45× | 1.63× |
| Engine + AI subset: copy | 56.0% | 1.39× | 1.81× | 2.27× |
| Generation + adapter: copy | 29.7% | 1.17× | 1.31× | 1.42× |
| AI choice: copy + moves | 66.1% | 1.49× | 2.12× | 2.95× |
| Engine + AI subset: copy + moves | 69.8% | 1.54× | 2.26× | 3.31× |
| Generation + verification: copy + moves | 26.3% | 1.15× | 1.27× | 1.36× |

Full engine/AI replacement could target more work, but this profile cannot
predict its implementation quality, conversion or compatibility cost. No fixed
rewrite speedup is defensible. These samples do not establish that a timed-out
game would finish with verification under the old CPU allowance.

### Caching: candidate repeats versus key cost

A separate observational pass, with identities/guard preserved, records
**167 legal calls / 115 unique state-only keys**, and **733 simulation calls /
398 unique keys**: **31.1%** and **45.7%** candidate duplicate fractions.
These are not safe cache-hit rates. Keys include snapshot/order/player/action,
but omit some projection/choice-path/profile context; complete keys can reduce
matches. Results are mutable and require isolation. `id(state)` is not enough
when the state mutates.

Computing the 900 full-state candidate keys costs **11.538 CPU seconds**, versus
**6.192** for the original choice. The audit pass totals **17.643** seconds; it
applies no caching and preserves normalized choice/input. Key cost alone loses.
If repeated calls had equal cost and key/results were free, the illustrative
saving would be **1.337 seconds / 1.28×**. That is neither measured gain nor a
rigorous ceiling: expensive calls may be unique. Eliminating *all* move/rules
time would cap this targeted choice improvement near **2.27×**, before saved-result
copying and context validation. A safe cheap version/context key is prerequisite
to a cache experiment. Existing `reuse_position_score` already uses bounded
decision-local planning-copy/pickle keys; measure that trade-off first.

### Conversion and graph size

This choice's authoritative state contains **121 cards**, **7,904 distinct
reachable objects / 944,382 shallow reachable bytes**, including 2,105 dicts and
2,232 lists. Its snapshot has **8,185 objects / 943,095 shallow bytes**,
**315,736 canonical JSON bytes**, or **316,884 with explicit card order**.
Cards contribute 225,094 encoded bytes, observations 50,391 and log 12,846.
The census excludes interpreter/global structures and allocator overhead; it is
not RSS or allocated bytes per clone. Immutable values are already shared.

Microprobes run with monitoring **disabled**, mean process CPU per call,
20 iterations (buffer operations 500), one state/host, no variance estimate:

| Operation | CPU per call |
| --- | ---: |
| Current selective copy, history excluded | 11.500 ms |
| Generic deepcopy, same history exclusion | 19.700 ms |
| Build complete snapshot | 14.043 ms |
| Canonical JSON encode | 2.900 ms |
| JSON decode | 2.500 ms |
| Snapshot deepcopy + deserialize | 35.098 ms |
| Preallocated ctypes/C buffer copy | 0.010 ms |
| Return native buffer as Python bytes | 0.012 ms |
| Snapshot → ordered JSON → native buffer → JSON → Python state | 37.294 ms |

State snapshot, RNG and card order match after the round trip. JSON decode
allocates fresh containers, so that path does not also pay the separate input
deepcopy in the deserialize-only probe; **do not sum the rows**. The current
selective copy is already **1.71×** faster than generic copying in this microcase.
The cheap C operation copies bytes, not Python object semantics; it is **not a
Rust object-graph copy benchmark**.

The **37.294-ms** JSON adapter is a measured possible conversion path, not an
unavoidable native-interface floor. But using it for every one of 284 copies
adds **10.591 seconds**, already above the whole AI choice before native work.
A credible kernel needs amortized/batched conversion, persistent native state,
or a carefully guarded Python-object interface. If Python rules need the full
Python graph back after every native clone, that benefit can disappear.

[PyO3's conversion documentation](https://pyo3.rs/main/conversions/tables.html)
distinguishes converting Rust collections from borrowing Python-native types;
borrowing a `PyDict` does not itself create a native state arena. Cython's
[extension-type documentation](https://docs.cython.org/en/latest/src/tutorial/cdef_classes.html)
explains the C-layout/direct-field alternative, which needs declared types and
interface work. Neither is a benchmark of this engine. A real prototype must
include all conversion, reconstruction, fallback and result-cloning costs.

## 3. CI: demonstrated imbalance; current per-test timing pending

Retained [green run 44019341176](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/actions/runs/44019341176),
attempt 1, source `1e8b4f321b03e36b667fd257d0a4dc5281ff3bf8`, has a qualified
**1,397-module / 38,115-identity** reference and four successful workers.
Counts are 38,016 call passes, 29 call skips, 70 setup skips and 380 passed
subtest reports; these categories are not added into extra test passes.
The maintainer is independently running a **38,075-node** timing cohort on
`e964503e`; its live JUnit files have **not** been read or treated as final here.
The rosters/sources differ, so old timings do not qualify the current tree.

Same-run diagnostic artifacts provide aggregate timing and top-20 slow phases
per shard, **not a duration for every test**. Inspected connector job summaries
confirm success but supply no job/step wall timestamps.

| Shard | Collected identities | Recorded phase seconds |
| --- | ---: | ---: |
| 0 | 9,287 | 3,389.155 |
| 1 | 9,317 | 6,444.239 |
| 2 | 10,358 | 4,291.304 |
| 3 | 9,153 | 2,383.867 |

Total **16,508.566 phase seconds**; maximum **6,444.239**, minimum **2,383.867**,
a **2.70×** imbalance despite similar counts. These sum setup/call/teardown
elapsed durations: **not CPU, worker wall or end-to-end CI**. Perfect four-way
redistribution gives phase-only ideal maximum **4,127.142 seconds**, at most
**1.56× / 35.9% reduction**, before indivisible modules and fixed overhead.
Weights may vary with runner speed/I/O/contention; not all imbalance is proved
to come from assignment.

Slow public definitions are validated against source; parameter values are
omitted. Sums below cover **exported top-20 entries only**, hence lower bounds
on complete function/module totals, not a complete module ranking:

| Public module / function | Exported phases | Sum seconds |
| --- | ---: | ---: |
| `test_live_bo3_series.test_seeded_live_ai_bo3_finishes_after_between_game_restore` | 2 | 954.255 |
| `test_human_bo3_terminal_restore.test_native_completed_series_survives_cold_read_without_sql_mutation` | 1 | 230.202 |
| `test_autoplay_seeded_games.test_seeded_strong_ai_game_accepts_complete_actions` | 3 | 151.467 |
| `test_training_environment.test_repeated_real_phase_trajectory_and_mid_episode_restore` | 3 | 150.602 |
| `test_static_aura_control_desired.test_paid_static_control_lifecycle` | 7 | 125.214 |
| `test_human_bo3_interactive.test_seeded_human_bo3_checked_http_cold_restart` | 1 | 122.422 |
| `test_training_mana_choice_coverage.test_chromatic_star_explicit_color_cost_departure_trigger_and_pending_draw_restore` | 2 | 106.021 |
| `test_human_bo3_native_swaps.test_native_swaps_between_checked_human_games` | 1 | 95.500 |

The live-BO3 function includes an individual **893.027-second call**, which extra
whole-module workers cannot divide. Duration alone does not distinguish CPU
from waits/I/O. A separate local 433-case adapter/pin subset took 94.926 seconds:
126 `test_interface_scope_76_mutations` rows contribute 52.929 recorded case
seconds; 39 `test_archetype_game_v3` rows contribute 24.188. This illustrates
non-game AST/pin work, **not its proportion across 38k tests**. The older AI
cohort has 85.071 seconds in 57 `test_ai_search_prefix` rows. These overlapping,
different-revision cohorts are not summed into a new suite result.

Cheap CI options:

1. **Timing-balanced whole-module assignment** after current same-run timings
   finish. Current source assigns sorted modules by `index % 4`, not time.
   Keep complete ordered identities, disjoint union, source/runtime binding and
   strict join; do not drop expensive cases. Historical phase imbalance makes
   this a better-supported first step than rewriting gameplay for CI speed.
2. Four→eight workers can halve an already balanced parallel test portion in
   the ideal case, not necessarily total CI or the imbalanced case above.
   Reference/collection/setup/install/join remain and runner cost grows. Four-
   worker assumptions exist in plan validation, ranges, artifacts and tests;
   editing only a YAML matrix would break qualification. Measure overhead.
3. Split slow modules only at safe fixture boundaries, preserving all cases,
   isolation and pinned/natural-cohort obligations. More shards cannot split
   that single 893-second call. No weaker integration games/mocks or budgets.
4. A PR subset can give early **advisory** feedback while retaining full main/
   tag qualification. Replacing a required full PR check is an explicit policy
   decision, not inherited full-suite success. Shared engine/fixtures, audit
   modules outside `backend/tests`, mutation guards and literal doc consumers
   make naive changed-file selection unsafe.
5. Investigate repeated static parse/read/setup only where timing proves it;
   retain mutation discrimination and fresh mutable fixtures. Rust gameplay
   does not automatically speed source guards, SQL/process checks or installs.
   No sharding, caches or gates changed in this spike.

## 4. Decision and next bounded step

Effort/risk is engineering judgment, **not a delivery-date estimate**. Expected
speed cannot be stated as an achieved gain without a prototype:

| Choice | Effort / risk | Measured basis and conditional speedup | Compatibility / what can break |
| --- | --- | --- | --- |
| Python changes first | Lowest for avoiding duplicate work; COW is a moderate/large representation change, not a shallow copy. Suitable for bounded PRs. | If copies become 2–5× faster: about 1.24–1.45× on this AI choice and 1.39–1.81× on this engine/AI subset; less on full harness. CI balancing has a separate 1.56× phase-only ideal bound. None is achieved here. | Alias isolation, custom copy hooks, RNG, order, mutable views and snapshot completeness. Pin-covered Python edits need a reviewed layered delta, not repinning away a failure. |
| Rust/Cython hot-path kernel | Moderate/high: typed representation or guarded Python-object kernel, fallback, stable batching interface, build/wheels/runtime closure and tests. | If copy+move services become 2–5× faster with negligible/amortized boundary cost: about 1.49–2.12× on this AI choice, 1.54–2.26× on engine/AI subset, but only 1.15–1.27× on generation+verification. Per-copy JSON conversion loses. | Transactional copies, Python subclass/protocol fallback, iteration/tie order, exceptions and persistence. Native packages need coordinated platform/hash-lock CI updates. Changed Python shims/call sites need pin layers; goldens, HTTP and cold saves must still pass. |
| Full Rust engine/AI rewrite | Highest: multi-subsystem port plus facade/migration risk, no defensible schedule from this spike. | Could accelerate more if state/search stay native, but no credible fixed gain is measured. Serialization, SQL/UI and source-guard CI costs survive unless separately changed. Not justified for this RC by these data. | Python object-facing APIs and ~38k Python tests, deterministic RNG, logs/choice ordering, all rules families, old JSON/saves and goldens. Existing tests may need a compatible facade before they can exercise native code. No permission to discard tests, old saves or pins. |

Recommended next proposal, **not implementation authorization**: one behavior-
preserving Python copy/immutable-metadata or query-reuse candidate, checked on
the exact copy contract, this matched choice and the same 128-action prefix.
Separately use the maintainer's completed current JUnit for timing-balanced CI.
If a justified bottleneck remains, prototype one guarded native kernel with
**conversion, reconstruction and fallback inside the timed boundary**. Require
full state/order/RNG/log fidelity and relevant pin/golden/HTTP/restore checks
before proposing any new registered measurement.

No reduced master search quality, incomplete cache keys, omitted fields/logs,
relaxed health threshold or casual RNG/order change is recommended. This
report closes no health/statistical/strength/RC gate and authorizes no game run.

Source entry points: [generation/replay](../../backend/scripts/archetype_game_v3.py),
[copying](../../backend/game_state/copying.py),
[AI projection/reuse](../../backend/ai/pending_effects.py),
[shards](../../.github/scripts/ci_backend_shards.py) and
[workflow](../../.github/workflows/ci.yml). Diagnostic scripts and aggregate
clock/size records remain private for operator review; no raw sample becomes
a public fixture or is advertised as a standalone public benchmark.
