#!/usr/bin/env bash
# Acceptance of a committed revision in an owned disposable checkout.
set -euo pipefail
repo=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)
revision=$(git -C "$repo" rev-parse --verify "${1:-HEAD}^{commit}")
python_bin=${MTG_ACCEPT_PYTHON:-python3.12}
command -v "$python_bin" >/dev/null
command -v node >/dev/null
command -v npm >/dev/null
command -v timeout >/dev/null
browser=${MTG_CHROME:-$(command -v google-chrome || command -v chromium || true)}
sandbox_flag=${MTG_BROWSER_NO_SANDBOX:-0}
[[ "$sandbox_flag" = 0 || "$sandbox_flag" = 1 ]] || exit 2
[[ -x "$browser" ]] || { echo 'Set MTG_CHROME to a supported browser executable.' >&2; exit 2; }
work=$(mktemp -d "${TMPDIR:-/tmp}/mtg-clean-acceptance-XXXXXX")
mkdir "$work/source" "$work/logs" "$work/npm-cache" "$work/xdg-cache"
printf '%s\n' "$revision" > "$work/revision.txt"
echo "Acceptance workspace: $work"
# git archive admits committed files only: no local DB, node_modules or caches.
git -C "$repo" archive "$revision" | tar -x -C "$work/source"
cd "$work/source"
git init -q
git add .
git -c user.name='Acceptance checkout' -c user.email=acceptance@localhost commit -qm "Source $revision"
printf '%s\n' "$PWD" > .private
printf '%s\n' "$PWD" > .private-choice-audit-source
# Drop inherited app/test settings without printing their values.
for setting in ${!MTG_@}; do unset "$setting"; done
export MTG_ISOLATED_TEST_ROOT=$PWD PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME="$work/xdg-cache" npm_config_cache="$work/npm-cache"
unset PYTHONPATH PYTHONHOME MTG_FRONTEND_DEPS MTG_TEST_PYTHON
stage() {
  local name=$1; shift
  echo "START $name"
  local code=0
  "$@" >"$work/logs/$name.log" 2>&1 || code=$?
  printf '%s\t%s\n' "$name" "$code" >> "$work/results.tsv"
  if ((code)); then echo "FAIL $name (exit $code); see $work/logs/$name.log" >&2; exit "$code"; fi
  echo "PASS $name"
}
stage platform "$python_bin" .github/scripts/ci_backend_shards.py platform
stage node-version node -e 'if(process.version !== "v24.22.0") throw Error("Requires CI Node v24.22.0")'
stage create-venv "$python_bin" -m venv "$work/venv"
py="$work/venv/bin/python"
stage backend-install timeout 900s "$py" -m pip install --require-hashes --only-binary=:all: --no-cache-dir -r backend/requirements-py312-linux.lock
stage backend-pip-check "$py" -m pip check
stage backend-runtime "$py" .github/scripts/ci_backend_shards.py runtime "$work/runtime.json"
stage frontend-install timeout 900s npm --prefix frontend ci --no-audit --no-fund
stage cold-offline timeout 180s bash -c 'cd backend; exec "$1" -m tests.release_agent.offline_probe' _ "$py"
stage api-contracts timeout 600s bash -c 'cd backend; exec "$1" -m pytest -q -p no:cacheprovider --junitxml="$2/api.xml" tests/test_api_input_contracts.py tests/test_offline_match_hydration.py tests/test_release_card_contracts.py' _ "$py" "$work"
stage runtime-dist timeout 180s "$py" ops/caddy/test_runtime_dist_boundary.py
stage runtime-inventory timeout 180s "$py" ops/caddy/test_runtime_inventory.py
stage runtime-source timeout 180s "$py" ops/caddy/test_runtime_source_artifacts.py
stage frontend-tests timeout 600s env MTG_TEST_PYTHON="$py" npm --prefix frontend test
stage frontend-lint timeout 180s npm --prefix frontend run lint
stage frontend-build timeout 180s npm --prefix frontend run build
# No program selection: run the entire configured cohort, including fallback UI.
# The browser harness takes another fresh source/DB/cache/profile copy and only
# consumes the dependencies freshly installed above.
stage browser timeout 14400s env MTG_TEST_PYTHON="$py" MTG_FRONTEND_DEPS="$PWD/frontend/node_modules" MTG_CHROME="$browser" MTG_BROWSER_NO_SANDBOX="$sandbox_flag" bash frontend/tests/run-browser-ci.sh
printf 'PASS\t%s\n' "$revision" > "$work/ACCEPTED.tsv"
echo "All configured stages passed: $work/results.tsv"
