# One-command local table launcher

Use the [README quick-start](../../README.md#setup) for the supported runtime,
backend wheel-lock install, `npm ci`, same-origin `/api` production build and
private DB directory. From the repository root, with that installation ready:

```sh
MTG_DATABASE_PATH=/absolute/private-local-directory/mtg.sqlite3 \
  MTG_LOCAL_PYTHON="$PWD/backend/.venv/bin/python" \
  bash scripts/start-local.sh
```

The directory must already exist and the path must be canonical, on local storage
outside the checkout. Reuse this exact DB path on later starts. For a fresh
installation it may be an absent file; if a legacy `backend/mtg_lab.db` exists,
startup refuses to abandon it for a new path. Preserve/relocate existing data
through the [backup/restore guidance](saved-game-backup-restore.md), not by deleting
files or owner locks. Without `MTG_DATABASE_PATH` the backend-local default still
applies; that default is outside the standalone maintenance CLI's scope.

Open **http://127.0.0.1:5173**. One Uvicorn worker serves the built frontend,
mounts the existing application at `/api`, and serves image cache at
`/card-images`. There is no Vite dev server, Node runtime server, second backend
or proxy to start. It does not install dependencies or silently rebuild.
Build with `VITE_API_BASE_URL=/api`, as in README; an external-origin build needs
rebuilding before this local mode. The backend venv is the default Python path.

Optional `MTG_LOCAL_PORT` is 1024..65535. Host and worker count are fixed to
127.0.0.1 and one; hostile worker-count environment values do not override the
explicit Uvicorn argument. Inherited `UVICORN_*` options and `WEB_CONCURRENCY`
are removed, and lifespan is explicitly on so environment settings cannot enable
reload or bypass database ownership startup. The launcher takes no arguments.
Missing/aliased frontend builds fail before importing main or starting a server.
Use Ctrl-C for normal lifespan shutdown; the shell execs Uvicorn directly.
Never delete owner locks or replace a live database to force startup.

This composition runs the **existing** main app lifespan exactly once, preserving
capacity ownership, startup seed/import steps and shutdown draining. It uses the
selected database and preserves saved data; it is not a fresh-DB reset. No engine,
persistence, CORS or source-pin file is edited. The API retains
its browser-origin middleware; the script configures only the exact loopback
origin. Static navigation falls back to index.html; missing assets/API/media
stay errors and dot files are refused. Files outside the build directory are
not served through StaticFiles symlinks.

This is **trusted local single-operator HTTP**, with no TLS or account login.
Other local users/processes may access loopback; it is not a sandbox or tenant
boundary. Do not bind it to a LAN/public interface or use it instead of the
reviewed HTTPS operator for those deployments. A working local launcher does
not qualify remote certificate trust, browser cohort acceptance or RC readiness.

## Verification

```sh
cd backend
python -m pytest -q tests/test_local_launcher.py tests/test_local_web_http.py
```

Seven launcher/file/lifespan contract cases failed before implementation and
passed locally after it. Eight real ASGI HTTP/static cases use an inert API and
owned build/media fixtures, never the application's DB. Collection alone is not
a pass: the local sandbox blocks threaded TestClient.
Claude reported 15 passing launcher/static tests at `f0b94a90` on the launcher
branch. The
separate real-app smoke at `1b7814bc` passed three Python tests and its Chrome
create/restore/SQLite-restart flow on the host. See
[the smoke command and scope](launcher-real-app-smoke.md). Those are bounded,
source-specific results, not a new run from this docs edit or full current-source
browser/clean-checkout/native-vendor acceptance.


## Retained limitations

Use the [single-operator contract](single-operator-deployment.md) for storage and
exposure limits, and the [README limitations](../../README.md#known-limitations-and-next-upgrades)
for rules/data/AI gaps. The maintainer retains the historical `legacy_unknown`
source-cleanup seam as an RC limitation with two strict expected failures;
[the ledger](known-failures.md) distinguishes it from a normal-LIFO exploit.
Backing up preserves old snapshots; it does not repair or migrate that ambiguity.
