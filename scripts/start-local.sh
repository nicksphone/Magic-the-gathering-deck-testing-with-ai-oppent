#!/usr/bin/env bash
# Local single-operator launcher; requires an already-built frontend.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd -P)
port=${MTG_LOCAL_PORT:-5173}
if [[ $# != 0 || ! "$port" =~ ^[1-9][0-9]{3,4}$ ]] || ((port < 1024 || port > 65535)); then
  echo 'Local port must be 1024..65535; this command takes no arguments.' >&2
  exit 2
fi
python_bin=${MTG_LOCAL_PYTHON:-$root/backend/.venv/bin/python}
if [[ ! -x "$python_bin" ]]; then
  echo 'Install backend dependencies and set MTG_LOCAL_PYTHON to its Python executable.' >&2
  exit 2
fi
if [[ ! -f "$root/frontend/dist/index.html" || -L "$root/frontend/dist" || -L "$root/frontend/dist/index.html" ]]; then
  echo 'Missing regular frontend build: run npm ci and npm run build in frontend first.' >&2
  exit 2
fi
python_bin=$(realpath "$python_bin")
# Uvicorn's environment must not enable reload or disable ownership lifespan.
for setting in ${!UVICORN_@}; do unset "$setting"; done
unset WEB_CONCURRENCY
export MTG_TRUSTED_ORIGINS="http://127.0.0.1:$port"
cd "$root/backend"
echo "Open http://127.0.0.1:$port (local single-operator table; Ctrl-C to stop)."
exec "$python_bin" -m uvicorn local_web:create_app --factory --host 127.0.0.1 --port "$port" --workers 1 --lifespan on --no-access-log --no-proxy-headers
