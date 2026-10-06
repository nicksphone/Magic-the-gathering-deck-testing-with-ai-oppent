#!/usr/bin/env bash
set -euo pipefail
umask 077
source_root=$(cd "$(dirname "$0")/../.." && pwd -P)
python=${MTG_TEST_PYTHON:?Set external MTG_TEST_PYTHON}
deps=$(realpath "${MTG_FRONTEND_DEPS:?Set external node_modules directory}")
chrome=${MTG_CHROMIUM:-$(command -v google-chrome || command -v chromium)}
archive_base=${MTG_UI_DIAGNOSTICS_ARCHIVE:-/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/ui-action-diagnostics}
existing=$archive_base
while [[ ! -d "$existing" ]]; do existing=$(dirname "$existing"); done
[[ $(findmnt -n -T "$existing" -o FSTYPE | tail -1) =~ ^nfs4?$ ]] || { echo 'Mounted NFS evidence required' >&2; exit 1; }
[[ $(git -C "$source_root" rev-parse --show-toplevel) == "$source_root" ]]
git -C "$source_root" diff --quiet HEAD -- backend frontend \
  ':(exclude)frontend/tests/browser-ui-action-diagnostics.mjs' \
  ':(exclude)frontend/tests/run-ui-action-diagnostics.sh' || { echo 'Freeze product source in an isolated Git baseline first' >&2; exit 1; }
runtime=$(mktemp -d /tmp/mtg-ui-action-diagnostics-run-XXXXXX)
[[ $(stat -f -c %T "$runtime") != nfs* ]]
archive="$archive_base/$(basename "$runtime")"
mkdir -p "$archive/private" "$runtime/evidence"
pids=()
finish() {
  status=$?
  trap - EXIT INT TERM
  for pid in "${pids[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${pids[@]}"; do
    for _ in {1..50}; do kill -0 "$pid" 2>/dev/null || break; sleep .1; done
    if kill -0 "$pid" 2>/dev/null; then kill -KILL -- "-$pid" 2>/dev/null || true; fi
    wait "$pid" 2>/dev/null || true
  done
  printf '%s\n' "$status" > "$runtime/exit-status"
  tar --exclude='./frontend/node_modules' --exclude='./profile' --exclude='./vite-cache' --exclude='*/__pycache__' --exclude='*/image_cache' -czf "$archive/private/runtime.tar.gz" -C "$runtime" .
  gzip -t "$archive/private/runtime.tar.gz"
  "$python" - "$runtime" "$archive/private/runtime.tar.gz" <<'PY'
import hashlib,sys,tarfile
from pathlib import Path
root=Path(sys.argv[1]); count=0
with tarfile.open(sys.argv[2]) as archive:
    for item in archive:
        if item.isfile():
            assert hashlib.sha256(archive.extractfile(item).read()).digest()==hashlib.sha256((root/item.name).read_bytes()).digest(),item.name
            count+=1
print('Archive bytes verified:',count)
PY
  cp "$runtime/evidence/results.json" "$archive/results.json" 2>/dev/null || true
  (cd "$archive" && sha256sum private/runtime.tar.gz > SHA256SUMS && sha256sum -c SHA256SUMS)
  echo "ARCHIVE=$archive STATUS=$status RUNTIME=$runtime"
  if [[ $status == 0 ]]; then rm -rf -- "$runtime"; else echo 'RED runtime preserved locally for diagnosis'; fi
  exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Git baseline plus these new tests only; no runtime or foreign SQLite is copied.
git -C "$source_root" archive HEAD backend frontend | tar -x -C "$runtime"
for file in run-ui-action-diagnostics.sh browser-ui-action-diagnostics.mjs; do cp "$source_root/frontend/tests/$file" "$runtime/frontend/tests/$file"; done
cp "$runtime/frontend/tests/ui_fixture_server.py" "$runtime/backend/tests/"
cp "$runtime/frontend/tests/ui_v2_fixture_server.py" "$runtime/backend/tests/"
[[ ! -e "$runtime/.git" && ! -e "$runtime/backend/mtg_lab.db" ]]
find "$runtime/backend" "$runtime/frontend" -type f -print0 | sort -z | xargs -0 sha256sum > "$runtime/source-manifest.sha256"
mkdir "$runtime/frontend/node_modules"
for entry in "$deps"/*; do ln -s "$entry" "$runtime/frontend/node_modules/$(basename "$entry")"; done
read -r backend_port frontend_port cdp_port < <("$python" - <<'PY'
import socket
sockets=[socket.socket() for _ in range(3)]
for s in sockets:s.bind(('127.0.0.1',0))
ports=[s.getsockname()[1] for s in sockets]
assert not set(ports)&{10199,15173,19222}
print(*ports)
PY
)
export MTG_BACKEND_ORIGIN="http://127.0.0.1:$backend_port" MTG_FRONTEND_ORIGIN="http://127.0.0.1:$frontend_port" MTG_BROWSER_ORIGIN="http://127.0.0.1:$cdp_port" MTG_UI_EVIDENCE="$runtime/evidence"
printf 'export default {cacheDir:%s,server:{proxy:{"/card-images":{target:%s}}}};\n' "\"$runtime/vite-cache\"" "\"$MTG_BACKEND_ORIGIN\"" > "$runtime/frontend/vite.diagnostics.config.mjs"
start() {
  label=$1; cwd=$2; shift 2
  (cd "$cwd" && exec setsid "$@") > "$runtime/$label.log" 2>&1 &
  pids+=("$!")
  echo "OWN $label PID=$! ROOT=$runtime PORTS=$backend_port/$frontend_port/$cdp_port" | tee -a "$runtime/processes.txt"
}
start backend "$runtime/backend" "$python" -m uvicorn tests.ui_v2_fixture_server:app --host 127.0.0.1 --port "$backend_port"
start frontend "$runtime/frontend" env VITE_API_BASE_URL="$MTG_BACKEND_ORIGIN" node "$deps/vite/bin/vite.js" --config vite.diagnostics.config.mjs --host 127.0.0.1 --port "$frontend_port" --strictPort
chrome_args=(--headless --disable-dev-shm-usage --no-first-run "--user-data-dir=$runtime/profile" --remote-debugging-address=127.0.0.1 "--remote-debugging-port=$cdp_port")
[[ ${MTG_BROWSER_NO_SANDBOX:-0} != 1 ]] || chrome_args+=(--no-sandbox)
start chromium "$runtime" "$chrome" "${chrome_args[@]}" about:blank
for endpoint in "$MTG_BACKEND_ORIGIN/health" "$MTG_FRONTEND_ORIGIN" "$MTG_BROWSER_ORIGIN/json/version"; do
  ready=0
  for _ in {1..300}; do
    for pid in "${pids[@]}"; do kill -0 "$pid" || exit 1; done
    if curl --silent --fail --max-time 1 "$endpoint" >/dev/null; then ready=1; break; fi
    sleep .2
  done
  [[ $ready == 1 ]] || { echo "Startup timeout: $endpoint"; exit 1; }
done
set +e
node --experimental-strip-types "$runtime/frontend/tests/browser-ui-action-diagnostics.mjs" 2>&1 | tee "$runtime/probe.log"
status=${PIPESTATUS[0]}
set -e
sha256sum -c "$runtime/source-manifest.sha256" > "$runtime/source-unchanged.log"
exit "$status"
