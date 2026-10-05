#!/usr/bin/env bash
set -euo pipefail
tests=$(cd "$(dirname "$0")" && pwd)
bash -n "$tests/run-activated-top-selection.sh" "$tests/run-browser-ci.sh"
scratch=$(mktemp -d "${TMPDIR:-/tmp}/mtg-officer-wrapper-check-XXXXXX")
listener=''
cleanup() {
  if [[ -n "$listener" ]]; then kill "$listener" 2>/dev/null || true; wait "$listener" 2>/dev/null || true; fi
  rm -r -- "$scratch"
}
trap cleanup EXIT
mkdir -p "$scratch/repo/.git" "$scratch/repo/backend" "$scratch/repo/frontend/tests" "$scratch/deps/node_modules/vite/bin"
cp "$tests/run-activated-top-selection.sh" "$scratch/repo/frontend/tests/"
touch "$scratch/deps/node_modules/vite/bin/vite.js" "$scratch/repo/backend/expected.py"
touch "$scratch/repo/backend/foreign.sqlite" "$scratch/repo/backend/foreign.db"
ln -s "$scratch/repo/backend/foreign.sqlite" "$scratch/repo/backend/foreign.py"
ln -s "$scratch/deps/node_modules" "$scratch/repo/frontend/node_modules"
touch "$scratch/repo/frontend/tests/activated-top-selection-fixture.py"
cat > "$scratch/python" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$1")/../.." && pwd)
test ! -e "$root/.git"
test -f "$root/backend/expected.py"
test ! -e "$root/backend/foreign.sqlite"
test ! -e "$root/backend/foreign.db"
test ! -e "$root/backend/foreign.py"
test ! -e "$root/frontend/node_modules"
printf 'PASS isolated regular source only; no caller git, database or symlink\n'
exit 42
SH
chmod +x "$scratch/python"
export TMPDIR="$scratch" MTG_TEST_PYTHON="$scratch/python" MTG_CHROME=/bin/true
export MTG_FRONTEND_DEPS="$scratch/deps" MTG_OFFICER_EVIDENCE_ROOT="$scratch/evidence"
wrapper="$scratch/repo/frontend/tests/run-activated-top-selection.sh"
if flock "$scratch/mtg-officer-ci.lock" bash "$wrapper" > "$scratch/lock.log" 2>&1; then exit 1; fi
grep -q 'Another Officer harness owns' "$scratch/lock.log"
echo 'PASS concurrent port owner rejected'
node -e 'require("http").createServer((q,s)=>{s.statusCode=404;s.end()}).listen(10237,"127.0.0.1")' &
listener=$!
for _ in $(seq 1 50); do
  if [[ -n "$(ss -H -ltn '( sport = :10237 )')" ]]; then break; fi
  sleep .1
done
if bash "$wrapper" > "$scratch/port.log" 2>&1; then exit 1; fi
grep -q 'must be unused' "$scratch/port.log"
kill "$listener"; wait "$listener" || true; listener=''
echo 'PASS occupied port rejected even when HTTP returns 404'
mkdir "$scratch/bin"
printf '#!/usr/bin/env bash\nprintf "ext4\\n"\n' > "$scratch/bin/findmnt"
chmod +x "$scratch/bin/findmnt"
if env -u MTG_OFFICER_EVIDENCE_ROOT PATH="$scratch/bin:$PATH" bash "$wrapper" > "$scratch/storage.log" 2>&1; then exit 1; fi
grep -q 'requires mounted NFS or an explicit' "$scratch/storage.log"
test ! -d "$scratch/evidence"
echo 'PASS absent NFS fails closed without implicit local evidence'
if bash "$wrapper" > "$scratch/copy.log" 2>&1; then exit 1; fi
grep -q 'PASS isolated regular source only' "$scratch/copy.log"
test -f "$scratch/repo/backend/foreign.sqlite"
test -L "$scratch/repo/backend/foreign.py"
test -d "$scratch/repo/.git"
echo 'PASS normal-repo copy isolation and unchanged caller artifacts'
mkdir -p "$scratch/ci/frontend/tests"
cat > "$scratch/ci/frontend/tests/run-activated-top-selection.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
test "$MTG_OFFICER_EVIDENCE_ROOT" = "$RUNNER_TEMP/mtg-officer-evidence"
test "$MTG_FRONTEND_DEPS" = "$PWD/frontend"
test "$MTG_TEST_PYTHON" = "$EXPECTED_PYTHON"
test "$MTG_CHROME" = /bin/true
for pid in $MTG_CHECK_PIDS; do ! kill -0 "$pid" 2>/dev/null; done
SH
(
  cd "$scratch/ci"
  export GITHUB_ACTIONS=true RUNNER_TEMP="$scratch/ci-runner" EXPECTED_PYTHON="$MTG_TEST_PYTHON"
  unset MTG_OFFICER_EVIDENCE_ROOT
  python_bin="$MTG_TEST_PYTHON" browser=/bin/true
  sleep 60 & backend_pid=$!
  sleep 60 & frontend_pid=$!
  sleep 60 & browser_pid=$!
  export MTG_CHECK_PIDS="$backend_pid $frontend_pid $browser_pid"
  trap 'for pid in "$backend_pid" "$frontend_pid" "$browser_pid"; do if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; fi; done' EXIT
  eval "$(sed -n '/^echo '\''Browser CI: stopping ordinary harness/,$p' "$tests/run-browser-ci.sh")"
)
echo 'PASS actual CI epilogue stops owned processes and forwards explicit hosted evidence'
