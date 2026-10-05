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

Runner/replay selection passes 84 tests; the combined targeted selection passes
110. Mocked runner tests prove export and failure contracts, not game quality.
Exact frozen runtime `14737b19bb3a01deee4ed3aa93473a0fa5ad7a7d` passes 8,219
tests in all 332 recursive files once, with 649 matching backend/fixture hashes
across four isolated sources, initial databases absent. The full browser gate
passes including all three natural BO3 modes; frontend build/lint/test pass.
Qualification metadata leaves backend/frontend bytes unchanged. Broader
actual-game decision-quality review remains open.

## Observed Saved-Input Drift

The first retained actual run resolved in 20 turns/556 decisions with no matched
cost/target error logs and no passes while a land play was legal. Its inputs
were pinned legacy saved rows: Drain contained 24 Swamps instead of the current
template's 16 Swamps/4 Mountains/4 Badlands, while Tribal contained 28 Forests
instead of 20 Forests/4 Swamps/4 Bayou. Missing printed-color land support is a
confounder; Treasure or Collected Company can still provide alternative routes.
This is not proof that those cards are never playable or that AI played well.

Existing runs continue unchanged for reproducibility. A separate read-only
export pins the unchanged current templates, with all 23 card entries checked
against canonical local profiles; a new paired-seat retained-trace run is active.
No live decks/card records were modified to construct those inputs. Full review,
timing diagnosis and statistical AI-strength claims remain open. The corrected
forward sample repeats exactly in 20 turns/548 decisions without matched cost/
target error logs or passes when a land play was legal. It also reproduces
repeated failure to deploy affordable creatures with an empty friendly board;
236 preceding decisions reconstruct exactly to the first offending position.
The strategic planner's pending-announcement valuation is a separate repair,
not an undocumented policy change in this qualified catalog/trace runtime.

These offline files contain hidden hands and are not safe live opponent views.
Archive completed evidence on verified NFS; keep running source and SQLite local.
Trace retention does not prove optimal decisions, broad balance or expert AI.
