# Per-card attachment SBA classification batching

## Scope and source

The only production change is in
`backend/rules_engine/state_based_actions.py::_apply_attachment_state_checks`:
one existing `rule_query_scope(state)` encloses the three calls to `is_aura`,
`is_equipment`, and `is_fortification` for one battlefield permanent. It closes
before target validation, bestow changes, detachments, zone changes, or log
writes. The function is not a generator. Each next card gets a fresh scope;
there is no cache across deaths, control changes, layer changes, or SBA waves.
This does not authorize calling mutable SBA processing from an outer query scope.

The isolated baseline was restored from the already qualified six-patch source:
`combat-replacement-requalification/20261006-sixpatch-50a7e6d/qualified-source.tar.gz`
under the project's NFS archive root. Its SHA256 is
`a516014174290430fcfd08f8b0af0e922555f1840c3a3b66b5764025f8bd1dfb`.
That source preserves parent private HEAD
`50a7e6dfec572eba6f839ab85161528bd0811fad` plus the previous qualified replacement
optimization and separate replay-spy adapter. This is not a new committed-main
baseline or a relabeling of the earlier performance archive. No parent/main,
AI, mana, engine, validation, schema, frontend, or frozen layer-helper edits.

## Whole retained decision

Same full canonical Tokens/Ramp snapshot: seed2225858263, turn31/tick902,
seat2, DeclareBlockers, 32 battlefield permanents. Input SHA256:
`4f5209b6a76a5d556a71b94fdd6ed39bf4bae232a1d88b5dfd674844232ef81e`.
The earlier diagnostic reconstructed this input twice through 901 checked
actions; metrics alone were not used as a snapshot. Every evaluation uses the
same fresh master-agent protocol because original agent-private history was
not available. No natural-game restart or earlier-choice regeneration.

Serial unprofiled ABBA runs, each bounded by a 420-second watchdog:

| Run | Baseline seconds | Patched seconds |
| --- | ---: | ---: |
| First pair | 44.808203 | 40.296249 |
| Reverse-order pair | 45.065567 | 40.549590 |
| Mean | 44.936885 | 40.422920 |

Measured incremental whole-decision reduction: **10.05%, 4.514 seconds**.
Other workers were active; two pairs on one snapshot do not establish a
universal speedup or resolution of the original natural-matrix timeout.
The setup-overlapping preliminary timer is retained but excluded from this mean.

Both complete profiles retain all 256 intents and 256 successful projections.
Every projection's full before/after snapshot is byte-identical; decompressed
stream SHA256 is
`7e943b61780a318b442841ae49e518fc731a7d328349baa72f1f83bb73f6f34c`.
SBA applications remain 1509 and attachment-check waves remain 1818 in both.
No search alternatives, legal responses, triggers, or SBA waves are removed.
Full instrumented profiles take 142.620s and 134.661s; profiling/recording
overhead is not part of the speed claim. Attachment-check cumulative profile
time is 15.280s versus 5.305s (overlapping profile costs must not be summed).

All six runs choose the same announced block: p1-029 by token04a and p1-025
by token04d. Every full checked applied snapshot is byte-identical, SHA256
`7f7d56dc9b732b97d78e1e794f97bbc10646f7a353615912fb156cc3ef57bcdf`.
These snapshot hashes also match the prior frozen archive. Input roots remain
unchanged. On this retained board, actual classification queries decrease from
6144 to 1024. Sixfold query-work reduction is **not** sixfold elapsed speed.

## Qualification and limits

- 14 new ordinary baseline contract failures become 14 ordinary passes;
  the red assertions concern absent query scopes/work reuse, not gameplay bugs.
- Both seats: actual canonical equip, bestow, Spreading Seas, and checked legal
  main-phase Song resolution. No Oracle edits or fabricated card fixtures.
- Controlled seams are labeled: Song removal, invalid-attachment/source death
  earlier in the same wave, controller change, and host departure. They are not
  claimed as complete legally played removal/control episodes.
- Classification scopes assert full state immutability and closure before
  target validation, graveyard moves, and bestow endings. Every wave compares
  complete state with an unbatched reference and with a restored snapshot.
- 1614 ordinary passes in 280.72s across 69 complete modules, including all
  inherited 1553 cases and 95 HTTP-named cases. No exclusions, deselections,
  skips, xfails, errors, or failures. Existing fixtures are unchanged.
- Snapshot roundtrip, both-seat hidden-information counterfactuals, and three
  malformed-action immutability checks pass. Existing `blocks: []` still raises
  AttributeError rather than ActionRejected; this is not fixed here.
- No dedicated canonical Fortification golden was added; its existing branch
  is retained. This is bounded qualification, not complete card/layer coverage,
  browser qualification, full-game completion, or policy-quality evidence.

Used `/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python`, Python3.12.3;
all eight requirements pins match. No installs or external services. Decision,
projection, focused, and privacy harnesses forbid SQLite and network sockets.
The full serial HTTP gate permits only fresh checkout-local API SQLite,
in-memory SQLite, and owned local `owned-test.sqlite` fixtures: 212 audited
connections, zero escapes/blocked requests. Databases stay local while active.

## Reproduction and handoff

The verified archive is
`combat-sba-classification-query-batches/20261006-sixpatch-50a7e6d-lrS1TO`
under `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/`.
It preserves `baseline-source.tar.gz`, `qualified-source.tar.gz`, production
and three-file integration patches, source hashes, interpreter pins, raw JUnit,
all timers/profiles/full projection states, SQLite audit/integrity receipts,
and AST-only refreshed graph. The old replay adapter is separate, already in
the baseline, and must not be reapplied or bundled as a new change.

Run from a source-only local extraction, never from NFS SQLite:

```bash
cd "$LOCAL_SOURCE/backend"
P=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python
PYTHONPATH="$PWD" "$P" "$EVIDENCE/state-only-qualification.py" -q \
  tests/test_sba_classification_query_batches.py
PYTHONPATH="$PWD" "$P" tests/test_tick902_replay_diagnostic.py \
  profile "$LOCAL_SNAPSHOT_DIR" --without-profile
```

`run-serial.sh` records the exact executed bounds/order. For another scratch
root, update the qualification runner's explicit owned-root assertion and local
temporary paths rather than relaxing the SQLite/socket guards. Requalification
is needed after later coupled-source changes; no main push was performed.
