# Task 3.3 Native Training Adapter Prototype

This additive private exporter follows the immutable final93 sidecar. It does
not modify the historical-bias method, aggregate calculations, legacy JSONL
readers, context admission/deduplication, or the stored priors artifact.

## Intake Contract

Only a completed, caller-authorized matrix envelope may be supplied. Do not
point this CLI at an active producer directory. The adapter reads no database,
does not import the native game runner, and never classifies cards or decks.

The caller supplies full expected source-base/backend hashes, the SHA256 of
the exact original execution-contract bytes, and the SHA256 of a retained
sealed-file inventory. These expectations must come from the parent's actual
terminal evidence, not be calculated from arbitrary inputs to make them pass.
The inventory transport is an explicit adapter protocol:

```json
{"schema_version":1,"files":{"relative/actual-file.json":"full-lowercase-sha256"}}
```

This inventory is not a fabricated writer receipt or a source of native
execution authority. It must retain actual completed artifact hashes. The
summary's four-field writer receipt lacks a whole-capsule hash; the external
seal is required in addition to that authentic receipt, never as its substitute.

Required source-backed envelope members are `parent-outcome.json`,
`runtime/outcome.json`, `runtime/matrix-summary.json`, and
`runtime/prepared-boards.json`. Header schema 2 binds source, harness, runtime,
fixtures, limits, package origin and prior parity receipt. Parent and child
closures, source-before/after hashes and manifest/export hashes must agree.
Only the complete 110-series/55-pair, two-seat, single-explicit-token schedule
with available six-metric per-player decision quality is admitted. Partial,
stopped, source-changed, missing-receipt and unsealed inputs remain unavailable.

The supported layout is pinned to producer SHA256
`9061cc3b92c136a6d44bd3bb9b3ecef3297dde125f04e18ccb36e49cabb0775b`.
Summary `series[k]` maps to actual `runtime/games/series-{k:05d}`; each retained
receipt must name its actual `game-{ordinal:02d}.json` member. The raw bytes are
`json.dumps(raw_log, ensure_ascii=True, separators=(',', ':'), allow_nan=False)`
encoded UTF-8. Receipt byte count/raw hash, capsule raw hash, sealed whole file
hash and summary/result fields are checked. Extra files, duplicate references,
symlinks and path traversal are rejected. No missing seed is derived from a
series, filename or ordinal.

## Private CLI

```bash
python -m scripts.build_ai_log_priors \
  --native-root /explicit/completed-envelope \
  --native-contract /explicit/original-contract.json \
  --native-inventory /explicit/retained-sealed-files.json \
  --expected-source-base FULL40HEX \
  --expected-backend-sha256 FULL64HEX \
  --expected-contract-sha256 FULL64HEX \
  --expected-inventory-sha256 FULL64HEX \
  --export-training-root /exclusive/owned/private-training
```

Incomplete or mixed native/legacy options return an unavailable JSON status
without SQL or game-file intake. Successful intake creates a new private root
(0700), preserved actual series directories (0700), and `games.jsonl` files
(0600). Rows contain the actual capsule basename, unchanged raw-log strings and
the capsule seed or null. Inputs and export metadata are never mutated. A write
failure removes only the newly created disposable export, not existing paths.

This command does not save priors. Its sanitized status contains counts, not
raw logs, card/deck/player names or private filenames. The unchanged
`--training-root` reader can subsequently consume this private export only in
an owned source stage. Directory/basename and supplied trace `action_index`
form the existing provenance key. Missing indices or contexts stay unavailable;
the adapter never constructs them from order, roster labels or hidden cards.
Original aggregate/role counts and context >=3 casts in >=2 known archetypes
requirements remain unchanged.

## Evidence Limits

All new fixtures are synthetic native-format protocol packets, NOT games,
execution receipts, canonical card admission, or learned timing data. They test
the actual adapter and existing reader functions under pre-collection denial of
SQL, sockets, providers and child processes. The previously authorized parity
reference capsule informed schema only; it lacks retained receipt/index/context
proof and was not used for training. No active full-matrix file was read.

Actual input qualification awaits the parent's terminal matrix evidence and
independently retained seals for its exact source epoch. A successful format
test or private export is not completion of Task 3.3; a genuine qualified
context-data rebuild and final composed-source gates are still required.
