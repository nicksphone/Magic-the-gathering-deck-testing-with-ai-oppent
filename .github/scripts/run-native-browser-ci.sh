#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

case "${MTG_BROWSER_VENDOR:-}:${MTG_CHROME:-}" in
  chrome:/opt/google/chrome/chrome|brave:/opt/brave.com/brave/brave) ;;
  *) echo 'Native CI requires an exact Chrome or Brave executable.' >&2; exit 2 ;;
esac
if [[ "$EUID" == 0 || "${MTG_BROWSER_NO_SANDBOX:-}" != 0 \
  || ! "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ || ! "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]+$ ]]; then
  echo 'Native CI requires nonroot, sandbox mode 0 and numeric run identity.' >&2
  exit 2
fi
test -d "${MTG_NATIVE_REPORT_DIR:?}"
unit="mtg-native-$MTG_BROWSER_VENDOR-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT.service"
cleanup() {
  status=$?
  trap - EXIT
  sudo systemctl stop "$unit" >/dev/null 2>&1 || true
  cgroup="/sys/fs/cgroup/system.slice/$unit"
  empty=true
  if [[ -e "$cgroup" ]] && ! grep -qx 'populated 0' "$cgroup/cgroup.events"; then
    empty=false
    status=1
  fi
  node --input-type=module - "$MTG_NATIVE_REPORT_DIR/lifecycle.json" "$status" "$empty" <<'NODE'
import { writeFileSync } from 'node:fs';
const [destination, status, empty] = process.argv.slice(2);
writeFileSync(destination, JSON.stringify({schema: 1, exit_status: Number(status), cgroup_empty: empty === 'true'}) + '\n', {flag: 'wx'});
NODE
  python3 .github/scripts/ci_native_browser_notice.py "$MTG_NATIVE_REPORT_DIR" "$MTG_BROWSER_VENDOR" || :
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# A service cgroup contains even browser crash handlers that create new sessions.
# No host install, sysctl, AppArmor or sandbox workaround is performed here.
sudo systemd-run --quiet --unit="$unit" --uid="$(id -u)" --gid="$(id -g)" \
  --working-directory="$PWD" --wait --pipe --collect --expand-environment=no \
  --property=Type=exec --property=KillMode=control-group \
  --property=TimeoutStopSec=15s --property=RuntimeMaxSec=2700s \
  --setenv="PATH=$PATH" --setenv="HOME=$HOME" \
  --setenv="GITHUB_SHA=$(git rev-parse HEAD)" \
  --setenv=GITHUB_ACTIONS=true --setenv="RUNNER_TEMP=${RUNNER_TEMP:?}" \
  --setenv="MTG_BROWSER_VENDOR=$MTG_BROWSER_VENDOR" --setenv="MTG_CHROME=$MTG_CHROME" \
  --setenv=MTG_BROWSER_NO_SANDBOX=0 --setenv="MTG_NATIVE_REPORT_DIR=$MTG_NATIVE_REPORT_DIR" \
  /bin/bash -euo pipefail -c '
    node frontend/tests/browser-vendor-preflight.mjs --report "$MTG_NATIVE_REPORT_DIR/preflight.json"
    bash frontend/tests/run-browser-ci.sh
  '
