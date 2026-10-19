# Exporter Publication Recovery

The existing seed + external fact-ledger CLI retains its full155/prior17
metadata contract. It now journals publication in the output seed's directory,
not a per-process scratch directory. This is recoverable publication, NOT an
atomic two-file visibility guarantee. Local Linux process-crash checks do not
certify power-loss/storage/NFS durability or hostile/uncooperative writers.

Normal export refuses a pending journal before reading preservation inputs or
opening SQLite. Resolve it explicitly using the SAME ordered destinations:

```sh
python scripts/export_builtin_oracle_seed.py \
  --output /absolute/seed.json --fact-ledger /absolute/facts.json \
  --recover-publication
```

Recovery runs before export_seed and does not need the original database, bulk,
semantic admission, preservation seed or prior ledger. Protected-input path/
hardlink alias checks still apply; these inspect file identity, not input data.
Without a journal it reports a no-op, not certification of arbitrary outputs.

A private 0600 exclusive/flock journal contains exact old opaque bytes, presence,
modes, new signatures and transaction-owned staging/restore paths. Prepared data
is fsynced before the first replace. The inode is stable; a checksummed commit
record is appended only after both replacements and directory syncs. A valid
complete commit selects the new generation; an absent/recognized-prefix torn
commit selects originals. Incomplete prepared, foreign/corrupt records, changed
outputs/stages, symlinks or an active owner refuse before recovery writes.

All endpoints/artifacts are preflighted before any recovery mutation. Original
restores are staged before changing destinations. Originally absent files are
removed only when they match the recorded transaction generation. Interrupted
rollback retains snapshots; explicit restart can resume from recognized states.
No directory glob cleanup, PID-age heuristic, silent regeneration or arbitrary
user-output deletion is permitted. Unknown user files remain untouched.

Journal snapshots are the temporary USER-OUTPUT BACKUP store, independent of
Git and canonical metadata inputs. They survive pending recovery and publication.
Verified successful cleanup removes them: no long-term prior-version retention
is promised. Failure/refusal retains evidence; do not delete it manually and
claim automatic recovery. Original bytes/presence/mode are preserved; inode,
mtime, ownership and xattrs are not promised. Keep exclusive/cooperating ownership
of both endpoints; overlapping pairs and hostile path races are outside scope.

The immutable old four real-CLI immediate-pair RED witnesses remain historical.
New restart tests qualify a different guarantee and do not weaken those tests.
The new file suite uses genuine frozen full155/17 payloads plus explicitly opaque
prior user files. Fault processes call the actual writer and SIGKILL themselves;
fresh recovery processes use missing metadata/SQLite input paths. The SQL suite
calls actual exporter.main in separate bounded subprocesses, never replaces
admission or metadata analysis, and denies network transport in export workers.

## Gate Commands

Shared read-only interpreter, from backend:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_export_publication_recovery.py
```

The ten-case/sixteen-process real CLI suite is deliberately guarded. It MUST
wait for an explicit parent-released shared SQL slot. It re-prepares ONE owned
SQLite path between serial cases and verifies exact DB bytes, SQL dumps and
all metadata input hashes unchanged through each invocation. Recovery invocations
use absent metadata paths; no SQLite is created there.

```sh
MTG_EXPORT_RECOVERY_SQL_SLOT=parent-approved \
MTG_EXPORT_RECOVERY_EVIDENCE_ROOT=/tmp/mtg-export-recovery-CLI-UNIQUE \
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_export_publication_recovery_cli.py
```

Dependency: already-qualified unchanged tests/full155_export_fixtures.py and
its exact canonical fixtures/prior17 ledger from the earlier 4d611c test package.
The new tests do NOT import the historical RED audit modules. Do not ship those
historical diagnostic tests as a known-red default release gate.
