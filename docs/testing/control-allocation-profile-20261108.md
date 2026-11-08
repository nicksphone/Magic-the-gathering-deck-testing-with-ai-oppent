# Control allocation diagnostic

One separately declared current-source Master game between Dimir Control and
Blue Control reaches the unchanged 600-second single-game deadline after 998
committed actions, at turn 33. It has no winner and remains a resource-limited
partial game. This is a fresh diagnostic coordinate, separate from the original
[full matrix](full-master-matrix-20261108.md); neither run is retried or extended.

The backend archive is `71743f0d`, with 2,692 bound files, byte-identical to the
`91fd0a04` candidate's backend. Later backend changes need separate qualification.
Difficulty, 6,000-tick cap, full resource policy,
heuristics, weights and rules remain unchanged. The worker uses the default
heuristic environment without opt-in learned-policy overrides. Instrumentation
is `cProfile` around the existing production `run_game`, its existing stage
observer and a timed delegation to the ordinary decision-quality builder.

| Instrumented stage | Calls | Total seconds |
| --- | --- | --- |
| Legal moves | 999 | 15.30 |
| AI choice | 999 | 519.04 |
| Checked action application | 998 | 51.48 |
| Decision-quality builder | 998 | 7.69 |

The last choice finishes before the next deadline check rejects trace
construction; it does not commit an extra action. The longest profiled choice
takes 49.56 seconds. Nested `copy_match_state` calls consume 258.06 cumulative
seconds over 13,695 calls, overlapping the stages above. Strategic line/state
evaluation and stack lookahead also appear prominently in the cumulative
profile. These overlapping figures must not be added together.

This points further performance investigation toward AI planning and copying;
quality recording is a small share of this instrumented execution. It does not
measure uninstrumented latency or establish a speedup. In particular, hundreds
of millions of small calls incur profiler overhead, so a prospective optimization
needs an uninstrumented comparison, exact action/state/RNG preservation and the
existing copy-protocol/hidden-input controls before adoption. No optimization,
policy change, AI-strength result or completed-series acceptance is claimed.

The worker's additional conservative post-run `checked_result` call also rejects
with dimension **deadline**, using the already expired budget. The resulting
exit status is one. This is not evidence of an oversized public API packet;
the diagnostic's private full-log result differs from the round-robin packet.
The supervisor closes normally after about 610 seconds, reaps its direct child
and verifies the process group is absent. It does not hit its 660-second outer
limit or terminate a still-running worker.

Independent receipt verification checks all 998 trace/tick counts, raw and
normalized hashes, stage/pstats agreement, runner pin, input equality and all
2,692 source hashes. A separate read-only reviewer confirms source/current-tree
equality, runner/helper pins, stage/pstats metadata, deadline attribution and
normal process closure, with no findings and no private game-body inspection.
SQL, network, children and protected owner/model bodies are
denied before imports; no denied events occur. The private raw game remains
private. An earlier setup attempt used the archetype label `Control` as a deck
name and stopped before match construction; its error and closure are retained,
with zero games spent. The corrected attempt starts one game and has no game
retries. Evidence remains under
`/home/nick/mtg-rc-evidence-20261108/control-profile-71743-v2/`, with the original
setup failure and attempt ledger alongside it.
