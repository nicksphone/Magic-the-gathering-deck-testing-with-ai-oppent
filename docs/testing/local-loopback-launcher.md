# One-command local table launcher

After installing the backend dependencies and building the frontend with its
normal same-origin `/api` configuration:

```sh
(cd frontend && npm ci && npm run build)
MTG_LOCAL_PYTHON=/absolute/path/to/backend-python bash scripts/start-local.sh
```

Open **http://127.0.0.1:5173**. One Uvicorn worker serves the built frontend,
mounts the existing application at `/api`, and serves its image cache at
`/card-images`. There is no Vite dev server, Node runtime server, second backend
process or proxy to start. It does not install dependencies or silently rebuild.
If you built with an external `VITE_API_BASE_URL`, rebuild with the default `/api`
configuration first. The existing backend venv is the default Python path.

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
normal backend-local database and preserves saved data; it is not a fresh-DB
reset. No engine, persistence, CORS or source-pin file is edited. The API retains
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
owned build/media fixtures, never the application's DB. Host execution is required
for those cases because the local sandbox blocks the existing threaded TestClient
runtime; collection alone is not a pass. A final real-app browser smoke should
start this command on an isolated source with an owned DB, check `/api/health`,
load the UI, start/reload a match, stop gracefully and verify saved restoration.
No live-server/browser acceptance for this launcher is claimed in this branch.
