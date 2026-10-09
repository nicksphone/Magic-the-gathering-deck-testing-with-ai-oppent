#!/usr/bin/env bash
set -euo pipefail

evidence=$(mktemp -d "$RUNNER_TEMP/mtg-backend-evidence-XXXXXX")
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
trap 'printf "stop\n" >&3; wait "$sampler" || true' EXIT

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
exec 3>&-
trap - EXIT
sample_disk >> "$evidence/disk-samples.log" 2>&1 || evidence_status=1
audit_status=0
python "$scratch/.github/scripts/ci_backend_evidence.py" "$evidence" "${statuses[0]}" \
  > "$evidence/coverage.json" || audit_status=$?
if ((statuses[0] != 0)); then exit "${statuses[0]}"; fi
if ((statuses[1] != 0)); then exit "${statuses[1]}"; fi
if ((evidence_status != 0)); then exit "$evidence_status"; fi
exit "$audit_status"
