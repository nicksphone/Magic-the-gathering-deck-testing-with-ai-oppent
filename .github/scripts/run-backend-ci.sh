#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${RUNNER_TEMP:-}" || -z "${GITHUB_OUTPUT:-}" ]]; then
  printf 'CI_BACKEND_EVIDENCE_SETUP_ERROR\n' >&2
  exit 1
fi
evidence=$(mktemp -d "$RUNNER_TEMP/mtg-backend-evidence-XXXXXX" 5>&- 2>/dev/null) || {
  printf 'CI_BACKEND_EVIDENCE_SETUP_ERROR\n' >&2
  exit 1
}
# Open before private decoding; even shell/observer errors stay runner-local.
if ! { exec 4>"$evidence/runner.log"; } 2>/dev/null; then
  printf 'CI_BACKEND_EVIDENCE_SETUP_ERROR\n' >&2
  exit 1
fi
exec 1>&4 2>&4 4>&-
progress_pid=
sampler=
cleanup_owned() {
  status=$?
  trap - EXIT
  if [[ -n "$progress_pid" ]]; then
    # A blocked public sink can stall only this isolated group, never pytest.
    kill -TERM -- "-$progress_pid" 2>/dev/null || true
    for ((attempt=0; attempt<20; attempt++)); do
      if ! kill -0 "$progress_pid" 2>/dev/null; then break; fi
      sleep 0.1
    done
    kill -KILL -- "-$progress_pid" 2>/dev/null || true
    wait "$progress_pid" || true
  fi
  if [[ -n "$sampler" ]]; then
    printf 'stop\n' >&3 || true
    wait "$sampler" || true
  fi
  return "$status"
}
trap cleanup_owned EXIT
if [[ "${MTG_CI_PROGRESS:-}" == 1 ]]; then
  # No inherited private environment, backend PYTHONPATH, or private preparation.
  progress_python=$(command -v python 5>&-)
  /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "$progress_python" -I -B - \
    "$PWD/.github/scripts/ci_backend_progress.py" "$evidence" 5>&- <<'PY'
from pathlib import Path
import sys

for value in sys.argv[1:]:
    path = Path(value).absolute()
    if any(component.is_symlink() for component in (*path.parents, path)):
        raise SystemExit('CI_PROGRESS_PATH_REJECTED')
PY
  /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/setsid "$progress_python" -I -B \
    "$PWD/.github/scripts/ci_backend_progress.py" "$evidence" "$PWD" </dev/null 1>&5 5>&- &
  progress_pid=$!
  printf '%s\n' "$progress_pid" > "$evidence/progress-owner.pid"
fi
exec 5>&-
printf 'evidence=%s\n' "$evidence" >> "$GITHUB_OUTPUT"
work=$(mktemp -d "$RUNNER_TEMP/mtg-backend-work-XXXXXX")
scratch="$work/source"
mkdir -p "$scratch" "$work/tmp" "$work/pytest-tmp" "$work/http"
archive="$work/source.tar"
git archive HEAD > "$archive"
archive_sha256=$(sha256sum "$archive" | cut -d ' ' -f 1)
printf '%s  %s\n' "$archive_sha256" "$archive" | sha256sum --check --status
tar -xf "$archive" -C "$scratch"
printf '%s' "$scratch" > "$scratch/.private-choice-audit-source"
printf '%s' "$scratch" > "$scratch/.private"
git rev-parse HEAD > "$evidence/source-head.txt"
python --version > "$evidence/python-version.txt"
python - <<'PY' > "$evidence/installed-packages.json"
from importlib.metadata import distributions
import json

packages = [{'name': package.metadata.get('Name'), 'version': package.version}
            for package in distributions()]
print(json.dumps(sorted(packages, key=lambda package: (package['name'] or '').lower())))
PY
printf 'source=%s\nwork=%s\nevidence=%s\n' "$scratch" "$work" "$evidence" > "$evidence/owned-paths.txt"

export MTG_ISOLATED_TEST_ROOT="$scratch" MTG_CI_EVIDENCE="$evidence"
export MTG_RELEASE_MEDIA_ARCHIVE="$archive" MTG_RELEASE_MEDIA_ARCHIVE_SHA256="$archive_sha256"
# The protected consumer must create this fresh root itself, not receive an existing slot.
export MTG_EXPORT_RECOVERY_EVIDENCE_ROOT=$(mktemp --dry-run /tmp/mtg-export-recovery-CLI-XXXXXXXXXXXXXXXX)
test ! -e "$MTG_EXPORT_RECOVERY_EVIDENCE_ROOT" && test ! -L "$MTG_EXPORT_RECOVERY_EVIDENCE_ROOT"
export MTG_EXPORT_RECOVERY_SQL_SLOT=github-actions-isolated
export TMPDIR="$work/tmp" PYTEST_DEBUG_TEMPROOT="$work/pytest-tmp"
export MTG_LAND_CHOICE_STAGE_EVIDENCE="$work/http"
python "$scratch/.github/scripts/prepare-backend-private-inputs.py" "$work/private-inputs"
export MTG_HEAT_WITNESS="$work/private-inputs/sealed-self-removal-witness.json"
for number in {01..13}; do unset "MTG_HEAT_WITNESS_$number"; done
for variable in MTG_PAID_AI_EVIDENCE MTG_PAID_VIEW_EVIDENCE \
    MTG_HUMAN_BO3_EVIDENCE MTG_BOUNDARY_AUDIT_EVIDENCE \
    MTG_BLOCK_AUDIT_EVIDENCE MTG_ATTACK_WITNESS_EVIDENCE \
    MTG_GY_INVENTORY_EVIDENCE MTG_CAUSAL_GY_EVIDENCE \
    MTG_GY_SELF_EVIDENCE MTG_PULL_EVIDENCE MTG_FROG_HTTP_EVIDENCE; do
  directory="$evidence/fixtures/$variable"
  mkdir -p "$directory"
  export "$variable=$directory"
done
mkdir -p "$work/private-heat-output"
export MTG_HEAT_REPORT="$work/private-heat-output/report.json"

sample_disk() {
  printf '\nUTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  timeout 5s df -B1 "$work" "$evidence" || printf 'df-bytes failed/status=%s\n' "$?"
  timeout 5s df -i "$work" "$evidence" || printf 'df-inodes failed/status=%s\n' "$?"
  timeout 10s du -sx -B1 "$work" "$scratch" "$work/tmp" "$work/pytest-tmp" "$work/http" "$evidence" \
    || printf 'du-bytes incomplete/status=%s\n' "$?"
}
sample_disk >> "$evidence/disk-samples.log" 2>&1
# Pipe control does not require another disk write when test storage is full.
mkfifo "$work/sampling-control"
exec 3<>"$work/sampling-control"
(
  for ((sample=0; sample<360; sample++)); do
    if read -r -t 60 -u 3; then exit 0; fi
    sample_disk
  done
) >> "$evidence/disk-samples.log" 2>&1 &
sampler=$!

cd "$scratch/backend"
export PYTHONPATH="$scratch/.github/scripts:$scratch/backend"
set +e
python -m pytest -vv --tb=short -ra -p no:cacheprovider -p ci_backend_evidence \
  3>&- 2>&1 | tee "$evidence/pytest.log" 3>&-
statuses=("${PIPESTATUS[@]}")
set -e
evidence_status=0
printf '%s\n' "${statuses[0]}" > "$evidence/pytest-exit-code.txt" || evidence_status=1
printf '%s\n' "${statuses[1]}" > "$evidence/tee-exit-code.txt" || evidence_status=1
printf 'stop\n' >&3
wait "$sampler" || evidence_status=1
sampler=
exec 3>&-
sample_disk >> "$evidence/disk-samples.log" 2>&1 || evidence_status=1
audit_status=0
python "$scratch/.github/scripts/ci_backend_evidence.py" "$evidence" "${statuses[0]}" \
  > "$evidence/coverage.json" || audit_status=$?
if ((statuses[0] != 0)); then exit "${statuses[0]}"; fi
if ((statuses[1] != 0)); then exit "${statuses[1]}"; fi
if ((evidence_status != 0)); then exit "$evidence_status"; fi
exit "$audit_status"
