#!/usr/bin/env bash
set -euo pipefail

scratch=$(mktemp -d /tmp/mtg-browser-ci-XXXXXX)
profile=$(mktemp -d /tmp/mtg-browser-profile-XXXXXX)
git ls-files backend | tar -cf - -T - | tar -xf - -C "$scratch"

backend_pid=''
frontend_pid=''
browser_pid=''
cleanup() {
  kill "$backend_pid" "$frontend_pid" "$browser_pid" 2>/dev/null || true
}
trap cleanup EXIT

start_backend() {
  (cd "$scratch/backend" && exec python -m uvicorn tests.browser_fixture_server:app --host 127.0.0.1 --port 10199) >"$scratch/backend.log" 2>&1 &
  backend_pid=$!
}

start_backend
(cd frontend && exec env VITE_API_BASE_URL=http://127.0.0.1:10199 ./node_modules/.bin/vite --host 127.0.0.1 --port 15173 --strictPort) >"$scratch/frontend.log" 2>&1 &
frontend_pid=$!

browser=$(command -v google-chrome || command -v chromium)
browser_flags=()
if [[ "${MTG_BROWSER_NO_SANDBOX:-}" == 1 ]]; then browser_flags+=(--no-sandbox); fi
"$browser" --headless --disable-dev-shm-usage --no-first-run "${browser_flags[@]}" \
  --user-data-dir="$profile" --remote-debugging-port=19222 about:blank >"$scratch/browser.log" 2>&1 &
browser_pid=$!

wait_for_services() {
  for _ in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:10199/health >/dev/null 2>&1 \
      && curl -fsS http://127.0.0.1:15173/ >/dev/null 2>&1 \
      && curl -fsS http://127.0.0.1:19222/json/version >/dev/null 2>&1; then return; fi
    sleep 0.25
  done
  tail -n 40 "$scratch/backend.log" "$scratch/frontend.log" "$scratch/browser.log"
  exit 1
}

wait_for_services
echo 'Browser CI: action scenarios'
(cd frontend && timeout 300s node tests/browser-human-actions.mjs)
echo 'Browser CI: App recovery scenarios'
(cd frontend && timeout 120s node tests/browser-recovery.mjs)
echo 'Browser CI: stopping copied backend'
kill "$backend_pid"
for _ in $(seq 1 50); do
  if ! kill -0 "$backend_pid" 2>/dev/null; then break; fi
  sleep 0.1
done
kill -KILL "$backend_pid" 2>/dev/null || true
wait "$backend_pid" 2>/dev/null || true
start_backend
wait_for_services
echo 'Browser CI: verifying process restart'
(cd frontend && timeout 120s node tests/browser-recovery.mjs --verify-restart)
echo 'Browser CI: match creation recovery'
(cd frontend && timeout 120s node tests/browser-start-recovery.mjs)
echo 'Browser CI: sideboard transition'
(cd frontend && timeout 120s node tests/browser-sideboard.mjs)
echo 'Browser CI: natural AI BO3'
(cd frontend && timeout 180s node tests/browser-live-bo3.mjs)
echo 'Browser CI: natural human BO3'
(cd frontend && timeout 240s node tests/browser-human-bo3.mjs)
