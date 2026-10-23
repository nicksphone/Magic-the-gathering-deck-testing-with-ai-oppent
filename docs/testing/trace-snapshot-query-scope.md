# Snapshot-Local Pure Query Reuse

This follows the single power/toughness-pair correction. Native profiling on
unchanged `6a6d7f14` found 34 genuine continuous-source body invocations for a
17-permanent trace. The existing pure-query cache was not shared across rows.
No historical deadline cause or speedup ratio is inferred from that sample.

Only `_battlefield_snapshot` and one import change. Its original comprehension
is wrapped in the existing `rule_query_scope`. The comprehension AST and exact
inverse module bytes are preserved, as are every other production function.
The snapshot result itself is not cached. If an enclosing same-state scope
already exists, it remains caller-owned; otherwise the new scope ends on normal
or exceptional snapshot exit. Mutable output lists remain independent.

Seven new ordinary unittest methods ran against unchanged production first:
four passed and three failed solely on source-body counts (8 versus 2, or 16
versus 4). Wire bytes, real knowledge usage and root/RNG checks passed before
those count failures. The same seven then passed with the correction, including
empty boards, both seats/noncreatures, fresh counters, aliases, nested ownership
and exception restoration. No existing tests or assertions change.

The bounded local runner passed 18 denial controls and observed no unexpected
I/O during either native run. Source, descriptor, Python/OS-thread and child
checks passed, and actual processes/unit and scoped file handles closed.
One delayed parent closure check led to a mislabeled archival preimage; its
immutable original remains, with a separate correction recovered from exact
Git bytes and joined to the actual RED loaded-origin/profile hashes. No native
run was repeated or relabeled to conceal it.

The observed four-card test work drops from eight source rebuilds to two.
The 17-card profiled scene has not been rerun on this correction. These checks
are not natural-game, deadline, log-cap, AI-strength, whole-CI or RC acceptance.
All 14 game resource ceilings, shared BO3 deadline, full trace fields, policy,
metrics and privacy remain unchanged. Private game traces are not public input.
