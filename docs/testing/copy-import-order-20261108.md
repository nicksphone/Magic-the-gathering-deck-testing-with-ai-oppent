# Copy prefix initialization and import order

Importing `game_state.copying` before `typing` froze three `copyreg` entries.
Later AI imports added the standard `ParamSpecArgs` and `ParamSpecKwargs`
reducers. The unchanged whole-registry equality guard then disabled the native
Card metadata prefix, despite no existing entry changing. A captured-state probe
confirmed zero prefix calls and 7,278 standard keep-alive calls in that order.

The copier now initializes those standard reducers before freezing its layouts.
It preserves any caller's preexisting reducers for the two colliding types by
identity. This matters when the C types were obtained from `_typing` before the
higher-level module was imported. Later registry changes still trigger the
existing conservative fallback. Registry equality, native-binding checks,
foreign-code latching, caller memo behavior and copy algorithms are unchanged.
No policy, search/resource limit, mutable-field isolation or information boundary
changes.

## Regression and review evidence

The initial three-case module reports one intended failure (copier-first) and
two passes on unchanged production. The first initialization correction makes
all three pass. Independent review then identifies that a bare eager import
overwrites preexisting reducers. Two new controls reproduce that finding:
**2 failed, 3 passed**. Preserving the prior bindings produces **5 passed** in
0.43 seconds, zero failures, errors or skips.

Each control uses a bounded fresh `-I -S -B` interpreter; pytest itself has
already imported `typing`, so a same-interpreter test would miss the defect.
Synthetic metadata measures actual prefix/keep-alive operations without claiming
Magic card support. Workers prohibit SQL, sockets, child processes and protected
owner/model-body opens before project imports. The late custom reducer still
executes through fallback, while both preexisting standard-type overrides retain
their actual copy output.

The final-source pure cohort passes **235 tests in 24.10 seconds**, zero
failures/errors/skips, across these complete modules:

```text
test_copy_atom_prefix.py
test_copy_dict_preflight.py
test_root_metadata_copy_contract.py
test_root_copy_preallocation_protocol.py
test_root_copy_registered_set_protocol.py
test_ai_selective_copy.py
test_nested_card_copy.py
test_ai_information_boundary.py
test_card_observation_memory.py
test_checked_action_copy_route.py
```

All 2,877 bound backend/audit files match before/after; the preimport audit records
zero denied SQL/socket/process operations. These include existing memo overrides,
alias/cycle, root reconstruction, foreign hooks, registered set protocols,
keep-alive exceptions, dynamic field hooks, hidden-input and checked-action
controls. Two dependency deprecation warnings remain visible. Independent review
accepts the corrected source, tests, bindings and evidence with no remaining
findings. The first passing source and its review defect remain retained.

## Captured-state comparison

The earlier [Control diagnostic](control-allocation-profile-20261108.md) has a
lossless execution record. Its entire 998-action partial reconstructs exactly,
including final event/hash/turn/winner checks, in 20.40 seconds. This spends zero
AI choices or natural games. Three private pre-action snapshots retain ticks 1,
581 and 845; capture leaves each authoritative root unchanged.

After final protocol and decision workers close, a separate copy-only epoch
uses the final frozen 2,694-file backend. Each state has nine rotated rounds,
five copies per mode per round (45 copies per mode). The worker is pinned to CPU 3;
audits remain active but no call profiler runs. The original matrix remains on
its separate CPU and unchanged source.

| Captured tick | Card instances | Retained baseline planning copy | Final native copy | Final supplied-empty-memo control |
| --- | --- | --- | --- | --- |
| 1 | 120 | 7.001 ms | 5.747 ms | 7.009 ms |
| 581 | 120 | 12.854 ms | 11.528 ms | 12.790 ms |
| 845 | 122 | 17.210 ms | 15.764 ms | 17.220 ms |

These are local medians per copy, not whole-game speedups. All modes produce
the same complete pickle graph as history-free stdlib deepcopy, and preserve the
source root/RNG. Baseline and final fresh Master choices each select the recorded
action; the final complete decision and resulting fresh-agent history equal the
baseline. The final choice takes 20.90 seconds while the protocol cohort is also
running, so that timing is a latency witness and behavior check, not clean paired
speed evidence. The quiet copy-only epoch makes zero additional AI calls.
The retained baseline and two candidate source revisions each spend one fresh
qualification choice. The reviewed candidate is measured again because its
reducer-preservation correction changes production initialization; the first
candidate is retained separately. These are three diagnostic choices, zero new
natural games, and no repetition of the original matrix or profiled game.

Original whole-game agent history was not captured. These fresh-agent checks do
not reproduce that history or establish strength. The approximately twenty-one
second decision and practical latency acceptance remain open, alongside complete
games, broader source qualification and all RC gates. Earlier ASGI/data/profile
results retain their `91fd0a04` source boundary.

Private declarations, both red/green epochs, source maps, JUnit, capture and
benchmark/closure receipts remain under
`/home/nick/mtg-rc-evidence-20261108/copy-import-order/` and the adjacent
`control-capture-91fd/` / `control-copy-benchmark-91fd/` roots. No raw game or
snapshot bodies are committed or made public fixtures.
