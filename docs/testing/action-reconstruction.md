# Offline Recorded-action Reconstruction

`analytics.action_replay.reconstruct_game` rebuilds a seeded diagnostic game from
resolved decks and its complete `AI TRACE` log. It does not call an AI agent,
sync cards, create an API match or access the live database.

Before each action it compares actor, turn, step, priority, active player, hand,
battlefield and generated legal action types. It then executes the recorded action
with rejection enabled. Complete normalized event logs, their hash, winner, final
turn and tick count must match. The first divergence identifies the decision and
field, or includes the existing first-log-divergence context. Invalid records and
rejected actions cannot produce a successful reconstruction.

## CLI

From `backend/`, using a retained `run_match` packet and its exact two-deck resolved
manifest:

```sh
.venv/bin/python scripts/reconstruct_action_replay.py \
  --deck-manifest /path/to/pair-input.json \
  --trace /path/to/execution.json \
  --output /path/to/private-reconstruction.json
```

Use `--reverse-seats` when the retained execution swapped the manifest's deck
order. Input manifests are validated with the same corpus-hash and resolved-data
contract as the deterministic matrix runner. Outputs cannot overwrite either
input. Exit codes: `0` matched, `1` first gameplay/log divergence, `2` invalid input
or I/O. Standard output contains only status, verified-game count and output path;
the report can contain private hand/log data and must remain private.

## Checks

Twenty-one isolated checks pass: both starting seats, no AI search or input
mutation, first hand/board/actor/phase/action/legal drift, event/hash/terminal
checks, malformed metadata and real subprocess CLI success/failure/overwrite
protection. The card fixture uses canonical Islands; it is not a competitive deck.
A complete retained Control/Ramp game also passes the real CLI. Strict
reconstruction of the original thirty logical samples matches twenty-six and
rejects four recorded casts. Three omit a required permanent target; the fourth
announces both a player and a planeswalker for a single-alternative spell.
These failures are useful discoveries, not a passing thirty-game legality gate.

The earlier frozen application backend and AI regression matrix did not import
this additive diagnostic. Their results do not include its twenty-one tests.
The latest frozen-source full suite includes the diagnostic: all 7,467 backend
checks pass. Strict reconstruction of its new thirty-sample matrix matches
twenty-nine games and rejects one Searing Blaze cast at decision 113, when no
creature target is announced. Complete repeated packets agree independently;
that repeatability does not excuse the rejected action or establish legality.

## Known Limitations and Next Upgrades

This validates engine execution of recorded actions, not whether those actions
were strategically best. Cast-pass and land-pass counters are review opportunities,
not automatic mistakes. Rebuilding changed-source records may correctly diverge;
retain engine revision and canonical inputs alongside logs. Live API/human event
streams without this seeded diagnostic contract need separate adapters. Replayed
effect correctness still depends on the supported rules engine.
