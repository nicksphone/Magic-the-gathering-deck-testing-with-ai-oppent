# Release/storage agent: standalone checkpoint

## Identity and ownership

- Branch: `ops/release-storage`, worktree `/home/nick/mtg-release-storage`.
- Exact base: `26c973449fa25591b6fc99d873512b13d8225e92` (main had advanced before the worktree was created).
- Tested implementation commit: `41c0f81f2359ad13bea2db4bdad7a3e84ddf6067`.
- This handoff is a subsequent documentation-only commit; obtain its ID with
  `git log -1 --format=%H -- docs/testing/release-storage-agent.md`.
- Authoritative instructions read from the original untracked
  `/home/nick/mtg-deck-testing-lab/release-agent-plan.md`; the original checkout
  was not edited. No live database was read, backed up, pruned or replaced.
- Graph report read before source exploration. It records `f35cb4bc`, older
  than this base; no wiki index was present. Shared Graphify files deliberately
  remain untouched for the backend integrator.
- New files only: `backend/persistence/job_retention.py`, the two scripts
  `backend/scripts/{prune_simulation_jobs,verify_storage_restore}.py`,
  `backend/tests/release_agent/{test_retention,test_restore,test_safety,offline_probe}.py`,
  and this document. No existing modules, manifests, frontend or shared docs changed.

## Current behavior reconciled against Gate 3

`main.py` already caps its terminal in-memory history at 20, falls back to SQLite
for older results, persists job requests/results, fails queued/running jobs on
restart, and supports single-process admission/cancellation. The job's ID is also
its durable simulator start idempotency key. These are not missing features.
`SimulationJobRecord` currently has no declared incoming foreign keys or separate
receipt table. Match-start receipts point to active matches, not simulation jobs.
Decks, match history, active snapshots, stats and card data are separate tables.
There is no user-settings table in the inspected persistence models.

**This does not close Gate 3.** Database quotas, automatic cleanup, durable retry
expiry semantics, API cache coordination, multiworker operation, network policy,
backend dependency review, browser soak/accessibility and broad recovery remain
outside this checkpoint.

## Deliverable 1: explicit-path retention

Standalone reusable API: `prune_jobs(database, *, max_age_seconds=None, keep=None,
now=None, apply=False, timeout=5.0, protected_ids=())`.

Run from a disposable backend source tree, on an operator-owned local database:

```sh
python -m scripts.prune_simulation_jobs --database /absolute/local/fixture.db \
  --max-age-seconds 2592000 --keep 100
# Review the JSON candidate IDs first. This deletes only a disposable fixture:
python -m scripts.prune_simulation_jobs --database /absolute/local/fixture.db \
  --max-age-seconds 2592000 --keep 100 --apply
```

There is no default database or retention policy. These numbers are examples,
not an approved live retention policy. At least one rule is required. Age must
be positive/finite, keep a nonnegative integer, and timeout nonnegative/finite.

- Only `completed`, `failed`, and the application's spelling `canceled` qualify.
  Queued/running/cancelling, unknown statuses, invalid/missing/negative/future
  finish timestamps are retained. Started time is never used as an unsafe fallback.
- Valid terminal rows are ordered by `(finished_at DESC, id DESC)`. Keep protects
  the first N of those rows, including linked rows. Invalid rows do not consume N.
- Age is strict: `finished_at < now - max_age_seconds`. The exact boundary stays.
  When both limits are set, **both must permit deletion (AND)**. This favors
  preservation, not a hard row/byte quota. `--keep 0` alone selects all otherwise
  eligible terminal rows; zero age is rejected rather than meaning delete-all.
- Incoming declared foreign keys are inspected and referenced parents protected,
  including CASCADE and SET NULL relationships. SQLite handles equality with
  parent affinity/collation. Unsupported/composite incoming references fail closed.
  `--protect-id` / `protected_ids` supplies additional logical references.
  Future JSON/application links must be explicitly integrated, not assumed found.
- Dry-run uses a read-only connection and read transaction. Apply plans and deletes
  under one `BEGIN IMMEDIATE`; commit failure or any partial-delete error rolls
  back. The write count must match the selected IDs (including collateral FK
  changes). Job-table triggers and existing foreign-key violations are refused.
- JSON includes candidate/deleted IDs and counts, protected reasons, policy and
  evaluation time. Repeat apply is idempotent for an unchanged database/policy.
  Operational failures return JSON on stderr and exit 1; argument syntax exits 2.
- No VACUUM, unrelated table deletion, SQL functions, shell commands or network
  calls are used. Row deletion need not reduce the database file's byte size.
- Absolute canonical paths and recognized local Linux filesystems are required.
  Symlinks, unknown/network mounts and the executing source tree's own
  `backend/mtg_lab.db` are refused. This is not a sandbox against hostile directory
  writers, hard links or a user explicitly naming another installation's live DB.

**Human approval is still required for any live cleanup.** No schedule or service
hook was added. Deleting a job also deletes its durable idempotency history:
reusing that key after cleanup/restart can launch a new job. Until an explicit
expiry/tombstone contract exists, do not present this as safe online API cleanup.

## Deliverable 2: backup/restore verification

```sh
# Create the directory beforehand; it must be empty, local and operator-owned.
python -m scripts.verify_storage_restore --fixture-directory /absolute/local/empty-dir
# Existing isolated source -> new backup -> different new restore:
python -m scripts.verify_storage_restore --source /absolute/local/source.db \
  --backup /absolute/local/backup.db --restore /absolute/local/restored.db
# Restore-only verification of an existing backup:
python -m scripts.verify_storage_restore --backup /absolute/local/backup.db \
  --restore /absolute/local/another-restored.db
```

Both copies use `sqlite3.Connection.backup`, not filesystem copying. The source
is read-only with a stable read transaction. Integrity and foreign-key checks,
schema hashes, row counts and order-stable per-table content hashes are compared;
the closed destination is reopened and checked. Destination files are reserved
with O_EXCL and mode 0600, never overwritten. Existing sidecars also cause refusal.
All file paths are preflighted before the two-stage operation starts. A failed
individual copy removes its own output; a completed backup is retained if the
subsequent restore fails. Abrupt process/power interruption can leave an incomplete
reserved destination; inspect/remove it manually, never blindly overwrite it.

The timeout bounds busy waits and each backup transfer, not total integrity/hash
scan time for arbitrarily large databases. There is no live file-swap operation.
Unknown virtual-table recovery is refused. Restore-only verifies self-consistency,
not whether the backup belongs to the intended source or is semantically current.

The generated fixture uses current SQLModel schemas and the actual match snapshot
serializer, storing a real seeded Island-deck state plus controller revision 7,
root seed 8128, action receipt, match-start receipt, saved deck, simulator request/
result, match-history and stats rows. Tests load the restored database through
`Repository` and actual `main._restore_active_matches`, then compare the complete
state/controller snapshots. WAL committed records are separately verified.
No claim is made that every historical snapshot version, card-cache/knowledge row,
external image file, user preference, interrupted game or deployment is recovered.
Schema/row equality covers stored tables, not external files or gameplay fidelity.

## Deliverable 3: clean-source release evidence

Scratch root for this run was
`/home/nick/.hermes/cache/scratch/release-storage-hy2kzkpx`.
All API imports/lifespans and test databases ran in disposable `source/` or
`cold/` copies made with `git archive`, never in either active checkout. Final
owned files were overlaid into `cold/`; byte equality with the implementation
commit was independently checked before committing. Initial cold DB was absent
and its image cache empty. The offline probe blocked socket connections before
application imports and failed if any connection was attempted.

| Executed check | Observed result |
| --- | --- |
| Base backend smoke, snapshot, recovery, job cache/admission | 37 passed |
| Final backend selection below, including new tests | 128 passed, 145 deprecation warnings |
| New release-agent cases within that selection | 43 passed, none skipped/xfail |
| Cold offline probe | 119 shipped-name hydrations and 119 served SVG fallbacks, zero network attempts; seeded match receipt/recovery passed |
| Fixture backup -> restore and restore-only CLIs | exit 0; integrity and all table hashes matched |
| Retention CLI dry/apply/repeat on restored disposable fixture | dry candidate `fixture-job`, no deletion; apply deleted it; repeat deleted none |
| Fresh `npm ci` (new node_modules and run-local npm cache) | exit 0; 164 packages installed |
| Frontend `npm run build`, `npm test`, `npm run lint` | all exit 0 |
| Python dependency consistency, `pip check` | exit 0 |
| `npm audit --json` | exit 1: 7 flagged packages (4 high, 2 moderate, 1 low) |
| `npm audit --omit=dev --json` | exit 0, no reported production-dependency advisories |

Versions: Python 3.12.3, SQLite 3.45.1, Node v26.7.0, npm 11.19.0,
Vite 5.4.21. `pip-freeze.txt` and `npm-tree.json` retain resolved dependencies.
The successful Python environment was newly created using `/usr/bin/python3 -m
venv`, then `pip install --no-cache-dir --only-binary=:all: -r requirements.txt`.
No dependency directory was borrowed from an existing application environment.

Failures were preserved, not hidden:

- Initial default `python3` was 3.14.7. Fresh installation failed building pinned
  `pydantic-core==2.23.4`: its PyO3 supports at most Python 3.13. A separate fresh
  Python 3.12 environment installed successfully; no manifests were changed.
  The initial build helper attempted Rust bootstrapping in its per-user
  `~/.cache/puccinialin` cache despite pip's scratch venv/no-cache option; this is
  an installer side effect outside the run directory, not a reused application
  dependency directory. It was not deleted because other agents may use it.
- Expected initial red tests failed collection before the new modules existed.
- First retention run exposed a real failure: a defensive SQLite authorizer
  rejected even a compiled potential CASCADE on an unreferenced row. The test
  stayed intact. Protection now uses incoming-link queries and a collateral-write
  count assertion before commit; CASCADE/SET NULL/RESTRICT cases pass.
- Deprecation warnings concern existing AnyIO and `datetime.utcnow` usage.
- npm's advisory report flags Vite/esbuild and build-tool transitives including
  Babel, PostCSS, Browserslist, baseline-browser-mapping and nanoid. These are
  dev dependencies in this manifest, not proof of shipped React bundle exploitability.
  Dev servers/building untrusted inputs remain relevant exposure paths. npm proposes
  a semver-major Vite update for some findings. No forced upgrade was performed;
  integrators must review supported Node/plugin versions and rerun frontend/proxy
  gates before a deliberate upgrade. Python runtime advisories were not audited.

Exact backend command, run from the disposable `cold/backend` directory:

```sh
../../venv312/bin/python -m pytest tests/release_agent \
  tests/test_api_smoke.py tests/test_match_persistence.py tests/test_match_recovery.py \
  tests/test_simulation_job_cache.py tests/test_simulation_admission.py \
  tests/test_offline_match_hydration.py tests/test_fallback_hydration.py \
  tests/test_placeholders.py tests/test_database_path.py tests/test_session_lifecycle.py \
  -q --basetemp=/home/nick/.hermes/cache/scratch/release-storage-hy2kzkpx/pytest-verified \
  --junitxml=../../evidence/backend-verified.xml
```

`evidence/reproduce.sh` assembles exercised commands into a new-scratch reproduction
recipe (shell-syntax checked; not claimed as a separately executed second run).
It pins both source commits but still resolves the manifests' transitive ranges.

## Evidence, archive and integration

Durable archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/release-storage-agent/release-storage-hy2kzkpx/`

Contains baseline/final test logs and JUnit, initial failures, install logs,
versions/resolved dependencies, frontend logs/audits, cold-probe output,
CLI JSON, closed fixture/backup/restored databases, owned-source snapshot and
this handoff. `manifest.json` lists SHA-256 and sizes. Archival requires `findmnt`
confirming NFS plus a successful write/read/delete probe; each copied file is
hash-verified before disposable local sources/dependencies are removed.
The archived databases are evidence, **not databases to open on NFS**. Copy them
to new local scratch before inspecting/restoring. No live user records were archived.

Proposed integration, **not implemented**:

1. Backend owner reviews/cherry-picks these owned commits and reruns combined gates.
2. Decide retention expiry and retry semantics (tombstones or explicit expired-key
   responses), then coordinate maintenance with `SIM_JOBS_LOCK`, cache eviction,
   workers and admission. Pass any newly introduced logical/JSON links as protected
   IDs or extend explicit link handling. Do not just call the CLI from a request.
3. Approve deployment-specific age/keep/disk quotas, an operator-controlled local
   path, backup storage permissions and restore rehearsal. Automatic quotas, VACUUM,
   scheduled jobs, live replacement, service restarts and publishing require their
   own review/approval. This agent performed none of them.
4. Backend integrator updates shared plan/Graphify after integration. No network
   security, multiworker consistency, clean-machine portability beyond these
   versions, full backend suite, browser soak or overall project completion is
   certified by this storage checkpoint.

## Coordinator independent verification

### Main integration verification

The parent reviewed the final owned-file diff through `e587379` and overlaid
only those eight files onto its repaired frozen backend in disposable local
copies. The exact focused selection below passed again: 128 tests, 222 existing
warnings. A separate cold copy, with absent SQLite database and empty image
cache, passed the module offline probe: 119 names hydrated, 119 fallback assets
served, no network attempts, seeded snapshot restored. An initial copy retained
image-cache files and was correctly refused by the cold probe; that failed
attempt is retained, not counted as acceptance.

Evidence is verified on NFS in
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/rules-regression-repairs/20261004T213559Z/release-and-latency-evidence.tgz`.
The archive was compared against local source and its SHA-256 read back. Main
integration does not enable any live maintenance, change release policies, or
claim the combined whole-project release gates are complete.

The coordinator reviewed all three implementation modules and the failure-path
and restoration tests at documentation commit `c4c833684199b8296d669e19341d410c725411f1`.
Only the eight owned new files differ from base, and `git diff --check` passed.
A separate `git archive HEAD` source copy and fresh Python 3.12 virtual environment
were created under local scratch `release-storage-coordinator-z022xe8u`; declared
requirements installed with `--no-cache-dir --only-binary=:all:` and `pip check`
passed. No API import/test ran in the worktree or original checkout.

Independent results:

- The exact 128-test backend selection documented above passed: 128 passed,
  223 existing deprecation warnings, no skipped/xfail cases.
- A separately extracted cold source passed
  `python -m tests.release_agent.offline_probe`: 119 hydrated names, 119 served
  fallback assets, zero network attempts, restored seeded snapshot.
- Fresh isolated `npm ci`, `npm run build`, `npm test`, and `npm run lint` passed.
  Installation again reported seven advisories; no forced upgrade was attempted.
- `python -m compileall -q persistence/job_retention.py
  scripts/prune_simulation_jobs.py scripts/verify_storage_restore.py
  tests/release_agent` passed in the disposable backend.
- All 36 files in the worker archive manifest matched their recorded sizes and
  SHA-256 hashes when independently read back. Archived databases were hashed as
  closed files only, never opened with SQLite on NFS.

Failed coordinator attempts are explicitly retained: running the offline probe
after API tests refused the already-created disposable database, as designed;
executing its file path directly in a fresh copy lacked the backend module search
path. The successful invocation above uses module execution on a genuinely cold
copy. A full `pytest tests -q` attempt exceeded the tool's 420-second execution
limit without a returned result; it is not claimed as a completed or passing full
suite. Process inspection afterward found no remaining coordinator test process.
The required focused storage/smoke selection did complete successfully.

Coordinator logs, JUnit, command manifests and review notes are archived separately
under the same diagnostics parent at `release-storage-coordinator-z022xe8u/`.
This documentation update makes no implementation change and does not approve
live pruning, merge to main, deployment, or project-wide release completion.
