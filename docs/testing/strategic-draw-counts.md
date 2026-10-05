# Strategic Draw Counts and Private Replay Views

## Planner Contract

The strategic horizon may value a guaranteed draw count in an already masked AI
decision view. The real engine resolves the announced stack on an isolated copy;
unseen cards remain unknown. Only announced draw/counter instructions qualify.
The library may lose only unknown objects transferred to the corresponding
hand, preserving the remaining order and existing hand prefix. Search, mill,
reordering, known identities and unresolved choices retain conservative fallback.
Draw limits, actual announced counters and drawing from an insufficient library
use the engine's outcomes, not an invented average card or forced deck winner.

The opt-in belongs only to strategic valuation. Default projections and
certainty helpers stay strict. Root scores already computed by callers are
reused in stack-response deltas; this is not a persistent mutable-state cache,
reduced search depth or a change to legal actions.

## Private Diagnostic Export

`backend/scripts/reconstruct_action_replay.py` can export both players' actual
hands and boards before recorded actions without calling AI search:

```sh
python backend/scripts/reconstruct_action_replay.py \
  --deck-manifest /path/resolved-decks.json --trace /path/retained-run.json \
  --output /mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/new-run/report.json \
  --decision-output /mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/new-run/decisions.jsonl
```

Create the fresh output directory on the verified NFS share first. Active source
and SQLite stay local. Use `--reverse-seats` for a retained swapped-deck run.
The trace must be a retained `run_match` JSON packet with complete per-game roots
and logs; a trace-export JSONL record's `result` is that packet.

New output files are exclusively created with owner-only permissions. Existing
evidence, input aliases and colliding outputs are rejected. JSONL starts with
schema version 1/provenance, carries game/seed/starting-player and decision
indices, and ends with verification status. An absent end record means incomplete
export; a divergence is not a successful reconstruction. Completed prefixes are
flushed so failed later work does not erase evidence.

Card views reuse the canonical UI serializer, detached even for nested faces.
Records add ownership, actual zone and raw counters; player views include mana,
snow/restricted mana, life/poison, library count and land-use counters. Announced
stack and combat assignments are included. Library identities are not exported.
These are private offline views: never a public API, AI input or training signal
that authorizes looking at opposing hands. Available casts/passes alone do not
prove misplay or optimality.

## Validation Status

- Combined focused selection: 135 checks pass; expanded information/projection,
  pending effects, strategic response and replay contracts: 356 checks pass.
- Final replay CLI/observer selection: 30 checks pass, including two-game seed
  attribution, existing-file/symlink protection, private modes, effective/base
  stats and mutation isolation for real modal-card face metadata.
- Final canonical retained reconstruction: 12 executions, 8,344 accepted
  decisions, matching logs/outcomes; six unique paired-seat samples contain
  4,172 decisions. Rich exports are byte-identical between repeats and private
  file permissions are verified. Repeated runs are not independent samples.
- Frozen `80062da`: 8,384 backend tests pass in all 339 recursive files once,
  with all 660 hashes matching four initially DB-empty source copies. Frontend
  tests/lint/build and the full browser harness/all three natural BO3 modes pass.
- Fresh candidate comparisons are running against the unchanged pinned inputs
  for Drain/Tribal, Tokens/Ramp and Tempo/Control. The release stays isolated until
  those new decisions and outcomes have been reviewed; main remains `8eeecd1`.
- Fresh candidate AI decisions and before/after decision quality remain open;
  repeated reconstruction is not a new independent game or balance sample.
