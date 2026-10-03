#!/usr/bin/env bash
set -euo pipefail

# The harness owns fixed loopback ports; concurrent runs must not share them.
exec 9>"${TMPDIR:-/tmp}/mtg-browser-ci.lock"
if ! flock -n 9; then
  echo "Another browser CI run owns the test ports; wait for it to finish." >&2
  exit 1
fi

python_bin="${MTG_TEST_PYTHON:-$PWD/backend/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  echo "Browser CI requires backend/.venv/bin/python or MTG_TEST_PYTHON" >&2
  exit 1
fi

scratch=$(mktemp -d "${TMPDIR:-/tmp}/mtg-browser-ci-XXXXXX")
profile=$(mktemp -d "${TMPDIR:-/tmp}/mtg-browser-profile-XXXXXX")
git ls-files backend | tar -cf - -T - | tar -xf - -C "$scratch"
{ git diff --name-only -- backend; git ls-files --others --exclude-standard backend; } | sort -u | while IFS= read -r path; do
  if [[ -f "$path" ]]; then install -D "$path" "$scratch/$path"; fi
done

backend_pid=''
frontend_pid=''
browser_pid=''
cleanup() {
  status=$?
  kill "$backend_pid" "$frontend_pid" "$browser_pid" 2>/dev/null || true
  wait "$backend_pid" "$frontend_pid" "$browser_pid" 2>/dev/null || true
  if [[ "$status" -eq 0 && "${MTG_KEEP_TEST_ARTIFACTS:-0}" != 1 ]]; then
    rm -r -- "$scratch" "$profile"
  else
    echo "Retained browser test artifacts: $scratch and $profile" >&2
  fi
}
trap cleanup EXIT

start_backend() {
  (cd "$scratch/backend" && exec "$python_bin" -m uvicorn tests.browser_fixture_server:app --host 127.0.0.1 --port 10199) >"$scratch/backend.log" 2>&1 &
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
  # Empty-cache corpus bootstrap can exceed 15 seconds on a busy test host.
  for _ in $(seq 1 240); do
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
echo 'Browser CI: simulation preflight'
(cd frontend && timeout 90s node tests/browser-simulation-preflight.mjs)
echo 'Browser CI: canonical combat coverage preflight'
(cd frontend && timeout 90s node tests/browser-combat-coverage.mjs)
echo 'Browser CI: declaration limits'
(cd frontend && timeout 90s node tests/browser-declaration-limits.mjs)
echo 'Browser CI: combat payments and target requirements'
(cd frontend && timeout 90s node tests/browser-combat-payments-requirements.mjs)
echo 'Browser CI: deliberate hybrid attack payments and minimum blocker requirements'
(cd frontend && timeout 120s node tests/browser-combat-branches.mjs)
echo 'Browser CI: domain and resolved temporary attack/block costs'
(cd frontend && timeout 180s node tests/browser-combat-domain-temporary.mjs)
echo 'Browser CI: conditional attack/block costs'
(cd frontend && timeout 180s node tests/browser-conditional-combat-costs.mjs)
echo 'Browser CI: multiple-block capacity and one payment per blocker'
(cd frontend && timeout 120s node tests/browser-combat-capacity.mjs)
echo 'Browser CI: specific combat recipients'
(cd frontend && timeout 120s node tests/browser-recipient-combat.mjs)
echo 'Browser CI: bestow casting choices'
(cd frontend && timeout 120s node tests/browser-bestow.mjs)
echo 'Browser CI: hand activations and owned counter payments'
(cd frontend && timeout 120s node tests/browser-hand-activations.mjs)
echo 'Browser CI: legendary channels and owned resolution choices'
(cd frontend && timeout 120s node tests/browser-legendary-channels.mjs)
echo 'Browser CI: private surveil, ordering and payoff triggers'
(cd frontend && timeout 120s node tests/browser-surveil.mjs)
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
(cd frontend && timeout 180s node tests/browser-start-recovery.mjs)
echo 'Browser CI: sideboard transition'
(cd frontend && timeout 120s node tests/browser-sideboard.mjs)
echo 'Browser CI: natural AI BO3'
(cd frontend && timeout 180s node tests/browser-live-bo3.mjs)
echo 'Browser CI: natural human BO3'
(cd frontend && timeout 240s node tests/browser-human-bo3.mjs)
echo 'Browser CI: natural human-vs-human BO3'
(cd frontend && MTG_HUMAN_BO3_OPPONENT=human timeout 360s node tests/browser-human-bo3.mjs)
