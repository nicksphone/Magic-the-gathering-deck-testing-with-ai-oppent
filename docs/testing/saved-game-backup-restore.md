# Local SQLite backup and saved-game reconstruction

Use one backend process/worker on a local filesystem. Backups contain decks,
saved games and other local records; keep their directories private. A backup
is a point-in-time copy, not replication. Actions accepted after it are absent
from a restore. Keep the original database until recovery has been checked.

## Operator procedure for an explicitly relocated database

These commands assume the application already uses an absolute, canonical
`MTG_DATABASE_PATH` **outside the checkout**, on a supported local filesystem.
Use the same application revision, built frontend and Python environment for
the drill; the [README quick-start](../../README.md#setup) selects an external DB
from the first launch. Replace
all example paths with your own; do not use a production file for a rehearsal.

1. Stop the launcher/backend normally. Wait for it to exit and for outstanding
   work to drain. Stop any separate import/training/maintenance process too.
   Do not delete the persistent owner `.lock` file or force a second owner.
2. Create private backup and recovery directories. The database filenames and
   their `-wal`, `-shm`, and `-journal` sidecars must not already exist at either
   destination. Do not copy only the main file of a running WAL database.
3. From `backend/`, use the existing SQLite online-backup implementation:

   ```bash
   umask 077
   mkdir -m 700 /absolute/private-backup /absolute/private-recovery
   /absolute/venv/bin/python -m scripts.verify_storage_restore \
     --source /absolute/current/mtg.sqlite3 \
     --backup /absolute/private-backup/checkpoint.sqlite3 \
     --restore /absolute/private-recovery/recovered.sqlite3
   ```

   Require exit 0 and `verified: true`. Preserve the returned schema/table
   fingerprints with the checkpoint. The timeout bounds unfinished copying
   cooperatively; it is not a hard wall-clock deadline. This operation never
   overwrites an existing destination. On failure, retain the source, inspect
   the error and choose a new recovery target; do not delete source sidecars.
4. To rehearse an existing checkpoint separately, omit `--source` and choose
   another absent restore path:

   ```bash
   /absolute/venv/bin/python -m scripts.verify_storage_restore \
     --backup /absolute/private-backup/checkpoint.sqlite3 \
     --restore /absolute/private-recovery/second-recovery.sqlite3
   ```

   Restore-only mode proves SQLite self-consistency, not checkpoint provenance.
   Compare its fingerprints with those recorded when the checkpoint was made.
5. Start the built single-worker table with `MTG_DATABASE_PATH` set to the
   **existing recovered file**. From the repository root:

   ```bash
   MTG_DATABASE_PATH=/absolute/private-recovery/recovered.sqlite3 \
     MTG_LOCAL_PYTHON="$PWD/backend/.venv/bin/python" \
     bash scripts/start-local.sh
   ```

   Keep the original backend stopped. Open **http://127.0.0.1:5173**; no separate
   Vite/backend server is needed. Confirm recovered match IDs, revisions,
   pending choices and legal moves before making new decisions. Reconcile state
   before retrying a lost request; preserve its original idempotency key/body.
   Reusing a key with different intent must conflict, and a new key with a
   stale revision must conflict. An older backup cannot know later receipts.

6. Stop the recovery instance cleanly before archiving it. Archive only closed,
   verified copies to remote/NFS storage; run the application on local storage.

The source-relative default `backend/mtg_lab.db` is deliberately refused by the
standalone maintenance CLI. This runbook does not bypass that restriction or
provide an in-place replacement command. For that deployment, arrange a
reviewed export/relocation first. A running application's registered
`DatabaseOwner.backup(destination)` is the existing in-process backup seam;
there is no public HTTP backup endpoint. A second Python process cannot borrow
its ownership. The offline procedure above needs no new production endpoint.

## Acceptance tests

From `backend/` in a disposable checkout:

```bash
python -m pytest -q tests/test_saved_game_backup_restore.py \
  tests/release_agent/test_restore.py tests/test_storage_backup_deadline.py
```

The new module checks a registered owner's populated backup, schema/row
fingerprints, exclusive destination refusal, and continued owner usability.
Its two seat-balanced ASGI cases save an actual accepted Battle attack and an
actual `/matches/start` receipt, back up, accept a later match, restore into a
clean directory, and start a fresh Python worker against only the restored
file. The worker compares complete saved state/controller rows and public
match responses, replays both original keys without mutation, rejects stale
and conflicting action intents, and confirms the later match is absent. The
original database remains unchanged during recovery.

Capacity-owner epochs/counters can change when startup reconciles ownership;
full database equality is checked before that startup, while saved games and
start receipts remain exact afterwards. Battle fixtures are **declared canonical
midgame**, not natural game histories. TestClient exercises ASGI routes, not
TCP loss or browser refresh. These tests do not establish machine-loss
recovery, backup retention/encryption, a different-version migration, or a
complete RC acceptance run. Test counts belong in the PR/CI results after an
actual run, not in this procedure.


Restoring a snapshot does not migrate missing historical provenance. The
maintainer retains the `legacy_unknown` finisher seam and its two strict xfails
as a documented RC limitation; see [the failure ledger](known-failures.md).
Do not infer a frame's historical ownership from the card's current zone.
