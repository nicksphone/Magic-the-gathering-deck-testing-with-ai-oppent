# Release and Storage Operations Agent Handoff

Help MTG Deck Testing Lab finish its operational release gates in parallel with
the AI/backend, UI, and rules-regression agents. Implement and test an independent
storage-operations chunk; do not redesign gameplay or duplicate the rules audit.

## Isolate Your Work

Read applicable AGENTS.md instructions and `graphify-out/GRAPH_REPORT.md` before
exploring source. Use any existing graph wiki for navigation and verify findings
against current code. Inspect `plan.md` Gate 3 first: some admission, cancellation,
restart and offline-asset work is already implemented. Do not report it missing
merely because an old audit says so.

Create a separate branch/worktree from committed main:

```sh
git -C /home/nick/mtg-deck-testing-lab worktree add -b ops/release-storage /home/nick/mtg-release-storage main
```

If it already exists, inspect rather than overwrite. Record the base revision.
Do not modify the original checkout, reset another agent's changes, merge main,
or push directly to main.

## Exclusive File Ownership

Add your implementation under these new paths:

- `backend/persistence/job_retention.py`
- `backend/scripts/prune_simulation_jobs.py`
- `backend/scripts/verify_storage_restore.py`
- `backend/tests/release_agent/`
- `docs/testing/release-storage-agent.md`

Do not edit existing engine/effect/AI/API modules, repositories/models, frontend,
dependencies, CI, root README/CHANGELOG/plan, or shared Graphify artifacts. Reuse
existing schemas and interfaces. If a production hook or schema change is needed,
report the integration patch separately for the backend agent to apply.

## Connected Deliverables

### 1. Safe Simulator Job Retention

Current work already caps in-memory terminal history, uses SQLite for old results,
and marks unfinished jobs failed after restart. Database retention/quotas remain
unfinished. Confirm current behavior before implementing storage cleanup.

Add a reusable retention helper and CLI for terminal simulator-job records:

- Explicit database path; no implicit operation on the live source-relative DB.
- Dry-run by default; deletion requires explicit `--apply`.
- Configurable age and keep-most-recent limits with clearly documented composition.
- Preserve queued/running/cancelling jobs and records required by existing links.
- Do not delete decks, card cache, active matches, snapshots, user settings, match
  history, or unrelated tables. Inspect relationships rather than assuming them.
- Transactional deletion, structured counts/IDs in dry-run output, idempotency,
  and clear failure/rollback behavior.
- Reject unsafe/inconsistent configuration. No network access, subprocess shell
  interpolation, credentials, or gameplay SQL functions/triggers.

Run apply-mode tests only against disposable databases you created. Never prune
the user's database. Live cleanup requires a separate review and approval.

### 2. Backup and Restore Verification

Add a verifier using SQLite's supported consistent backup mechanism, not a raw
copy of a running database. Back up an isolated fixture database to local scratch,
restore to a different local path, and check the supported invariants:

- Integrity/foreign-key checks as applicable.
- Saved decks, active-match/controller snapshots, seed/revision/idempotency
  metadata and simulator-job records survive.
- Corrupt/missing backup and failed-write cases return meaningful nonzero errors.
- No overwrite of an existing destination by default. Never replace the live DB.

Do not execute SQLite databases on NFS. Only closed completed backup artifacts
may be archived there after verification. Use current persistence schemas; report
an unverified recovery surface rather than fabricating successful restoration.

### 3. Clean-Checkout Release Evidence

In a disposable copy with empty DB/cache and declared dependencies, verify offline
fallback assets, relevant backend smoke/storage tests, and frontend build/test/lint
scripts where practical. A reused dependency directory is not a fresh-install test:
label it accurately. Install dependencies only in your isolated scratch, never
alter the active checkout's environment or another agent's dependencies.

Capture reproducible commands, versions, source revision and pass/fail results.
Investigate current dependency advisories if useful, distinguishing development
tools from shipped runtime reachability. Do not run force upgrades or change
manifests; hand off any justified upgrade separately.

## Validation and Safety

Test retention ordering, age boundaries, keep limits, active-record preservation,
empty runs, repeat runs, linked-record protection, transaction rollback and lock/
storage failures. Test backup/restore with real persisted records, not only mocked
success. Keep meaningful failures intact and report them; do not skip or weaken
assertions to make a green summary.

Backend database paths are source-relative, so changing cwd does not isolate them.
Run API lifespans/tests only from a disposable source copy with its own local DB.
Do not read/write live user records. Do not stop/restart existing services. Avoid
servers unless needed; inspect ownership and choose an unused dedicated loopback
port, not other agents' ports.

Keep running scratch and databases local. For completed backups/logs/evidence,
verify NFS is mounted and writable, then archive in a unique run directory under:

`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/release-storage-agent/`

Verify copies/checksums before deleting your completed scratch. Preserve
uncommitted work explicitly; GitHub cannot restore user databases or local files.

## Handoff

Commit only your owned new files on `ops/release-storage`; do not merge main.
In `docs/testing/release-storage-agent.md`, provide branch/base/commit IDs, files
changed, exact commands/results, evidence locations, destructive-operation safety
boundaries, and proposed integration points. Clearly identify what is standalone,
what requires an API hook, and what still needs human approval or verification.

The backend agent will review, integrate, run combined gates, update shared
documentation/Graphify, and publish. Do not claim network security, multiworker
consistency, or overall project completion from this storage milestone.
