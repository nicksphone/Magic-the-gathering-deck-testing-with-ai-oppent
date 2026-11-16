# Stopped v3 trace1 pilot: diagnosis and evidence scope

The operator confirmed termination before authorizing this read-only analysis.
Run `archetype-pilot-20261116-v3-trace1` used source
`54c50a91becc629f868f0b2a09814bf35a97e297`. Raw traces, snapshots, actions,
hands, logs, requests and DBs remain private; none is copied into this document
or the tests. The plan was not resumed or rerun.

## Why it stopped

`PILOT-INCOMPLETE.json` accounts for **12/36** cells: nine resolved, one
`replay_divergence`, one `timeout`, one `error`. `complete` and `usable` are
false; `budget_refused` is false. The three forecast fields remain null.

Cell **010** caused the fail-fast stop. Its game completed, but the verifier
returned 1 with `replay_divergence` at **zero-based action 647** (the 648th
accepted action), mismatching `after_sha256` and `log_delta`. The documented
controller policy sets the shared stop event on a verifier/protocol failure.
It then stops the concurrently running peer, cell **011**, and admits no further
cells. Thus 24 cells never started; they are not completed games or draws.
Cell 001's earlier trace quota refusal did not itself stop the controller.

The final report records 2,786.746 controller wall seconds and 5,573.491 charged
worker-slot seconds, with 167,226.509 campaign seconds remaining at that report's
measurement point. This is not summed child CPU or a usable performance forecast.
The registry ledger, not this rounded report, governs any later admission.

## Replay divergence: adapter ordering loss

The in-place diagnostic used the exact recorded interpreter/distribution identity
and an unchanged checkout of the run's source. It read the original trace without
copying it. The whole cell-010 trace hash matches its game receipt; its 773
records/771 accepted actions authenticate under the original v3 record chain.

A **single real transition** from action 647's full checkpoint reproduces the
failure; no AI search or game replay from the opening is needed:

1. Deserialize that checkpoint's `before` snapshot and request legal moves.
   The canonical before-state and legal-move hashes match the recorded action.
2. Execute the recorded `choose_mechanic` combat-damage assignment through
   `checked_action`, then capture the resulting complete snapshot.
3. The resulting snapshot differs from the recorded `after` in **`log` only**.
   The log delta has the same five entries as a multiset, in a different order:
   four simultaneous state-based departure messages and one trigger-publication
   message. RNG, progress and other recorded state values match.
4. A causal control reconstructs the 120 initial cards' insertion order from the
   same factory inputs and places the ten later cards after them. Canonical
   before-state/legal hashes remain identical, and the **entire recorded after
   hash now matches**, with no differing fields. This is a diagnostic control,
   not a trace rewrite or permission to accept a modified result.

The diagnostic bounds were 30 CPU seconds and 45 wall seconds per process. The
one transition took about 0.145 CPU seconds without profiling; timing here is
reproduction evidence, not a pilot forecast. A separate reverse-order control
also changes graveyard-list order, illustrating why arbitrary reordering cannot
be dismissed as harmless everywhere.

### Cause and classification

`archetype_game_v3.capture` canonicalizes JSON with sorted keys and reconstructs
its `value` from those bytes. Canonical trace encoding also sorts nested object
keys. The verifier deserializes those values after every action; the game phase
keeps its native `state.cards` insertion order. The canonical hash does not
represent that order, although the engine can observe it on the next transition.

`state_based_actions._apply_state_based_actions_once` builds lethal candidates
from `state.cards.items()`. `_resolve_lethal_creature_batch` logs/moves them in
that iteration order. The normal application persistence path uses unsorted
`json.dumps(serialize_match_snapshot(...))`, preserving native mapping order.

This is **adapter-induced loss of an engine-observable representation**, not
random AI/RNG behavior or evidence of a different winner at action 647. It is
not an expected difference that may be ignored under the declared exact replay
contract. Sorting/omitting logs or relaxing equality would conceal the defect.
The stopped run remains unusable after diagnosis.

The approved adapter-only fix records ordered card IDs separately from canonical
snapshot values/digests, authenticates order evidence, and restores it at replay
and selected handler/SQLite boundaries. It leaves rules, AI and historical pins
unchanged. A new trace format/policy, source revision, run ID and issued plan are
required before any further pilot; no new run is authorized by this report.

Public regression command (declared combat fixture, not private pilot data):

```sh
cd backend
python -B -m pytest -q tests/test_archetype_game_v3.py \
  -k real_simultaneous_sba_deaths
```

The fixture makes real attacks, blocks and damage choices using complete public
Grizzly Bears/Runeclaw Bear printings. Against the old adapter, it fails at
zero-based action 2 with `after_sha256` and `log_delta`; generation's native full
state digests agree with v2. The order-preserving candidate makes that replay
pass without editing the engine, log contents or expected digests. Broader
candidate test results are separate from the pilot's failed result.

## Cell 011: censored peer, not an independent exception

Its game child was sent SIGTERM and actually waited: return code **-15**,
termination `cancelled`, 107.607 measured CPU seconds and 108.709 wall seconds.
There is no `game-result.json`; stderr is empty. Consequently there is **no
recorded Python exception class or child traceback frame** to report. The
relevant controller path is `run_process` observing the shared stop event and
calling its termination/reap routine; inventing an engine exception would be
incorrect.

Its progress receipt binds 304 accepted actions. The intact authenticated trace
contains 308 accepted action records, ending at turn 11 / declare attackers.
The four later records do not extend the last progress receipt's CPU-category
attribution. The interrupted operation is unknown. Treat this cell as censored;
its `error` summary label is not an additional demonstrated engine bug.

## Cell 001: trace quota, not CPU or wall exhaustion

The worker returned 1 with `error: trace_limit`; stderr is empty. Measured CPU is
**985.111 seconds**, cell wall is **989.636 seconds**, below the shared 1,200 CPU
/ 1,500 wall ceilings. Verification never started and no final outcome exists.

The trace has **65,890,540 bytes** and 1,151 intact authenticated action records
(indices 0–1150), ending at turn 40 / declare blockers. Its last progress receipt
binds 1,136 actions; report both numbers rather than treating a stale progress
counter as the final trace count. The 64-MiB quota refuses the whole next record
before writing, so a stopped file can be smaller than 67,108,864 bytes. The
refused record's exact byte size was not persisted and is not reconstructed here.

This is a resource-limited incomplete cell, not a loss, draw or evidence that the
new CPU budget was exhausted. A new quota proposal must be predeclared for a
new plan, retaining this failure and the campaign charge.

## Nine accepted resolved cells: accounting only

All nine have successful verification and `parity_checked: true`, with life
termination. These are the final cell-result statuses, not ten game-phase wins:
cell 010's game outcome was not accepted after verification failed.

| Cell | Final turn | Accepted actions | Winning physical seat |
| --- | ---: | ---: | ---: |
| 000 | 21 | 568 | 1 |
| 002 | 29 | 813 | 1 |
| 003 | 22 | 653 | 2 |
| 004 | 21 | 708 | 1 |
| 005 | 18 | 533 | 2 |
| 006 | 29 | 810 | 1 |
| 007 | 20 | 572 | 2 |
| 008 | 16 | 499 | 2 |
| 009 | 17 | 533 | 1 |

That is 5,689 accepted actions, turns 16–29, 499–813 actions per game, and five
seat-1 / four seat-2 wins. These are **counts, not a win-rate/strength estimate**.
They are a selected, incomplete portion of the declared schedule. Do not drop
the other cells to compute a completed-game forecast, matchup result or
statistical/RC acceptance. The full pilot remains `usable: false`.
