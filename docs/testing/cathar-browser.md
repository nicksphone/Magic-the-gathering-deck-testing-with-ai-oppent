# Canonical Cathar Browser Gate

Run from a normal Git checkout. This standalone gate does not use or modify
`ui_v2_fixture_server.py` or `run-browser-ci.sh`, and does not mutate that checkout's
backend, database, card data, App or ordinary game controls.

```bash
MTG_TEST_PYTHON=/absolute/path/to/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/absolute/path/to/frontend/node_modules \
node frontend/tests/browser-cathar.mjs
```

The dependency variables are optional when those dependencies already exist in
the checkout. Requirements: Node with global WebSocket, Python backend dependencies
and pytest (canonical fixture helpers), installed frontend dependencies, Chromium
or Chrome, Git, tar, gzip, and a mounted writable RCHFiles NFS share. No package
installation or network card lookup is performed by the gate.

`MTG_CHROMIUM` can select an installed browser. Only use
`MTG_BROWSER_NO_SANDBOX=1` when the environment requires it; sandboxing remains the
default. `MTG_CATHAR_ARCHIVE` can select another directory on mounted NFS, never a
local fallback. Hosted GitHub Actions is the sole exception: an explicit archive
directory must resolve inside `RUNNER_TEMP`; the shared harness declares
`$RUNNER_TEMP/mtg-cathar-evidence`. Local runs fail closed without NFS even when
an explicit local archive path is provided. Browser card artwork may use the normal App's remote image URLs;
artwork availability is not a rules acceptance claim.

## Isolation

The runner copies tracked and non-ignored working backend/frontend source into
a new local temporary directory. It excludes databases, dependency trees and
runtime caches, reuses external dependencies, gives Vite a disposable cache,
and creates a fresh source-local SQLite database. No live database is borrowed.
Three separate ephemeral ports bind to `127.0.0.1`: real FastAPI, Vite serving the
unmodified App, and Chromium CDP. Owned PIDs and ports are printed immediately.
The runtime dependency directory contains individual package symlinks, not a
symlink to the external dependency root: Vite config caches stay local too.
Source symlinks are rejected before any service starts, and the Git inventory
must match the source root. SQLite scratch must be local storage.

`cathar_fixture_server.py` refuses direct import in a normal checkout before
importing `main`. It requires a runner-created ownership marker, matching source
root and token, source-local `main`, and loopback fixture requests. The fixture
routes are separate from normal game routes. Only the runner's process groups
are terminated or restarted; shared browser CI ports/processes are not touched.

The gate reuses `browser-driver.mjs`. Casting, choosing a trigger target, selecting
Unsummon's target, and passing priority are React App controls that send real
HTTP `/matches/{id}/action` requests. A passive fixture-server observer records
their payloads/statuses. The runner never posts game actions directly, intercepts
or replaces browser responses, invokes React internals, or adds missing controls.
A missing/disabled target/cast/pass control is a failed gate, not an API shortcut.
App restoration's existing automatic-play pause remains unchanged.

## Canonical Coverage

Both human seats run each of these cases:

- **Day entry and ledger:** cast Brutal Cathar; choose the second opposing
  Recruitment Officer through the real trigger-target buttons; resolve exile;
  restore snapshot and reload; perform an explicitly labelled night transition;
  verify the same incarnation and ledger; cast canonical Unsummon through the App
  to leave the battlefield and return the linked creature.
- **Night entry and pending transform exile:** cast into night; visibly verify
  Moonrage Brute 3/3 and no front-face target ability; controlled day transition
  creates a real front-face trigger; choose through the App; controlled night
  transformation retains the pending trigger/source incarnation; resolve it;
  verify linked exile and source-departure return.
- **Pending source blink:** day entry and human target choice; a controlled
  shared-rules exile/linked-return fixture at night creates a new Moonrage Brute
  incarnation; resolving the old targeted trigger through App passes must not
  exile the target or leave a ledger entry.

Visible battlefield names and printed 2/2 or 3/3 stats are asserted, as well as
authoritative zones, payload target IDs, source timestamps and ledger contents.
Night entry absence is checked in the App, legal moves, and stack/choice state.

SQLite snapshot restoration evicts the in-memory controller and reloads through
the normal repository restoration path; complete snapshot hashes must match.
Browser reloads recover choices and ledgers. Two real backend process restarts
cover P1 day-entry target choice and P2 transformed pending exile before resolution,
with changed PIDs and identical snapshot hashes, followed by actual App actions.

Entry/board/designation/blink arrangements are **explicit controlled fixtures**,
not claims that a natural game sequence or historical repair occurred. Canonical
card facts are never edited. A timing fixture is not an invented blink card.

## Provenance And Evidence

Cathar, Recruitment Officer and Plains reuse `cathar_day_night.json`, canonical
Scryfall face records in `cathar_canonical/`, and their SHA-256 provenance manifest.
The existing facts-versus-records canonical test runs when the guarded fixture
server starts. Unsummon is the unmodified pinned canonical record from
`defensive_responses.json`. These are controlled rules positions, not competitive
deck validation, general transform certification, or inspection-UI certification.

Each run archives results, actual HTTP action records, full synthetic snapshots,
screenshots, source manifest, source files, service logs and the stopped local test
database under:

```text
/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/cathar-browser/<run>/
```

The archive directory is private. No raw user game is loaded. Runtime archives
exclude the ownership token, browser profile, dependencies and disposable caches.
All processes stop before SQLite archival. Every archived regular file is verified
byte-for-byte against local scratch, and an archive SHA-256 manifest is written.
Successful runtime copies are removed only after verification. Failed runs are
archived and retained for diagnosis. Do not run archived SQLite directly on NFS.

```bash
cd /mnt/rchfiles/codex-storage/mtg-deck-testing-lab/cathar-browser/<run>
sha256sum -c SHA256SUMS
```

Successful output contains six `PASS` lines and `success=true`. Exit status is
nonzero on a missing control, rule mismatch, restoration failure, service failure,
or inability to preserve and verify NFS evidence. This is a focused browser gate,
not the whole browser CI suite.

## CI Integration

The default `bash frontend/tests/run-browser-ci.sh` runs this dedicated gate
after the independent Officer harness. The shared harness freezes regular
backend/frontend source, excludes caller databases/caches/source symlinks, and
keeps its private Git inventory outside the guarded test source root. Its three
ordinary service groups stop before Officer, which stops its own services before
Cathar starts. The ordinary fixed ports are checked without killing listeners;
the singleton lock remains held through both independent gates. Failed ordinary
logs/frozen source are retained, including a later Cathar failure.

`MTG_FRONTEND_DEPS` accepts a frontend directory or its `node_modules` directory
at the shared entry point. It forwards the former to Officer and the latter to
Cathar. Individual Cathar invocation still expects `node_modules`.

```bash
bash frontend/tests/test-cathar-ci-harness.sh
bash frontend/tests/test-activated-top-selection-harness.sh
```

The lightweight integration check executes the actual shared preamble and
epilogue, substitutes owned test listeners for the long middle scenarios, and
observes ordered Officer/Cathar invocation, stop/port closure, declared bounded
scope, failure-log retention, singleton/foreign-port rejection, source/database
isolation, hosted artifact-root confinement and local absent-NFS rejection. It
is not a substitute for the six real browser cases or a full browser CI run.
