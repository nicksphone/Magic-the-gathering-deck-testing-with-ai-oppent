# Built launcher real-app smoke

This adds code and tests for the PR72 single-origin launcher. No full browser
run is claimed by this document. Keep the existing pinned browser runner,
natural BO3 cohort and fixture modules unchanged. This is a separate focused
smoke, not the clean-checkout/full-browser/Firefox acceptance gate.

## In-process real-app check

From `backend/`, with the normal backend dependencies installed:

```sh
python -B -m pytest -q tests/test_launcher_real_app.py
```

The test copies only application Python/JSON/SVG inputs to a private temporary
tree, excludes developer databases/caches/local knowledge/test modules and
symlinks, and supplies a tiny explicit HTML/JS fixture. Two fresh Python
processes use the actual `local_web.create_app` factory and real app lifespan
through TestClient. The first creates a seeded all-Island human/human match,
keeps both hands and plays a legal land through `/api`. The second opens the
same relocated SQLite DB, restores the exact match and retries the original
start/action keys. Stale intent must return 409, saved rows must remain equal,
local media must work, and the capacity owner must close before process exit.
Network connections are refused in these test processes.

The HTML is an ASGI fixture, **not a production build or browser result**.
The complete test needs a host where TestClient's async/thread runtime works;
collection or the two pure copy/environment tests alone do not prove it passed.

## Real browser command (host run)

After the launcher and this smoke branch are integrated, use a clean committed
checkout, Linux, Node 24.22.0, npm, a backend Python with the hash-locked
application dependencies, and installed Chrome/Chromium. No Java/Forge runtime
is required. From the repository root:

```sh
MTG_TEST_PYTHON=/absolute/backend-venv/bin/python \
  MTG_CHROME=/absolute/path/to/google-chrome \
  bash frontend/tests/run-launcher-smoke.sh
```

The script creates a private disposable Git archive, fresh npm cache,
production `/api` frontend build, relocated SQLite DB and browser profile.
It invokes **the actual `scripts/start-local.sh`**, not a fixture app, on
`127.0.0.1:15173`; Chrome's CDP port is 19222. Both ports must be free. It shares
the existing browser-CI port lease and never stops a foreign listener. The
selected Python path retains its venv symlink. No developer database, images,
node_modules, browser profile, pending start or saved match is copied in.
Only the disposable frontend receives `npm ci --include=dev`; the checkout's dependency tree
is unchanged. Backend dependency installation is a separate prerequisite.

The CDP scenario uses real `/api/matches/start` to create a **fresh canonical
all-Island opening**, not a declared midgame fixture or competitive AI episode.
App restores it, keeps both hands and plays the specifically offered land
through real UI controls. Each UI intent must increment revision exactly once.
It checks full state after page refresh, captures the first UI action's actual
key/body and proves its retry does not mutate the match. The runner stops and
actually waits for the launcher, starts a new backend process against the same
SQLite file, then opens App again using the retained browser localStorage. The
second phase requires exact state equality, original start/action-key retries
and stale-revision rejection. App API reads/writes must stay on the launcher
origin under `/api`; production bundle assets must be present and Vite/HMR
assets absent. Runtime exceptions/console errors fail the scenario. Local
`/card-images` and reserved-path 404 responses are checked too.

Success prints two scenario PASS lines and the final launcher PASS line. A
failure or timeout is a failed smoke; do not infer success from retained
checkpoint files. Owned processes are stopped, and the private workspace path
is retained for diagnosis. The script does not delete SQLite owner locks or
retry failed writes. Logs, profiles, DBs and complete match checkpoints remain
private and must not be committed or published. The script never prints sealed
witness/report environment values. It clears inherited app/Vite overrides.

The default browser keeps its sandbox flags. Only if the chosen host's existing
CI policy explicitly requires it, `MTG_BROWSER_NO_SANDBOX=1` adds that flag; this
is never an automatic retry and is not a sandbox qualification. The smoke can
load normal external card images; its local-media assertion is not proof of
complete offline browser fallback. It does not establish long-session soak,
BO3, AI strength, LAN/TLS, cross-browser support or full renderer containment.

Pure contract checks (no browser/server startup):

```sh
cd frontend
npm run test:unit:launcher-smoke
```

They also run at the end of the existing `npm test` chain. The existing build
command, dependency lock and pinned browser cohort are unchanged. Record actual
host/CI results separately after execution; this file invents no run totals.
