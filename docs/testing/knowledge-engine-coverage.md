# Offline Knowledge-to-Engine Coverage

`backend/scripts/knowledge_engine_coverage.py` reads an explicitly supplied,
digest-pinned **local offline SQLite copy** in `mode=ro`, `query_only`, one
transaction. No app lifespan, network, inference calls, import, tag updates,
numeric tactical scores, or database writes. Never open SQLite on NFS: verify
the approved archive and decompressed hash, then copy/extract locally first.

```sh
backend/.venv/bin/python backend/scripts/knowledge_engine_coverage.py \
  --database /local/scratch/qualified-copy.sqlite3 \
  --database-sha256 APPROVED_DECOMPRESSED_SHA256 \
  --examples 3 --out /local/scratch/new-coverage.json
```

The JSON is deterministic for identical database bytes and classifier source.
No wall-clock timestamps or machine-local DB paths enter it. Existing output,
its `.part`, symlinks, NFS SQLite, active/recovery sidecars, hardlinks and the
live filename `mtg_lab.db` are refused. Publication reuses the existing atomic
no-clobber readiness writer. Archive only completed reports/evidence to project
NFS and verify copies before cleaning successful disposable scratch.

## Meaning

- **Unsupported:** exact labels returned by
  `rules_engine.coverage.known_unsupported_mechanics`, including its existing
  combat/static diagnostics and delegated parsers. Counts are distinct cards
  per label, not mutually exclusive. Some labels conservatively remain despite
  narrow handlers; this report does not run effect tests or invent overrides.
- **Supported:** `cards: null`, not zero. This classifier has no affirmative
  certification interface. Empty gap lists must not become supported cards.
- **Unknown:** detected families from the existing `MechanicMetadata` surface
  extractor; its schema explicitly says execution support unknown. Extraction
  is transient, per card, not stored or fully duplicated in the report. It does
  not interpret condition truth or fabricate game state. These broad surface
  families are not a one-to-one mapping to classifier gap labels.
- **Metadata:** card types and fact completeness, stored nested metadata
  missing/stale/current-input-version, empty/malformed text, and invalid
  identities are separate. A current extractor version is not semantic
  certification. Empty oracle text and non-detection do not prove vanilla.
- **Competence:** `trained_competence: unknown`, `rules_support_certified: false`.
  Fetched card facts and verified rulings are not trained execution ability.

Representatives are bounded, selected by ascending knowledge row ID, and carry
stored name, printing/Oracle IDs, canonical-identity consistency and raw payload
hash. Source ledgers retain archive/source digests; engine modules and extractor
sources are hashed so future classifier changes do not silently share evidence.
Hashes establish identity and consistency, not independent publisher authenticity
or freshness. This report does not replace canonical deck-admission rules.

## Bounds and Checks

Parent qualification on `6905667` plus this sidecar passes **49 tests** across
the report, rules coverage and mechanic-metadata modules. An independently
executed read-only report over the verified local 38,690-profile copy is
byte-identical to the worker's qualified output. It reports 3,369 cards across
61 known-gap labels, 34 detected surface families with unknown semantics,
13 fact-metadata gaps and 38,690 missing nested metadata records. The 35,321
cards without a known gap are **not** certified supported cards. These counts
describe this pinned corpus/classifier, not all-card latest-upstream freshness.

Private parent evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/preflight-and-coverage-6905667/`.
No source database or live application knowledge row was modified.

Database 2 GiB; rows 100,000; profile 2 MiB. SQL checks row count and maximum
profile **byte** length before reading any payload. Each parsed string surface
field is capped at 16 KiB, faces at 32, declared keyword/type lists at 256 items
and 256 bytes/item. Families per status and provenance ledger entries are capped
at 256. Representatives default three, maximum ten; no unbounded per-card report
or full nested JSON. Over-limit inputs abort, never truncate silently. Reports
separate malformed/missing profiles from cards classified without known gaps.

```sh
cd backend
.venv/bin/python -m pytest --noconftest -q tests/test_knowledge_engine_coverage.py
```

Tests use isolated synthetic parser fixtures, not claimed canonical card data.
They cover deterministic/empty output, real classifier root/face detection,
unknown/no-positive fallback, stale/malformed metadata, bounded representatives,
pre-read byte/count rejection, surface/face limits, read-only source preservation,
digest refusal, output collisions, symlinks and NFS guards. Full-corpus evidence
must identify exact source/after snapshot and executed source hashes separately;
this documentation itself is not a successful-run receipt.
