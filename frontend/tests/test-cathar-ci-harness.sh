#!/usr/bin/env bash
set -euo pipefail
tests=$(cd "$(dirname "$0")" && pwd)
node_bin=$(command -v node)
scratch=$(mktemp -d "${TMPDIR:-/tmp}/mtg-cathar-ci-check-XXXXXX")
listener=''
cleanup() {
  local status=$?
  if [[ "$status" != 0 ]]; then tail -n 30 "$scratch"/*.log 2>/dev/null || true; fi
  if [[ -n "$listener" ]]; then kill "$listener" 2>/dev/null || true; wait "$listener" 2>/dev/null || true; fi
  if [[ -f "$scratch/pids" ]]; then
    while read -r pid; do kill -TERM -- "-$pid" 2>/dev/null || true; done < "$scratch/pids"
  fi
  rm -r -- "$scratch"
}
trap cleanup EXIT
mkdir -p "$scratch/repo/frontend/tests" "$scratch/repo/backend/tests" "$scratch/deps/node_modules/vite/bin" "$scratch/bin" "$scratch/runner"
touch "$scratch/repo/backend/tests/__init__.py"
touch "$scratch/deps/node_modules/vite/bin/vite.js" "$scratch/repo/backend/expected.py"
printf 'private sentinel\n' > "$scratch/repo/backend/foreign.sqlite"
ln -s "$scratch/repo/backend/foreign.sqlite" "$scratch/repo/backend/foreign.py"
ln -s "$scratch/deps/node_modules" "$scratch/repo/frontend/node_modules"
touch "$scratch/repo/frontend/tests/ui_fixture_server.py" "$scratch/repo/frontend/tests/ui_v2_fixture_server.py" "$scratch/repo/frontend/tests/browser-cathar.mjs"
cat > "$scratch/repo/frontend/tests/run-activated-top-selection.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
test "$MTG_FRONTEND_DEPS" = "$MTG_CHECK_DEPS"
test "$MTG_OFFICER_EVIDENCE_ROOT" = "$RUNNER_TEMP/mtg-officer-evidence"
test "$PWD" != "$MTG_CHECK_REPO"
for pid in $(cat "$MTG_CHECK_PIDS"); do ! kill -0 -- "-$pid" 2>/dev/null; done
test -z "$(ss -H -ltn '( sport = :10199 or sport = :15173 or sport = :19222 )')"
echo Officer >> "$MTG_CHECK_EVENT_LOG"
setsid "$MTG_CHECK_NODE" -e 'require("http").createServer((q,s)=>s.end()).listen(10237,"127.0.0.1")' &
pid=$!
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' EXIT
echo "$pid" >> "$MTG_CHECK_PIDS"
SH
cat > "$scratch/bin/node" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
test "$1" = frontend/tests/browser-cathar.mjs
test "$MTG_FRONTEND_DEPS" = "$MTG_CHECK_DEPS/node_modules"
test "$MTG_CATHAR_ARCHIVE" = "$RUNNER_TEMP/mtg-cathar-evidence"
test "$(cat "$MTG_CHECK_EVENT_LOG")" = Officer
test "$PWD" = "$GIT_WORK_TREE"
test ! -e .git
test -f backend/expected.py
test ! -e backend/foreign.sqlite
test ! -e backend/foreign.py
test -d frontend/node_modules
test ! -L frontend/node_modules
for pid in $(cat "$MTG_CHECK_PIDS"); do ! kill -0 -- "-$pid" 2>/dev/null; done
test -z "$(ss -H -ltn '( sport = :10199 or sport = :15173 or sport = :19222 or sport = :10237 )')"
echo Cathar >> "$MTG_CHECK_EVENT_LOG"
exit "${MTG_CHECK_CATHAR_EXIT:-0}"
SH
chmod +x "$scratch/bin/node"
# Execute the real preamble/teardown/epilogue, replacing only the lengthy middle
# browser scenarios with three owned listeners. There is no production bypass.
wrapper="$scratch/repo/frontend/tests/run-browser-ci.sh"
sed '/^start_backend()/,$d' "$tests/run-browser-ci.sh" > "$wrapper"
cat >> "$wrapper" <<'SH'
browser=/bin/true
for port in 10199 15173 19222; do
  setsid "$MTG_CHECK_NODE" -e 'require("http").createServer((q,s)=>s.end()).listen(Number(process.argv[1]),"127.0.0.1")' "$port" &
  pid=$!
  echo "$pid" >> "$MTG_CHECK_PIDS"
  case "$port" in 10199) backend_pid=$pid;; 15173) frontend_pid=$pid;; 19222) browser_pid=$pid;; esac
done
for _ in $(seq 1 100); do
  if [[ $(ss -H -ltn '( sport = :10199 or sport = :15173 or sport = :19222 )' | wc -l) == 3 ]]; then break; fi
  sleep .05
done
test $(ss -H -ltn '( sport = :10199 or sport = :15173 or sport = :19222 )' | wc -l) == 3
SH
sed -n '/^echo '\''Browser CI: stopping ordinary harness/,$p' "$tests/run-browser-ci.sh" >> "$wrapper"
git -C "$scratch/repo" init -q
git -C "$scratch/repo" add backend frontend
git -C "$scratch/repo" -c user.name=Test -c user.email=test@localhost commit -qm fixture
export TMPDIR="$scratch" MTG_TEST_PYTHON=/bin/true MTG_CHROMIUM=/bin/true
export MTG_FRONTEND_DEPS="$scratch/deps/node_modules" GITHUB_ACTIONS=true RUNNER_TEMP="$scratch/runner"
export MTG_CHECK_NODE="$node_bin" MTG_CHECK_DEPS="$scratch/deps" MTG_CHECK_REPO="$scratch/repo"
export MTG_CHECK_PIDS="$scratch/pids" MTG_CHECK_EVENT_LOG="$scratch/order"
unset MTG_OFFICER_EVIDENCE_ROOT MTG_CATHAR_ARCHIVE GIT_DIR GIT_WORK_TREE
export PATH="$scratch/bin:$PATH"
if flock "$scratch/mtg-browser-ci.lock" bash "$wrapper" > "$scratch/lock.log" 2>&1; then exit 1; fi
grep -q 'Another browser CI run owns' "$scratch/lock.log"
echo 'PASS shared singleton rejects another harness'
"$node_bin" -e 'require("http").createServer((q,s)=>s.end()).listen(10199,"127.0.0.1")' & listener=$!
for _ in $(seq 1 100); do [[ -n "$(ss -H -ltn '( sport = :10199 )')" ]] && break; sleep .05; done
if bash "$wrapper" > "$scratch/port.log" 2>&1; then exit 1; fi
grep -q 'no foreign service will be stopped' "$scratch/port.log"
kill -0 "$listener"
kill "$listener"; wait "$listener" || true; listener=''
echo 'PASS occupied port fails closed without killing its listener'
bash "$wrapper" > "$scratch/success.log" 2>&1
test "$(cat "$scratch/order")" = $'Officer\nCathar'
grep -q 'six controlled cases, both seats; not full transform support' "$scratch/success.log"
test "$(cat "$scratch/repo/backend/foreign.sqlite")" = 'private sentinel'
test -L "$scratch/repo/backend/foreign.py"
echo 'PASS actual frozen-source CI epilogue invokes Officer then scoped Cathar after owned services stop'
: > "$scratch/pids"; : > "$scratch/order"
if MTG_CHECK_CATHAR_EXIT=23 bash "$wrapper" > "$scratch/failure.log" 2>&1; then exit 1; else test "$?" = 23; fi
grep -q 'Retained browser test artifacts:' "$scratch/failure.log"
retained=$(sed -n 's/Retained browser test artifacts: \([^ ]*\) and .*/\1/p' "$scratch/failure.log")
test -f "$retained/source-revision.txt"
echo 'PASS Cathar failure propagates and frozen diagnostic source is retained'
if GITHUB_ACTIONS=false MTG_CATHAR_ARCHIVE="$scratch/local-evidence" "$node_bin" "$tests/browser-cathar.mjs" > "$scratch/storage.log" 2>&1; then exit 1; fi
grep -q 'Local Cathar evidence requires mounted NFS' "$scratch/storage.log"
test ! -e "$scratch/local-evidence"
echo 'PASS local explicit artifact path still fails closed without NFS'
if MTG_CATHAR_ARCHIVE="$scratch/outside-runner" "$node_bin" "$tests/browser-cathar.mjs" > "$scratch/root.log" 2>&1; then exit 1; fi
grep -q 'Hosted evidence must stay inside RUNNER_TEMP' "$scratch/root.log"
echo 'PASS hosted artifact root cannot escape RUNNER_TEMP'
