# Offline Corpus Readiness

`backend/scripts/corpus_knowledge_readiness.py` audits explicit SQLite inputs,
prepares source-backed profile patches, and validates them against a disposable
local overlay. It does not import the app, choose a live database implicitly,
change numerical tactical estimates, or apply patches to the live database.
Gameplay rules remain application code, not database operations.

## Commands

From `backend`, inspect available arguments without opening the application DB:

```bash
./.venv/bin/python -m scripts.corpus_knowledge_readiness --help
./.venv/bin/python -m scripts.corpus_knowledge_readiness report \
  --database /local/consistent-card-database-copy.db \
  --out /mnt/rchfiles/codex-storage/mtg-deck-testing-lab/knowledge-corpus/new-report.json
```

`prepare` requires a canonical-card archive with its expected SHA-256 and a local
checkpoint. Optional rulings require a separate archive hash. Preserve official
fetch manifests: a matching hash proves byte identity, not publisher authority.
`fetch-rulings` explicitly downloads official bulk data; it does not issue a
request for every card. `fetch-card` produces a separately pinned current-response
packet when a canonical source record differs; differences are never guessed.

`validate` checks a prepared artifact against its original canonical snapshot and
creates a new local validation database. `campaign` accepts an explicitly pinned
seed artifact/checkpoint and publishes/validates deltas of at most 500 rows.
Standalone `prepare` limits newly examined rows but its artifact is cumulative;
use campaign deltas for bounded delivery. Mechanic materialization requires the
reviewed extractor version and remains separately opt-in. Existing tags, scores
and canonical fields are preserved unless a separately declared, verified refresh
authorizes an owned field change.

## Recovery And Storage

`apply-index` applies a complete digest-pinned artifact index in one transaction
to an explicit independent **offline local copy**. Required arguments are
`--database`, `--target`, `--target-sha256`, `--index`, `--index-sha256` and a new
`--out` report. A separately verified canonical refresh also requires its packet
and hash. Source and target must initially be exact byte copies. There is no
default target, live-write flag or force/rebase override.

The importer rejects live database names, NFS SQLite, symlinks, hardlinks,
sidecars, changed source/target identities and incomplete/duplicate coverage.
It freezes bounded validated artifacts before opening the target transaction,
preserves nonprofile columns and legacy tags, and verifies every resulting row.
If commit succeeds but report publication fails, preserve and audit the target;
do not blindly retry. Installation into the running app is a separate step.

Limits are enforced in code rather than trusted from the index: 256 artifacts,
500 records per artifact, 2 MiB per JSONL line, 64 MiB expanded per artifact,
1 GiB aggregate expansion and 2 GiB local staging. Index, receipt, compressed
artifact, refresh and source-profile reads also have explicit byte limits.
Oversized/truncated/compressed-bomb inputs fail before target mutation.

Source connections are read-only. Active SQLite checkpoints/overlays must be
local, never NFS. Completed archives, immutable receipts and reports belong on
verified RCHFiles storage. Existing outputs, unfinished `.part` files, input/output
collisions and unsafe symlinks fail closed, without replacing user artifacts.

`--resume-campaign` requires identical configuration and committed scratch
ownership. Config-before-seed and commit-before-receipt interruptions can resume;
unowned/incomplete leftover SQLite needs explicit audit. Delivered artifact,
receipt, checkpoint and full-profile hashes are compared before resumed writes.
Missing committed scratch or changed evidence is refused, not silently repaired.
Final validation compares every complete profile, including unchanged/refused
rows, in addition to numeric/tag/core-column preservation.

## Evidence And Limits

Parent importer/recovery qualification passes **100 checks** on the current
combat milestone. A separate isolated application of all 38,690 profiles from
78 pinned artifacts to a parent backup passes integrity checks and preserves all
nine nonknowledge tables, schema, nonprofile columns, tags and 1,264 saved match
records. No live rows were imported. Private preservation evidence is archived
under `knowledge-corpus/fresh-backup-qualification-d519d37/`; deploying that old
full database later would lose newer writes and is not authorized by this test.

The completed offline campaign contains 38,690 unique validated profile patches:
18,609 dated-bulk verified empty ruling lists and 20,081 nonempty lists. The source
bulk is dated 2026-09-27; one differing Cathar record has an independently verified
current response. This does not claim all-card latest-upstream freshness.
Full delivered/checkpoint/profile equality was independently verified for all
38,690 rows. No live rows were imported by this campaign or this CLI increment.

Recovery qualification passes 47 focused checks. Parent composition with dataset,
training, metadata, knowledge and fixed mana passes 245 checks, including
teacher-source hash coverage. Evidence is on RCHFiles under
`knowledge-corpus/all-card-4334e37/` and parent composed qualification directories.
The [mechanic backlog](corpus-mechanic-backlog.md) separates known engine flags,
fact warnings, missing nested metadata and unknown trained competence. Missing
warnings or available canonical facts never certify arbitrary-card execution.
