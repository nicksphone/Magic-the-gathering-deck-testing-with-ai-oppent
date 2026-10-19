# Current Job Crash Recovery

Qualified 2026-10-08 on the immutable final518/Storm source whose runtime
production bytes were published in `7455a9d`. The source manifest contains
4,917 files; all source and 2,772 qualified runtime file hashes were unchanged.
No application repair was needed in this qualification.

## Actual Scenario

The one completed A/B/C scenario exited zero. Three actual ASGI processes used
one isolated local database outside the source tree and the original public
simulation endpoints:

- A completed a control job, admitted the 500-match crash request, and was
  killed with a real owned SIGKILL while its durable job remained unfinished.
- The closed crash artifacts were archived before B started. B's genuine
  pre-reconciliation backup retained the unfinished request and matching escrow.
- B marked that job failed with the restart error, preserved its request and
  any published snapshots, rebuilt the capacity ledger, and cleared reservations.
  Completed/failed idempotent replays were stable; a conflicting request returned
  409 without changing the database. A new control job completed.
- C restarted again and retained the exact job and snapshot rows. Ledger,
  foreign-key, integrity, and replay checks passed.

B and C each recorded process return code `-15` after graceful application
shutdown. Both satisfied the original worker, pool, admission, ownership,
backup, and handle closure checks. The installed Uvicorn re-raises the captured
termination signal after shutdown; accepting that code alone is not sufficient.

Independent checks found all owned supervisor/server/diagnostic PIDs ended,
the listener quiet, and actual database, backups, lock and directory fuser
checks empty. Accessible owned FD/cwd references were absent; unrelated process
visibility limits are recorded rather than claimed away. SQL was released at
2026-10-08T13:16:04Z.

## Evidence And Limits

Verified archive:
`parent-integration/job-sigkill-fullABC-PASS-6PN74D/` under the MTG NFS artifact
root. Manifest SHA256:
`a7279a32d60ae6288bbbf6241c9abda756de1b2392dfb22bd2f8f8b3d95da472`.
Raw requests, rows, backups, signal identities, return codes, terminal and
independent closure receipts are preserved. Closed SQLite copies are evidence,
not databases to execute on NFS.

Earlier attempts stopped on external-database placement, premature SQLite
authorizer installation, or an unrecorded process-exit assertion. Their raw
failure ledgers remain immutable. Corrections changed only the isolated harness;
they did not weaken application checks or modify application source.

This qualifies the declared single-owner job crash/restart component. It does
not establish physical exhaustion, long soak, browser recovery, distributed
workers, arbitrary-card semantics, AI strength, deployment, or a newer product
composition. Python-native instrumentation is not an OS sandbox.
