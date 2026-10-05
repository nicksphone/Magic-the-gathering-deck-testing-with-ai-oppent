# Catalog Identity and Successful Replay Traces

## Catalog Contract

Repository deck ordering is descending creation time, then descending ID.
Built-in refresh and expansion references preserve the first normalized name/
source identity instead of overwriting it with an older duplicate. Expansion
records are refreshed by their source as before. No row deletion, ID migration
or alteration of user decks is introduced. Historical rows stay available.

Three new catalog regressions initially failed. The expanded targeted selection
passes 26 tests, including SQLite timestamp ties, newest-record refresh, the
deck API's visible result, expansion references and preservation of older rows.

## Trace Contract

```sh
python scripts/regression_matrix_replay.py --deck-manifest pinned-decks.json \
  --matches-per-pair 2 --best-of 1 --max-ticks 2400 --progress \
  --output matrix.json --trace-output decisions.jsonl
```

The optional new JSONL file starts with input provenance, difficulty, tick cap
and protocol. Each completed run is written and closed before its repeat starts.
Run records include seed, seat identity, repeat number and full match results,
including existing actor-hand/battlefield/action traces and game logs. This
retains resolved games rather than only anomalous games. A crashed incomplete
run is not represented as completed. Existing paths are rejected, as are
collisions with summary/progress/input/export paths. Default reports remain
compact, with two repeats per logical sample, not two independent balance wins.

Runner/replay selection passes 84 tests. Mocked runner tests prove export and
failure contracts, not game quality. Frozen combined full qualification and
actual pinned-deck retained-trace review are pending.

These offline files contain hidden hands and are not safe live opponent views.
Archive completed evidence on verified NFS; keep running source and SQLite local.
Trace retention does not prove optimal decisions, broad balance or expert AI.
