#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
python=${MTG_TEST_PYTHON:-$root/backend/.venv/bin/python}
deps=${MTG_FRONTEND_DEPS:-$root/frontend}
runtime=$(mktemp -d "${TMPDIR:-/tmp}/mtg-officer-http-XXXXXX")
if [[ $(stat -f -c %T "$runtime") == nfs* ]]; then
  echo 'SQLite test runtime must be on local storage' >&2
  exit 1
fi
out=/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/activated-top-selection/http-browser-$(date -u +%Y%m%dT%H%M%SZ)
test "$(findmnt -T /mnt/rchfiles/codex-storage -n -o FSTYPE | tail -1)" = nfs
mkdir -p "$out"
printf 'NFS write verification\n' > "$out/.probe"
test "$(cat "$out/.probe")" = 'NFS write verification'
rm "$out/.probe"
export MTG_OFFICER_RUNTIME="$runtime" MTG_OFFICER_EVIDENCE="$out" MTG_FRONTEND_DEPS="$deps"
export MTG_BACKEND_ORIGIN=http://127.0.0.1:10237 MTG_FRONTEND_ORIGIN=http://127.0.0.1:15237 MTG_BROWSER_ORIGIN=http://127.0.0.1:19237
export VITE_API_BASE_URL="$MTG_BACKEND_ORIGIN" PYTHONDONTWRITEBYTECODE=1
backend='' frontend='' browser=''
cleanup() {
  result=$?
  for pid in "$backend" "$frontend" "$browser"; do if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi; done
  if [[ -f "$runtime/officer-test.sqlite" ]]; then
    "$python" - "$runtime/officer-test.sqlite" <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as connection:
    assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
PY
  fi
  tar -czf "$out/runtime-evidence.tar.gz" -C "$runtime" .
  tar -dzf "$out/runtime-evidence.tar.gz" -C "$runtime"
  printf 'test_exit=%s\nruntime=%s\nevidence=%s\n' "$result" "$runtime" "$out" > "$out/run-status.txt"
  if [[ "$result" == 0 ]]; then rm -r -- "$runtime"; else printf 'Retained failed runtime: %s\n' "$runtime"; fi
  printf 'Evidence: %s\n' "$out"
}
trap cleanup EXIT
for port in 10237 15237 19237; do
  if curl -fsS --max-time 1 "http://127.0.0.1:$port/" >/dev/null 2>&1; then echo "Port $port already in use" >&2; exit 1; fi
done
start_backend() {
  "$python" "$root/frontend/tests/activated-top-selection-fixture.py" > "$runtime/backend-${1}.log" 2>&1 &
  backend=$!
  for _ in $(seq 1 120); do
    if curl -fsS "$MTG_BACKEND_ORIGIN/health" >/dev/null 2>&1; then return; fi
    if ! kill -0 "$backend" 2>/dev/null; then cat "$runtime/backend-${1}.log"; exit 1; fi
    sleep 0.25
  done
  cat "$runtime/backend-${1}.log"; exit 1
}
start_backend before-restart
timeout 120s node "$root/frontend/tests/browser-activated-top-selection.mjs" prepare 2>&1 | tee "$out/http-results.log"
kill "$backend"; wait "$backend" || true; backend=''
start_backend after-restart
node "$deps/node_modules/vite/bin/vite.js" --config "$root/frontend/tests/vite-activated-top-selection.mjs" > "$runtime/frontend.log" 2>&1 &
frontend=$!
chrome=${MTG_CHROME:-/home/nick/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome}
"$chrome" --headless --disable-dev-shm-usage --no-first-run --no-sandbox \
  --user-data-dir="$runtime/browser-profile" --remote-debugging-port=19237 about:blank > "$runtime/browser.log" 2>&1 &
browser=$!
for _ in $(seq 1 120); do
  if curl -fsS "$MTG_FRONTEND_ORIGIN/" >/dev/null 2>&1 && curl -fsS "$MTG_BROWSER_ORIGIN/json/version" >/dev/null 2>&1; then break; fi
  if ! kill -0 "$frontend" 2>/dev/null || ! kill -0 "$browser" 2>/dev/null; then cat "$runtime/frontend.log" "$runtime/browser.log"; exit 1; fi
  sleep 0.25
done
timeout 240s node "$root/frontend/tests/browser-activated-top-selection.mjs" browser 2>&1 | tee "$out/browser-results.log"
