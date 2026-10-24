#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd -P)
cd "$root"
test "$(realpath "$(git rev-parse --show-toplevel)")" = "$root"

source "$root/frontend/tests/browser-program-diagnostic.sh"

# Select the browser before starting services.
browser="${MTG_CHROME:-}"
if [[ -z "$browser" ]]; then
  if [[ -n "${MTG_BROWSER_VENDOR:-}" ]]; then
    echo 'Native browser mode requires MTG_CHROME; automatic fallback is disabled.' >&2
    exit 2
  fi
  browser=$(command -v google-chrome || command -v chromium)
fi
if [[ -n "${MTG_BROWSER_VENDOR:-}" ]]; then
  run_browser_program "browser-vendor-preflight.mjs" node frontend/tests/browser-vendor-preflight.mjs --check-config "$browser"
fi

# The harness owns fixed loopback ports; concurrent runs must not share them.
exec 9>"${TMPDIR:-/tmp}/mtg-browser-ci.lock"
if ! flock -n 9; then
  echo "Another browser CI run owns the test ports; wait for it to finish." >&2
  exit 1
fi
if [[ -n "$(ss -H -ltn '( sport = :10199 or sport = :15173 or sport = :19222 )')" ]]; then
  echo 'Browser CI ports 10199, 15173 and 19222 must be unused; no foreign service will be stopped.' >&2
  exit 1
fi

python_bin="${MTG_TEST_PYTHON:-$PWD/backend/.venv/bin/python}"
if [[ ! -x "$python_bin" && -z "${MTG_TEST_PYTHON:-}" ]]; then python_bin=$(command -v python3); fi
if [[ ! -x "$python_bin" ]]; then
  echo "Browser CI requires backend/.venv/bin/python or MTG_TEST_PYTHON" >&2
  exit 1
fi
python_bin=$(realpath -s "$python_bin")
frontend_deps=$(realpath "${MTG_FRONTEND_DEPS:-$root/frontend/node_modules}")
if [[ -f "$frontend_deps/node_modules/vite/bin/vite.js" ]]; then frontend_deps="$frontend_deps/node_modules"; fi
test -f "$frontend_deps/vite/bin/vite.js"
test "$(basename "$frontend_deps")" = node_modules

scratch=$(mktemp -d "${TMPDIR:-/tmp}/mtg-browser-ci-XXXXXX")
profile=$(mktemp -d "${TMPDIR:-/tmp}/mtg-browser-profile-XXXXXX")
backend_pid=''
frontend_pid=''
browser_pid=''
stop_owned() {
  local pid=${1:-}
  [[ -n "$pid" ]] || return 0
  # All service groups were created by setsid, never discovered from a port.
  kill -TERM -- "-$pid" 2>/dev/null || true
  for _ in $(seq 1 50); do
    if ! kill -0 -- "-$pid" 2>/dev/null; then break; fi
    sleep 0.1
  done
  if kill -0 -- "-$pid" 2>/dev/null; then kill -KILL -- "-$pid" 2>/dev/null || true; fi
  wait "$pid" 2>/dev/null || true
}
stop_owned_services() {
  for pid in "$backend_pid" "$frontend_pid" "$browser_pid"; do stop_owned "$pid"; done
  backend_pid='' frontend_pid='' browser_pid=''
}
cleanup() {
  status=$?
  if ((status)); then report_browser_bootstrap_failure "$status" "${1:-1}" || :; fi
  stop_owned_services
  if [[ "$status" -eq 0 && "${MTG_KEEP_TEST_ARTIFACTS:-0}" != 1 ]]; then
    rm -r -- "$scratch" "$profile"
  else
    echo "Retained browser test artifacts: $scratch and $profile" >&2
  fi
}
trap 'cleanup "$LINENO"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Freeze regular source only; never import a caller DB or follow source symlinks.
[[ "$(stat -f -c %T "$scratch")" != nfs* ]]
git rev-parse HEAD > "$scratch/source-revision.txt"
while IFS= read -r -d '' path; do
  case "/$path/" in
    */node_modules/*|*/.venv/*|*/venv/*|*/__pycache__/*|*/.pytest_cache/*|*/.cache/*|*/cache/*|*/image_cache/*|*/diagnostics/*|*/training_runs/*|*/dist/*|*/logs/*|*/backend/knowledge/data/*|*/backend/backend/*) continue ;;
  esac
  case "$path" in *.db|*.db-*|*.sqlite|*.sqlite-*|*.sqlite3|*.sqlite3-*) continue ;; esac
  [[ -f "$path" && ! -L "$path" ]] || continue
  # A symlinked parent directory must not escape the checkout either.
  [[ "$(realpath "$path")" = "$root/$path" ]] || continue
  install -D "$path" "$scratch/$path"
done < <(git ls-files -z --cached --others --exclude-standard -- backend frontend)
cp "$scratch/frontend/tests/ui_fixture_server.py" "$scratch/frontend/tests/ui_v2_fixture_server.py" "$scratch/backend/tests/"
# Private Git inventory outside the test root lets independent gates recopy the
# same frozen source, without making guarded fixture imports look like live Git.
env -u GIT_DIR -u GIT_WORK_TREE git init --bare -q "$profile/source.git"
export GIT_DIR="$profile/source.git" GIT_WORK_TREE="$scratch"
cd "$scratch"
git add -- backend frontend
git -c user.name='Browser CI fixture' -c user.email=fixture@localhost commit -qm 'Frozen browser CI source'
mkdir "$scratch/frontend/node_modules"
for dependency in "$frontend_deps"/*; do
  ln -s "$dependency" "$scratch/frontend/node_modules/$(basename "$dependency")"
done
cat > "$scratch/frontend/vite.ci.config.ts" <<'VITE'
import base from './vite.config';
export default {...base, cacheDir: '../vite-cache'};
VITE
cd "$scratch"

start_backend() {
  (cd "$scratch/backend" && exec setsid env MTG_TRUSTED_ORIGINS=http://127.0.0.1:15173 "$python_bin" -m uvicorn tests.ui_v2_fixture_server:app --host 127.0.0.1 --port 10199) >"$scratch/backend.log" 2>&1 &
  backend_pid=$!
}

(cd frontend && NODE_ENV=development VITE_API_BASE_URL=http://127.0.0.1:10199 run_browser_program "prepare-development-frontend.mjs" node tests/prepare-development-frontend.mjs "$scratch/frontend" "$scratch/frontend/vite.ci.config.ts" "$scratch/frontend-dev-ci")
start_backend
(cd frontend && exec setsid env NODE_ENV=development VITE_API_BASE_URL=http://127.0.0.1:10199 node "$frontend_deps/vite/bin/vite.js" preview --mode development --outDir ../frontend-dev-ci --config vite.ci.config.ts --host 127.0.0.1 --port 15173 --strictPort) >"$scratch/frontend.log" 2>&1 &
frontend_pid=$!

browser_flags=()
if [[ "${MTG_BROWSER_NO_SANDBOX:-}" == 1 ]]; then browser_flags+=(--no-sandbox); fi
setsid "$browser" --headless --disable-dev-shm-usage --no-first-run "${browser_flags[@]}" \
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
(cd frontend && run_browser_program "browser-development-runtime-proof.mjs" timeout 30s node tests/browser-development-runtime-proof.mjs)
if (($#)); then
  echo 'Focused browser scenarios, not the full browser gate'
  for scenario in "$@"; do
    if [[ ! "$scenario" =~ ^browser-[a-z0-9-]+\.mjs$ || ! -f "frontend/tests/$scenario" ]]; then
      echo "Invalid browser scenario: $scenario" >&2
      exit 2
    fi
    (cd frontend && run_browser_program "$scenario" timeout 300s node "tests/$scenario")
  done
  exit 0
fi
# CORS transport diagnostic: ordinary hosted CDP only.
cors_diagnostic_status=0
if [[ -z "${MTG_BROWSER_VENDOR:-}" ]]; then
  (cd frontend && MTG_FRONTEND_ORIGIN=http://127.0.0.1:15173 MTG_BACKEND_ORIGIN=http://127.0.0.1:10199 run_browser_program "browser-cors-transport-diagnostic.mjs" timeout 45s node tests/browser-cors-transport-diagnostic.mjs) || cors_diagnostic_status=$?
else
  printf '%s\n' 'CORS_TRANSPORT_DIAGNOSTIC [{"classification":"not-applicable","reason":"native-vendor-scope"}]'
fi
echo 'Browser CI: async readiness helper'
(cd frontend && run_browser_program "browser-driver-async.mjs" timeout 30s node tests/browser-driver-async.mjs)
echo 'Browser CI: competitive table v2'
(cd frontend && MTG_UI_EVIDENCE="$scratch/ui-v2-evidence" MTG_BROWSER_ORIGIN=http://127.0.0.1:19222 MTG_FRONTEND_ORIGIN=http://127.0.0.1:15173 MTG_BACKEND_ORIGIN=http://127.0.0.1:10199 run_browser_program "browser-ui-v2.mjs" timeout 180s node tests/browser-ui-v2.mjs)
(cd frontend && MTG_BROWSER_ORIGIN=http://127.0.0.1:19222 MTG_FRONTEND_ORIGIN=http://127.0.0.1:15173 MTG_BACKEND_ORIGIN=http://127.0.0.1:10199 run_browser_program "browser-ui-v2-costs.mjs" timeout 180s node tests/browser-ui-v2-costs.mjs)
echo 'Browser CI: action scenarios'
(cd frontend && run_browser_program "browser-cast-resources.mjs" timeout 300s node tests/browser-cast-resources.mjs)
(cd frontend && run_browser_program "browser-graveyard-permissions.mjs" timeout 300s node tests/browser-graveyard-permissions.mjs)
(cd frontend && run_browser_program "browser-limited-graveyard-permissions.mjs" timeout 300s node tests/browser-limited-graveyard-permissions.mjs)
(cd frontend && run_browser_program "browser-graveyard-cast-methods.mjs" timeout 300s node tests/browser-graveyard-cast-methods.mjs)
(cd frontend && run_browser_program "browser-announced-color-costs.mjs" timeout 300s node tests/browser-announced-color-costs.mjs)
(cd frontend && run_browser_program "browser-opaque-selection.mjs" timeout 300s node tests/browser-opaque-selection.mjs)
(cd frontend && run_browser_program "browser-direct-combat.mjs" timeout 180s node tests/browser-direct-combat.mjs)
(cd frontend && MTG_TEST_PYTHON="$python_bin" MTG_FRONTEND_ORIGIN=http://127.0.0.1:15173 run_browser_program "browser-attack-all.mjs" timeout 180s node tests/browser-attack-all.mjs)
(cd frontend && run_browser_program "browser-game-over.mjs" timeout 180s node tests/browser-game-over.mjs)
(cd frontend && run_browser_program "browser-auto-progress.mjs" timeout 120s node tests/browser-auto-progress.mjs)
(cd frontend && run_browser_program "browser-activation-payments.mjs" timeout 180s node tests/browser-activation-payments.mjs)
(cd frontend && run_browser_program "browser-joint-activation-payments.mjs" timeout 120s node tests/browser-joint-activation-payments.mjs)
(cd frontend && run_browser_program "browser-nested-mana-life.mjs" timeout 120s node tests/browser-nested-mana-life.mjs)
(cd frontend && run_browser_program "browser-life-lock.mjs" timeout 120s node tests/browser-life-lock.mjs)
(cd frontend && run_browser_program "browser-life-conversion.mjs" timeout 120s node tests/browser-life-conversion.mjs)
(cd frontend && run_browser_program "browser-land-types.mjs" timeout 90s node tests/browser-land-types.mjs)
(cd frontend && run_browser_program "browser-human-actions.mjs" timeout 300s node tests/browser-human-actions.mjs)
(cd frontend && run_browser_program "browser-zone-keyword-actions.mjs" timeout 300s node tests/browser-zone-keyword-actions.mjs)
(cd frontend && run_browser_program "browser-ordered-targets.mjs" timeout 120s node tests/browser-ordered-targets.mjs)
(cd frontend && run_browser_program "browser-distinct-permanents.mjs" timeout 120s node tests/browser-distinct-permanents.mjs)
(cd frontend && run_browser_program "browser-ordered-modifiers.mjs" timeout 120s node tests/browser-ordered-modifiers.mjs)
(cd frontend && run_browser_program "browser-ordered-copy.mjs" timeout 120s node tests/browser-ordered-copy.mjs)
(cd frontend && run_browser_program "browser-linked-damage.mjs" timeout 180s node tests/browser-linked-damage.mjs)
(cd frontend && run_browser_program "browser-linked-copy.mjs" timeout 120s node tests/browser-linked-copy.mjs)
(cd frontend && run_browser_program "browser-conditional-copy.mjs" timeout 180s node tests/browser-conditional-copy.mjs)
echo 'Browser CI: simulation preflight'
(cd frontend && run_browser_program "browser-simulation-preflight.mjs" timeout 90s node tests/browser-simulation-preflight.mjs)
echo 'Browser CI: canonical combat coverage preflight'
(cd frontend && run_browser_program "browser-combat-coverage.mjs" timeout 90s node tests/browser-combat-coverage.mjs)
echo 'Browser CI: declaration limits'
(cd frontend && run_browser_program "browser-declaration-limits.mjs" timeout 90s node tests/browser-declaration-limits.mjs)
echo 'Browser CI: combat payments and target requirements'
(cd frontend && run_browser_program "browser-combat-payments-requirements.mjs" timeout 90s node tests/browser-combat-payments-requirements.mjs)
echo 'Browser CI: deliberate hybrid attack payments and minimum blocker requirements'
(cd frontend && run_browser_program "browser-combat-branches.mjs" timeout 120s node tests/browser-combat-branches.mjs)
echo 'Browser CI: domain and resolved temporary attack/block costs'
(cd frontend && run_browser_program "browser-combat-domain-temporary.mjs" timeout 180s node tests/browser-combat-domain-temporary.mjs)
echo 'Browser CI: conditional attack/block costs'
(cd frontend && run_browser_program "browser-conditional-combat-costs.mjs" timeout 180s node tests/browser-conditional-combat-costs.mjs)
echo 'Browser CI: multiple-block capacity and one payment per blocker'
(cd frontend && run_browser_program "browser-combat-capacity.mjs" timeout 120s node tests/browser-combat-capacity.mjs)
echo 'Browser CI: specific combat recipients'
(cd frontend && run_browser_program "browser-recipient-combat.mjs" timeout 120s node tests/browser-recipient-combat.mjs)
echo 'Browser CI: bestow casting choices'
(cd frontend && run_browser_program "browser-bestow.mjs" timeout 120s node tests/browser-bestow.mjs)
echo 'Browser CI: canonical devotion payoff families'
(cd frontend && run_browser_program "browser-devotion.mjs" timeout 180s node tests/browser-devotion.mjs)
echo 'Browser CI: compound defensive spell responses'
(cd frontend && run_browser_program "browser-defensive-responses.mjs" timeout 120s node tests/browser-defensive-responses.mjs)
echo 'Browser CI: conditional creature type transitions'
(cd frontend && run_browser_program "browser-conditional-creature-types.mjs" timeout 120s node tests/browser-conditional-creature-types.mjs)
echo 'Browser CI: indexed mana, paid activations and multipliers'
(cd frontend && run_browser_program "browser-mana-abilities.mjs" timeout 180s node tests/browser-mana-abilities.mjs)
echo 'Browser CI: hand activations and owned counter payments'
(cd frontend && run_browser_program "browser-hand-activations.mjs" timeout 120s node tests/browser-hand-activations.mjs)
echo 'Browser CI: legendary channels and owned resolution choices'
(cd frontend && run_browser_program "browser-legendary-channels.mjs" timeout 120s node tests/browser-legendary-channels.mjs)
echo 'Browser CI: private surveil, ordering and payoff triggers'
(cd frontend && run_browser_program "browser-surveil.mjs" timeout 120s node tests/browser-surveil.mjs)
echo 'Browser CI: deliberate effect-authorized casts and declines'
(cd frontend && run_browser_program "browser-effect-casts.mjs" timeout 180s node tests/browser-effect-casts.mjs)
echo 'Browser CI: deliberate spell discard and sacrifice payments'
(cd frontend && run_browser_program "browser-cast-payments.mjs" timeout 180s node tests/browser-cast-payments.mjs)
echo 'Browser CI: kicker payment and conditional branch targets/effects'
(cd frontend && run_browser_program "browser-kicker.mjs" timeout 240s node tests/browser-kicker.mjs)
echo 'Browser CI: permanent kicker entry and owned ETB targets'
(cd frontend && run_browser_program "browser-permanent-kicker.mjs" timeout 180s node tests/browser-permanent-kicker.mjs)
echo 'Browser CI: kicked cast payoffs and first-cast discounts'
(cd frontend && run_browser_program "browser-kicked-cast.mjs" timeout 180s node tests/browser-kicked-cast.mjs)
echo 'Browser CI: nonmana kicker costs and owned discard resolution'
(cd frontend && run_browser_program "browser-nonmana-kicker.mjs" timeout 180s node tests/browser-nonmana-kicker.mjs)
echo 'Browser CI: canonical sacrifice-union kicker and conditional discard goldens'
(cd frontend && run_browser_program "browser-kicker-goldens.mjs" timeout 240s node tests/browser-kicker-goldens.mjs)
echo 'Browser CI: qualified subtype/color payments and actual search/controller/counter effects'
(cd frontend && run_browser_program "browser-qualified-costs.mjs" timeout 180s node tests/browser-qualified-costs.mjs)
echo 'Browser CI: exhaustive resources and announced-X discard payments'
(cd frontend && run_browser_program "browser-variable-costs.mjs" timeout 180s node tests/browser-variable-costs.mjs)
echo 'Browser CI: linked discard, bounded search and actual follow-up draws'
(cd frontend && run_browser_program "browser-linked-discard.mjs" timeout 180s node tests/browser-linked-discard.mjs)
echo 'Browser CI: bounded discard, modal/loyalty actions and per-turn history'
(cd frontend && run_browser_program "browser-discard-history.mjs" timeout 180s node tests/browser-discard-history.mjs)
echo 'Browser CI: simultaneous wheels, effective hand stats and draw continuation'
(cd frontend && run_browser_program "browser-wheel-draw.mjs" timeout 240s node tests/browser-wheel-draw.mjs)
echo 'Browser CI: canonical resource-defined creature stats'
(cd frontend && run_browser_program "browser-characteristic-stats.mjs" timeout 180s node tests/browser-characteristic-stats.mjs)
echo 'Browser CI: canonical conditional static buffs and keyword grants'
(cd frontend && run_browser_program "browser-conditional-static.mjs" timeout 180s node tests/browser-conditional-static.mjs)
echo 'Browser CI: App recovery scenarios'
(cd frontend && run_browser_program "browser-recovery.mjs" timeout 120s node tests/browser-recovery.mjs)
echo 'Browser CI: stopping copied backend'
stop_owned "$backend_pid"
backend_pid=''
start_backend
wait_for_services
echo 'Browser CI: verifying process restart'
(cd frontend && run_browser_program "browser-recovery.mjs" timeout 120s node tests/browser-recovery.mjs --verify-restart)
echo 'Browser CI: match creation recovery'
(cd frontend && run_browser_program "browser-start-recovery.mjs" timeout 180s node tests/browser-start-recovery.mjs)
echo 'Browser CI: sideboard transition'
(cd frontend && run_browser_program "browser-sideboard.mjs" timeout 120s node tests/browser-sideboard.mjs)
echo 'Browser CI: natural AI BO3'
(cd frontend && run_browser_program "browser-live-bo3.mjs" timeout 180s node tests/browser-live-bo3.mjs)
echo 'Browser CI: natural human BO3'
(cd frontend && run_browser_program "browser-human-bo3.mjs" timeout 240s node tests/browser-human-bo3.mjs)
echo 'Browser CI: natural human-vs-human BO3'
(cd frontend && MTG_HUMAN_BO3_OPPONENT=human run_browser_program "browser-human-bo3.mjs" timeout 360s node tests/browser-human-bo3.mjs)

echo 'Browser CI: stopping ordinary harness before independent Officer restart flows'
stop_owned_services
# The independent App fixture uses owned ports/profile and substitutes every API
# response; it must never borrow the ordinary harness's user/session storage.
echo 'Browser CI: interactive support review and pending-start recovery'
(cd frontend && MTG_UI_EVIDENCE="$scratch/interactive-preflight-evidence" \
  CHROMIUM_BINARY="$browser" run_browser_program "browser-interactive-preflight.mjs" timeout 180s node tests/browser-interactive-preflight.mjs)
# Hosted CI explicitly opts into ephemeral evidence; local runs still require NFS.
if [[ "${GITHUB_ACTIONS:-}" == true && -z "${MTG_OFFICER_EVIDENCE_ROOT:-}" ]]; then
  export MTG_OFFICER_EVIDENCE_ROOT="${RUNNER_TEMP:?GitHub CI requires RUNNER_TEMP}/mtg-officer-evidence"
fi
MTG_TEST_PYTHON="$python_bin" MTG_CHROME="$browser" \
  MTG_FRONTEND_DEPS="$(dirname "$frontend_deps")" run_browser_program "run-activated-top-selection.sh" bash frontend/tests/run-activated-top-selection.sh
echo 'Browser CI: canonical Cathar (six controlled cases, both seats; not full transform support)'
if [[ "${GITHUB_ACTIONS:-}" == true && -z "${MTG_CATHAR_ARCHIVE:-}" ]]; then
  export MTG_CATHAR_ARCHIVE="${RUNNER_TEMP:?GitHub CI requires RUNNER_TEMP}/mtg-cathar-evidence"
fi
MTG_TEST_PYTHON="$python_bin" MTG_CHROMIUM="$browser" \
  MTG_FRONTEND_DEPS="$frontend_deps" run_browser_program "browser-cathar.mjs" node frontend/tests/browser-cathar.mjs
# Propagate diagnostic failure only after the unchanged full browser suite.
if [[ "$cors_diagnostic_status" -ne 0 ]]; then
  exit "$cors_diagnostic_status"
fi
