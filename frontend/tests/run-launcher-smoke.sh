#!/usr/bin/env bash
# Built real-app single-origin smoke. All state/build/profile data is disposable.
set -euo pipefail
launcher_smoke_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
source "$launcher_smoke_root/frontend/tests/browser-program-diagnostic.sh"

start_launcher() {
  (cd "$source_root" && exec setsid env MTG_LOCAL_PYTHON="$python_bin" \
    MTG_LOCAL_PORT="$launcher_port" MTG_DATABASE_PATH="$database" \
    bash scripts/start-local.sh) >"$work/logs/launcher.log" 2>&1 &
  launcher_pid=$!
}

stop_owned() {
  local pid=$1 grace=$2 forced=0 code=0 tick
  [[ -n "$pid" ]] || return 0
  kill -TERM -- "-$pid" 2>/dev/null || true
  for ((tick=0; tick<grace; tick++)); do
    if ! kill -0 -- "-$pid" 2>/dev/null; then break; fi
    sleep 0.1
  done
  if kill -0 -- "-$pid" 2>/dev/null; then
    forced=1
    kill -KILL -- "-$pid" 2>/dev/null || true
  fi
  wait "$pid" || code=$?
  ((forced == 0)) && [[ "$code" = 0 || "$code" = 143 ]]
}

stop_launcher() {
  local pid=$launcher_pid
  launcher_pid=''
  stop_owned "$pid" 250
}

wait_for_app() {
  for _ in $(seq 1 240); do
    if curl -fsS "http://127.0.0.1:$launcher_port/api/health" >/dev/null 2>&1; then return; fi
    if ! kill -0 "$launcher_pid" 2>/dev/null; then break; fi
    sleep 0.25
  done
  echo "Launcher was not ready; see $work/logs/launcher.log" >&2
  return 1
}

install_frontend() {
  (cd "$source_root/frontend" && timeout 900s npm ci --include=dev --no-audit --no-fund) >"$work/logs/npm-ci.log" 2>&1
}

main() {
  (($# == 0)) || { echo 'No arguments; use MTG_TEST_PYTHON and MTG_CHROME.' >&2; return 2; }
  local root=$launcher_smoke_root
  local python_bin=${MTG_TEST_PYTHON:-$root/backend/.venv/bin/python}
  local browser=${MTG_CHROME:-$(command -v google-chrome || command -v chromium || true)}
  local sandbox=${MTG_BROWSER_NO_SANDBOX:-0}
  [[ "$sandbox" = 0 || "$sandbox" = 1 ]] || return 2
  [[ -x "$python_bin" && -x "$browser" ]] || { echo 'Backend Python and Chrome/Chromium are required.' >&2; return 2; }
  python_bin=$(realpath -s "$python_bin")
  node -e 'if (process.version !== "v24.22.0") throw Error("Requires CI Node v24.22.0")'
  command -v npm >/dev/null; command -v setsid >/dev/null
  command -v flock >/dev/null; command -v ss >/dev/null; command -v timeout >/dev/null
  [[ -z "$(git -C "$root" status --porcelain --untracked-files=all)" ]] || {
    echo 'Run from a clean committed checkout; no working-tree source is copied.' >&2; return 2;
  }
  # Share the existing browser-CI port lease, without changing its runner/cohort.
  exec 9>"${TMPDIR:-/tmp}/mtg-browser-ci.lock"
  flock -n 9 || { echo 'Another browser run owns the test ports.' >&2; return 2; }
  [[ -z "$(ss -H -ltn '( sport = :15173 or sport = :19222 )')" ]] || {
    echo 'Ports 15173 and 19222 must be unused; no foreign service is stopped.' >&2; return 2;
  }
  # EXIT cleanup can run after main returns, so these owned-process handles
  # deliberately outlive main's local scope.
  work='' source_root='' database='' launcher_port=15173 launcher_pid='' browser_pid=''
  launcher_smoke_stage=prepare
  work=$(mktemp -d "${TMPDIR:-/tmp}/mtg-launcher-smoke-XXXXXX")
  source_root="$work/source"; database="$work/state/app.sqlite3"
  mkdir -m 700 "$source_root" "$work/state" "$work/profile" "$work/logs" "$work/npm-cache"
  git -C "$root" archive HEAD | tar -x -C "$source_root"
  git -C "$root" rev-parse HEAD >"$work/revision.txt"
  echo "Launcher smoke workspace: $work"
  cleanup() {
    local status=$?
    if [[ -n "$launcher_pid" ]]; then stop_launcher || { ((status)) || status=1; }; fi
    if [[ -n "$browser_pid" ]]; then stop_owned "$browser_pid" 50 || true; browser_pid=''; fi
    trap - EXIT
    if ((status)); then echo "FAIL launcher smoke stage: $launcher_smoke_stage" >&2; fi
    echo "Retained private smoke workspace: $work"
    exit "$status"
  }
  trap cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  # Capture selected executables/options above, then discard inherited app secrets
  # and mutation/runtime overrides without printing their values.
  for setting in ${!MTG_@}; do unset "$setting"; done
  for setting in ${!VITE_@}; do unset "$setting"; done
  unset PYTHONPATH PYTHONHOME NODE_OPTIONS
  export PYTHONDONTWRITEBYTECODE=1 npm_config_cache="$work/npm-cache"
  launcher_smoke_stage=frontend-install
  install_frontend
  launcher_smoke_stage=frontend-build
  (cd "$source_root/frontend" && NODE_ENV=production VITE_API_BASE_URL=/api \
    VITE_REQUEST_SIGNAL_DIAGNOSTICS=0 timeout 180s npm run build) >"$work/logs/build.log" 2>&1
  [[ ! -e "$source_root/backend/mtg_lab.db" && ! -e "$database" ]]
  launcher_smoke_stage=launcher-start
  start_launcher
  wait_for_app
  launcher_smoke_stage=browser-start
  local flags=()
  [[ "$sandbox" = 0 ]] || flags+=(--no-sandbox)
  setsid "$browser" --headless --disable-dev-shm-usage --no-first-run "${flags[@]}" \
    --user-data-dir="$work/profile" --remote-debugging-address=127.0.0.1 \
    --remote-debugging-port=19222 about:blank >"$work/logs/browser.log" 2>&1 &
  browser_pid=$!
  local ready=0
  for _ in $(seq 1 120); do
    if curl -fsS http://127.0.0.1:19222/json/version >/dev/null 2>&1; then ready=1; break; fi
    if ! kill -0 "$browser_pid" 2>/dev/null; then break; fi
    sleep 0.25
  done
  ((ready)) || { echo "Browser was not ready; see $work/logs/browser.log" >&2; return 1; }
  launcher_smoke_stage=browser-scenario
  (cd "$source_root/frontend" && MTG_LAUNCHER_ORIGIN=http://127.0.0.1:15173 \
    run_browser_program browser-launcher-smoke.mjs timeout 180s node tests/browser-launcher-smoke.mjs \
      --create "$work/state/browser-checkpoint.json")
  # A new real backend process uses the same DB and built assets. The Chrome
  # profile/localStorage remains, while the first scenario's tab has closed.
  launcher_smoke_stage=launcher-restart
  stop_launcher
  start_launcher
  wait_for_app
  launcher_smoke_stage=browser-scenario
  (cd "$source_root/frontend" && MTG_LAUNCHER_ORIGIN=http://127.0.0.1:15173 \
    run_browser_program browser-launcher-smoke.mjs timeout 90s node tests/browser-launcher-smoke.mjs \
      --restore "$work/state/browser-checkpoint.json")
  stop_launcher
  printf 'PASS built launcher real-app browser smoke and SQLite process restart\n'
}

if [[ "${BASH_SOURCE[0]}" = "$0" ]]; then main "$@"; fi
