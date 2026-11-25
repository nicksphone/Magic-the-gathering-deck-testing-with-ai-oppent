# Optional C++ kernel for AI metadata copying

This design scopes a prototype for review. The regular Python copier remains
the reference. Use CPython 3.12 and pybind11 after Python 3.12 development
headers are available and a compatible build input has been approved.
This design supplies no implementation or dependency update.

## Select the boundary after profiling

The first candidate is the qualified card-metadata prefix in
`game_state.copying._copy_card_field_prefix`, called from `copy_match_state`.
Reprofile the merged exact-copy and query changes before selecting it.
Extend to the existing root metadata traversal only if the first prototype
passes parity and profiling shows that the additional boundary pays off.
Leave `ai.pending_effects.planning_copy`, `ai.information.decision_view`,
and `rules_engine.action_validation.checked_action` on the Python entry
points. The caller still constructs the redacted AI view, qualifies native
dispatch, allocates root and card shells, and handles overrides and history.
Rules, legal-move generation, effects, AI policy, and serializers are
outside the first prototype.

In the earlier cycle position, copying took 2.40 of 6.19 AI CPU seconds
(38.8%). The source graph had about 7,900 reachable objects and 944 KB
of shallow sizes. A history-free Python copy averaged 11.5 ms on that
position. An ordered JSON round trip through a native buffer averaged
37.3 ms. Prefer a direct Python-object kernel with one boundary crossing
per qualified batch. A 2× improvement across the *entire measured copy
slice* predicts about 1.24× on that old decision. Accelerating one metadata
subset predicts less. The relevant measure is whole-call CPU with
qualification, allocation, conversion and fallback included. See the
[paired performance spike](python-native-performance-spike-20261117.md).

## Proposed interface and fallback

Use one private call from the qualified Python copy path. Pass original
ordered card field dictionaries and the relevant preallocated memo
entries as Python objects. Return a completed batch and ordered memo
additions, or an explicit unsupported status. Both results are private to
the caller. The Python wrapper publishes a successful batch to the
existing card shells and memo. It begins the ordinary Python walk from the
original prefix on unsupported input.

- Keep the GIL, hold owned references with RAII, and check exact types.
  Accept exact lists and dictionaries containing exact atomic values or
  supported containers. Share the Python reference to each admitted
  immutable value. Require exact built-in immutable dictionary keys;
  treat `Zone` as an immutable value only when the guarded Python binding
  identifies the known class. Let Python handle sets, tuples, subclasses,
  and unknown keys in the first prototype.
- Treat the original memo and input graph as read-only. Use an identity
  overlay seeded with the preallocated root and card memo entries. Insert
  a new container in the overlay before visiting children, so cycles and
  aliases resolve to the right shell. Preserve source item order and
  Python's original keep-alive ordering. A reference to the root object's
  attribute dictionary must remain distinct from the new object's actual
  attribute dictionary wherever the reference copier keeps them distinct.
- Keep Python's guards for exact classes, descriptors, dispatch tables,
  stock copier and reducer bindings, fresh caller memo and default
  field copier. A caller-supplied memo or alternate field copier always
  uses Python. Preserve history inclusion/exclusion exactly. A miss must
  leave the input, keep-alive list, existing memo and shells untouched.
  Bound traversal with an explicit depth/work guard and return unsupported
  on a guard miss.
- Avoid custom Python callbacks during the supported traversal. The design
  review must account for CPython allocation and finalizer reentrancy in
  addition to key equality/hash behavior. Match existing exception ordering.
  Allocation errors and failed internal invariants propagate. Unsupported
  input is a separate status and cannot mask an error.
  [pybind11 GIL documentation](https://pybind11.readthedocs.io/en/stable/advanced/misc.html#global-interpreter-lock-gil)
  [CPython reference counting and finalizers](https://docs.python.org/3.12/c-api/refcounting.html#c.Py_DECREF)

Start with an explicitly selected diagnostic path, then add a gated
runtime opt-in only after differential tests. Keep the Python path when
the extension is absent, disabled, or unsupported. Verify the ABI and
runtime identity in future native build/driver qualification. Existing
source-pinned modules need reviewed layered updates for any eventual
dispatch integration.

## Differential tests before any adoption

| Layer | Controls and required comparisons |
| --- | --- |
| Graph and memo | Compare against the current Python copier and applicable stdlib reference fixtures. Check exact values and dictionary order, alias equivalence classes and cycles, distinct root/attribute-dictionary semantics, cross-card and card-to-root aliases, and mutable sibling/source isolation. Exercise explicit memo replacements, immutable empty containers, and history kept or omitted. |
| Protocol fallback | Cover dict/list subclasses, custom keys/reducers, registered set protocol, custom field copier, monkeypatched class descriptors, recursive depth bounds and throwing hooks. Confirm no partial native writes, exact hook sequence and exception class, and reuse of the untouched Python fallback. Validate native hit and miss paths separately so silently never dispatching cannot pass. |
| Information and RNG | Verify hidden-card redaction and observation order, exact RNG state and next draws, persisted lookups, and unchanged inputs in both routes. Future allocations or fallback must preserve authoritative state. |
| Decisions and transitions | Use the archived normal and timeout positions privately. Compare complete ordered offers, exact choices, accepted and rejected action outcomes, full ordered snapshots and log deltas. Include simultaneous state-based actions, tied ranking, costs, and pending choices. Compare both copy routes from identical inputs in alternating order. |
| Integration | Run the copy protocol, checked-action copy, AI information, AI decision, replay, selected handler/SQLite parity, health/strength and interface-scope suites. Require equality on all admitted test cases, including branch-global alias tests that normalized JSON cannot represent. Test compiled and Python-only jobs separately after implementation. |

Report per-corpus native hit rates, time spent on admitted copies and
fallback, boundary CPU, peak memory, and paired whole-choice CPU.
Benchmark normal and tail positions separately using fresh agents and
unlimited policy in both builds. A proposed adoption threshold is at
least 10% less median decision CPU on the declared tail corpus and no
more than 5% regression on the normal corpus, alongside exact parity.
Use the same checkout and hash-locked environment plus the separately
recorded extension build. Report median and tail latency on repeated
paired runs. Keep the Python path if graph fidelity or whole-choice
performance fails the gate. Consider a later kernel for a profiled,
pure rules query only after isolating its input and measuring the
Python/native boundary.
