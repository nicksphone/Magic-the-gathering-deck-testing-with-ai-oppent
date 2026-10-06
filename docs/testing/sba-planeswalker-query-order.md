# Planeswalker SBA Query Order

The planeswalker loop in `_apply_state_based_actions_once` checks battlefield
zone and nonpositive, nonmissing loyalty before querying effective types.
This is a pure-query short-circuit optimization, not a new SBA algorithm.
It retains the existing card iteration, controller lookup, departure events,
graveyard replacements, logs and subsequent waves. It adds no query scope,
cache, candidate list, action cap, search pruning or AI policy change.

Classification is still performed at each eligible card's actual position in
the loop. Earlier events, control changes and type-source departures therefore
affect later cards normally. A converted planeswalker with zero loyalty is not
put into the graveyard while its effective type is Land; removal of the type
source makes its current planeswalker type visible again.

## Ordinary Controls

`backend/tests/test_sba_planeswalker_query_order.py` uses existing committed
canonical rows, without changing Oracle text or fabricating gameplay cards:

- Both seats: healthy, off-battlefield and missing-loyalty objects avoid the
  unnecessary planeswalker-loop query; zero and negative-loyalty actual walkers
  retain exact original outcomes and events.
- Teferi, Hero of Dominaria and Nissa, Who Shakes the World cover dead walkers;
  Rest in Peace covers actual exile replacement and absence of a dies event.
- Song of the Dryads is actually cast and resolved through checked actions.
  The later loyalty-zero boundary is explicitly controlled setup.
- Controlled callbacks invoke real change-control/destruction handlers between
  departures. They test order, owner destination and refreshed later-card types;
  they are not claimed canonical death triggers or full legal game episodes.
- Ugin's actual payable loyalty activation consumes all loyalty, puts the
  source into the graveyard, retains the independent stack ability, restores
  the snapshot, and resolves that ability through checked priority actions.
- Baseline/candidate full snapshots, event order and restarted states compare
  exactly. Assertions forbid an active query cache across departure callbacks
  and replacement calls.

The reference restores only the old type-first condition in the current
function. No other rule, fixture, handler or action validation is weakened.
The two query-order assertions are ordinary strict failures on the original
condition, not xfails. The other18 controls already pass before the change.

```sh
cd backend
.venv/bin/python -m pytest -p no:cacheprovider tests/test_sba_planeswalker_query_order.py -q
```

## Measurement Boundary

Qualification is on published `14ffe1eac20303a5fcc0fa68d4e8e697ace0c28c` plus
this one-line change, in an independent source checkout. Although its entire
SBA file matches old E, its agent and engine differ. Old-E timings are context,
not current baseline measurements.

The current before/after benchmark restores the exact saved old-E tick95
stopped state with all IDs and snapshot fields unchanged. It uses cold current
agents, not the missing original HTTP agent memory. Two complete plain repeats
per version have a declared600s external wall bound each, no internal action
or branch cap. The comparisons include full before/after snapshots, offered
intents, chosen action, every recorded projected engine action and projection
entry counters. No UUID or gameplay fields are excluded. Diagnostic wrappers
are identical for both versions and forward current engine keyword arguments.

Completed measured outcomes and serial scoped neighbor qualification are
recorded in the verified NFS artifact's REPORT.md. The source/archive manifests
pin the actual code and shared interpreter dependency versions. This bounded
capture does not establish universal speed, full BO3 performance, matchup
balance, complete card support or full-suite readiness.
