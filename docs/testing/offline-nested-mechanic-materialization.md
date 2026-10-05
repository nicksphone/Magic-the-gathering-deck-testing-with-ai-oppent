# Offline Nested Mechanic Materialization

This is a **nested-metadata-only** transformation of a verified local canonical
knowledge snapshot. It does not acquire card facts, rewrite ruling evidence,
refresh tags, train an agent, or certify engine support. Schema version `1` and
extractor `canonical-tactical-surface-v1` are explicit pins; code hashes and
current canonical `card_data` input hashes must also be recorded.

## Existing CLI and Preservation Boundary

The reviewed corpus CLI offers `prepare`/`campaign` with
`--materialize-mechanics-version canonical-tactical-surface-v1 --limit 500`.
Do not supply `--refresh-tags-sha256`. However, `prepare` also assigns new
`card_data_provenance`/`card_data_sha256` from its supplied card archive, even
without tag/ruling refresh. It can refuse the already-correct current Cathar
record against a historical bulk. Thus invoking it unchanged is **not** a
strict provenance-preserving nested-only operation. The archived materialization
job left this preparation path unchanged; this boundary remains explicit.

The general importer allows source/ruling provenance changes by design. For a
declared current mechanics manifest, import now validates the input/version pin
and recomputes the complete current extractor output, rejecting altered coverage,
evidence or quality fields even if the payload hashes were updated. Historical
version-only validation accepted such changes; focused regressions close that
boundary. `current_input_version_not_semantics` still does not certify gameplay
semantics, and undeclared metadata modifications remain non-owned changes.

## Archived Runner Contract

A reproducible evidence runner can use the existing extractor, canonical
hashing, artifact publisher, binary bounded reader and `validate_profile_patch`
without replacing published code. Starting from the exact verified snapshot:

- Generate **only** `mechanic_metadata` from the row's existing canonical raw
  payload. Compare every other profile key for exact presence/value equality.
- Keep all raw data, facts, ruling content/status/provenance, legacy tags and
  versions, numerical fields, unrelated annotations and nonprofile columns.
- Use a common card-source manifest predicate actually present in every
  retained source packet (`source: scryfall`), plus a complete retained source
  provenance ledger and per-row original record hash. This is not a new bulk
  acquisition claim; full original provenance remains in every profile and the
  source snapshot/ledger hashes anchor it. Do not discard Cathar's verified
  current response or pretend it was taken from the historical bulk.
- Publish at most 500 rows/artifact and immutable digest-pinned receipts. Read
  compressed artifacts through existing fixed compressed/index/receipt limits,
  binary `readline(max+1)`, decompressed byte counters and indexed-row bounds.
- Recompute exact extractor content when validating generation; mere matching
  version/input hashes are insufficient. Compare complete before/after row
  hashes, not just legacy tags or a generic readiness summary.
- Keep all source, validation, application and checkpoint SQLite local. Source
  opens are `mode=ro`/`query_only`; writes are only to independent explicit
  offline targets. Reject existing/foreign paths; never open NFS SQLite.
- Reuse the reviewed full-transaction `apply-index` on a second independent
  local byte copy, using the new manifest/index pins and complete row
  preconditions. No card refresh is needed: current raw data never changes.
- Independently verify all nonknowledge rows/schema, every nonprofile column,
  every profile field except the new nested metadata, and all computed metadata
  against the exact pinned extractor. Verify cold archive decompression/hash
  before cleaning disposable local scratch; retain source/index/code/receipts.

Job-specific invocation, input/code/output hashes, counts and interrupted-state
handling belong in the immutable campaign evidence. A successful receipt is
not deployment approval, and a full archived target is not a safe ongoing live
DB replacement. Restore locally from the approved source archive, verify its
hash, then reproduce via the pinned delta index on an independent byte copy.

## Meaning of the Result

Parent qualification against `e4d8aa8` passes 132 composed checks and a full
38,690-row/78-artifact offline application with exact extractor recomputation.
Independent comparison preserves schema, every nonmetadata profile field,
all nonprofile columns, all nine other tables and 1,264 saved snapshots.
Evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/nested-materialization-e4d8aa8/`.
The qualified offline target is not the live database.

Missing nested metadata can become current-input/version metadata on every
row. Semantic gaps do **not** thereby shrink. Coverage families still have
`execution_support: unknown`; evidence has `semantics: not_evaluated`;
`unsupported_semantics` remains explicit, and learned quality is `not_assessed`.
Empty/malformed/missing card surfaces remain extractor `unknown` records. Do
not replace unknowns with numerical zero scores or claim all-card trained
competence. Existing classifier gap counts concern engine code, not extraction.

```sh
cd backend
.venv/bin/python -m pytest --noconftest -q tests/test_nested_mechanic_materialization.py
```
