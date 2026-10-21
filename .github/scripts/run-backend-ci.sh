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
declare -A diagnostic_pins=()
diagnostic_failed=0
diagnostic_until=
diagnostic_remaining=120
monotonic_second() {
  local uptime rest
  read -r uptime rest < /proc/uptime
  printf '%s\n' "${uptime%%.*}"
}
begin_closeout() {
  diagnostic_until=$(($(monotonic_second) + diagnostic_remaining))
}
pin_diagnostic() {
  local row
  local -a fields
  if IFS= read -r row 2>/dev/null < "/proc/$1/stat"; then
    read -r -a fields <<< "${row##*) }"
    if [[ "${fields[1]:-}" == "$$" ]]; then diagnostic_pins[$1]=${fields[19]:-}; fi
  fi
  return 0
}
close_diagnostic() {
  local role=$1 pid=$2 grace=$3 phase attempt limit row target
  local forced=0 finished=0 close_started
  local -a fields phases=(drain TERM KILL)
  diagnostic_status=2
  diagnostic_wait_status=UNKNOWN
  close_started=$(monotonic_second)
  begin_closeout
  # Progress already has an explicit TERM shutdown contract, not a drain.
  if [[ "$role" == progress ]]; then phases=(TERM KILL); fi
  for phase in "${phases[@]}"; do
    limit=$grace
    if [[ "$phase" == TERM ]]; then limit=20; fi
    if [[ "$phase" == KILL ]]; then limit=10; fi
    for ((attempt=0; attempt<limit; attempt++)); do
      if IFS= read -r row 2>/dev/null < "/proc/$pid/stat"; then
        read -r -a fields <<< "${row##*) }"
        if [[ "${fields[1]:-}" != "$$" || -z "${diagnostic_pins[$pid]:-}" ||
              "${fields[19]:-}" != "${diagnostic_pins[$pid]}" ]]; then break 2; fi
        if [[ "${fields[0]}" == Z ]]; then finished=1; break 2; fi
      elif ! kill -0 "$pid" 2>/dev/null; then
        finished=1; break 2
      else
        break 2  # Unknown identity: no signal and no potentially blocking wait.
      fi
      if (($(monotonic_second) >= diagnostic_until)); then break 2; fi
      if [[ "$phase" != drain && "$attempt" == 0 ]]; then
        target=$pid
        if [[ "$role" == progress || ( "$role" == pytest && "$shard_role" != legacy ) ]]; then
          if [[ "${fields[2]}" != "$pid" || "${fields[3]}" != "$pid" ]]; then break 2; fi
          target=-$pid  # Only this pinned, setsid-owned progress/pytest group.
        fi
        if [[ "$role" != progress || "$phase" == KILL ]]; then forced=1; fi
        kill -"$phase" -- "$target" 2>/dev/null || true
      fi
      sleep 0.1
    done
  done
  if ((finished)); then
    if wait "$pid"; then diagnostic_wait_status=0; else diagnostic_wait_status=$?; fi
    diagnostic_status=$diagnostic_wait_status
  fi
  if ((forced || !finished)); then diagnostic_failed=1; diagnostic_status=2; fi
  if ((diagnostic_status != 0)); then diagnostic_failed=1; fi
  diagnostic_remaining=$((diagnostic_remaining - $(monotonic_second) + close_started))
  if ((diagnostic_remaining < 0)); then diagnostic_remaining=0; fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$role" "$pid" "$finished" "$forced" "$diagnostic_wait_status" \
    >> "$evidence/diagnostic-closeout.tsv" || { diagnostic_failed=1; diagnostic_status=2; }
}
# Open before private decoding; raw streams never reach the public sink.
storage_python=$(command -v python3 5>&-)
storage_script="$PWD/.github/scripts/ci_backend_storage.py"
exec 4> >(/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "$storage_python" -I -B \
  "$storage_script" stream "$evidence" runner.log 5>&- 2>/dev/null)
logger_pid=$!
pin_diagnostic "$logger_pid"
if ! kill -0 "$logger_pid" 2>/dev/null; then
  printf 'CI_BACKEND_EVIDENCE_SETUP_ERROR\n' >&2
  exit 1
fi
exec 1>&4 2>&4 4>&-
shard_role=${MTG_CI_SHARD_ROLE:-legacy}
shard_helper="$PWD/.github/scripts/ci_backend_shards.py"
work_run() {
  if [[ "$shard_role" == legacy ]]; then "$@"; return; fi
  local remaining
  remaining=$(python "$shard_helper" remaining) || return
  timeout --signal=TERM --kill-after=15s "${remaining}s" "$@"
}
if [[ "$shard_role" != legacy && "$shard_role" != reference && "$shard_role" != worker ]]; then
  exit 2
fi
progress_pid=
sampler=
pressure_pid=
pytest_pid=
pytest_started=0
sink_pid=
watcher_pid=
pytest_status=
evidence_status=
audit_status=
pressure_status=
sink_status=
watcher_status=
work_exit_stage=EARLY_OR_UNKNOWN
group_after_wait_quiet=
group_final_quiet=
write_runner_closeout() {
  local value stage=$work_exit_stage complete=true failed changed=false
  local path="$evidence/runner-closeout.json"
  local -a codes=() groups=()
  # Fixed scalar operands only; no shell output, PID, argv or raw log is serialized.
  for value in "$closeout_entry_status" "$status" "${pytest_status:-}" \
      "${evidence_status:-}" "${audit_status:-}" "${pressure_status:-}" \
      "${sink_status:-}" "${watcher_status:-}"; do
    if [[ "$value" =~ ^(0|[1-9][0-9]{0,2})$ ]] && ((value <= 255)); then
      codes+=("$value")
    else
      codes+=(null)
      complete=false
    fi
  done
  for value in "$group_after_wait_quiet" "$group_final_quiet"; do
    case "$value" in
      true|false) groups+=("$value") ;;
      *) groups+=(null); complete=false ;;
    esac
  done
  case "$stage" in
    EARLY_OR_UNKNOWN|PYTEST|SINK|CONTROL|EVIDENCE|AUDIT) ;;
    *) stage=EARLY_OR_UNKNOWN ;;
  esac
  case "$diagnostic_failed" in 0) failed=false ;; 1) failed=true ;; *) return 1 ;; esac
  if ((closeout_entry_status != status)); then changed=true; fi
  [[ ! -e "$path" && ! -L "$path" ]] || return 1
  (umask 077; set -o noclobber
   printf '{"schema_version":1,"work_exit_stage":"%s","entry_exit_code":%s,"final_exit_code":%s,"pytest_exit_code":%s,"evidence_exit_code":%s,"audit_exit_code":%s,"pressure_exit_code":%s,"sink_exit_code":%s,"watcher_exit_code":%s,"diagnostic_failed":%s,"group_after_wait_quiet":%s,"group_final_quiet":%s,"trap_changed_exit":%s,"closeout_complete":%s}\n' \
     "$stage" "${codes[@]}" "$failed" "${groups[@]}" "$changed" "$complete" > "$path")
}
cleanup_owned() {
  status=$?
  closeout_entry_status=$status
  trap - EXIT
  begin_closeout
  if [[ -n "$pytest_pid" ]]; then
    # Only the actual registered pytest session may receive deadline signals.
    # No name/discovered-PID/group fallback on an unknown registration.
    if [[ "$shard_role" != legacy ]]; then
      timeout --signal=TERM --kill-after=2s 20s python "$shard_helper" stop-pytest \
        "$evidence/deadline.json.identity.json" || diagnostic_failed=1
      close_diagnostic pytest "$pytest_pid" 0
    else
      if [[ -n "${diagnostic_pins[$pytest_pid]:-}" ]]; then
        close_diagnostic pytest "$pytest_pid" 0
      else
        diagnostic_failed=1
      fi
    fi
    # The bounded closer waits only on an observed zombie/absent owned child.
    if [[ "$diagnostic_wait_status" != UNKNOWN ]]; then
      pytest_status=$diagnostic_wait_status
      printf '%s\n' "$pytest_status" > "$evidence/pytest-exit-code.txt" || diagnostic_failed=1
    else
      diagnostic_failed=1
    fi
  fi
  if [[ -n "$watcher_pid" ]]; then
    close_diagnostic watcher "$watcher_pid" 20
    watcher_status=$diagnostic_status
  fi
  if [[ -n "$progress_pid" ]]; then
    # A blocked public sink can stall only this isolated group, never pytest.
    close_diagnostic progress "$progress_pid" 20
    if ((diagnostic_status != 0)); then diagnostic_failed=1; fi
  fi
  if [[ -n "$sampler" ]]; then
    printf 'stop\n' >&3 || true
    close_diagnostic sampler "$sampler" 50
  fi
  if [[ -n "$pressure_pid" ]]; then
    close_diagnostic pressure "$pressure_pid" 50
    pressure_status=$diagnostic_status
  fi
  if [[ -n "$sink_pid" ]]; then
    close_diagnostic sink "$sink_pid" 50
    sink_status=$diagnostic_status
  fi
  if [[ "$shard_role" != legacy && "$pytest_started" == 1 ]]; then
    # Retain registration after leader wait; absence of its group is separate.
    # This presence-only query never signals a surviving/reused/unbound group.
    timeout --signal=TERM --kill-after=2s 5s python "$shard_helper" group-quiet \
      "$evidence/deadline.json.identity.json" "$evidence/group-quiet-final.json" \
      && group_final_quiet=true || { group_final_quiet=false; diagnostic_failed=1; }
  fi
  # Release only this freshly pinned reserve, never failed/source scratch.
  timeout --signal=TERM --kill-after=2s 10s /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "$storage_python" -I -B \
    "$storage_script" release "$evidence" </dev/null || true
  exec 1>/dev/null 2>/dev/null
  close_diagnostic logger "$logger_pid" 20
  if ((status == 0 && (diagnostic_status != 0 || diagnostic_failed != 0))); then status=2; fi
  # Optional evidence failure cannot replace the already determined runner exit.
  write_runner_closeout || true
  exit "$status"
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
  pin_diagnostic "$progress_pid"
  printf '%s\n' "$progress_pid" > "$evidence/progress-owner.pid"
fi
exec 5>&-
printf 'evidence=%s\n' "$evidence" >> "$GITHUB_OUTPUT"
work=$(mktemp -d "$RUNNER_TEMP/mtg-backend-work-XXXXXX")
scratch="$work/source"
mkdir -p "$scratch" "$work/tmp" "$work/pytest-tmp" "$work/http"
archive="$work/source.tar"
work_run git archive HEAD > "$archive"
archive_sha256=$(sha256sum "$archive" | cut -d ' ' -f 1)
printf '%s  %s\n' "$archive_sha256" "$archive" | sha256sum --check --status
work_run tar -xf "$archive" -C "$scratch"
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
if [[ "$shard_role" != legacy ]]; then
  work_run python "$shard_helper" runtime "$evidence/runtime-identity.json"
  work_run python "$shard_helper" binding "$PWD" "$archive_sha256" "$evidence/binding.json"
fi

export MTG_ISOLATED_TEST_ROOT="$scratch" MTG_CI_EVIDENCE="$evidence"
export MTG_RELEASE_MEDIA_ARCHIVE="$archive" MTG_RELEASE_MEDIA_ARCHIVE_SHA256="$archive_sha256"
# The protected consumer must create this fresh root itself, not receive an existing slot.
export MTG_EXPORT_RECOVERY_EVIDENCE_ROOT=$(mktemp --dry-run /tmp/mtg-export-recovery-CLI-XXXXXXXXXXXXXXXX)
test ! -e "$MTG_EXPORT_RECOVERY_EVIDENCE_ROOT" && test ! -L "$MTG_EXPORT_RECOVERY_EVIDENCE_ROOT"
export MTG_EXPORT_RECOVERY_SQL_SLOT=github-actions-isolated
export TMPDIR="$work/tmp" PYTEST_DEBUG_TEMPROOT="$work/pytest-tmp"
export MTG_LAND_CHOICE_STAGE_EVIDENCE="$work/http"
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "$storage_python" -I -B \
  "$storage_script" reserve "$evidence" </dev/null
work_run python "$scratch/.github/scripts/prepare-backend-private-inputs.py" "$work/private-inputs"
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
pin_diagnostic "$sampler"

cd "$scratch/backend"
export PYTHONPATH="$scratch/.github/scripts:$scratch/backend"
# Only this fresh serial job workspace may reclaim fully passed startup snapshots.
export MTG_CI_PASSED_SNAPSHOT_CLEANUP=1
export MTG_CI_STORAGE_GUARD=1
export PYTEST_PLUGINS="${PYTEST_PLUGINS:+$PYTEST_PLUGINS,}ci_backend_storage"
pytest_args=(-m pytest -vv --tb=short -ra -p no:cacheprovider -p ci_backend_evidence -p ci_backend_snapshot_cleanup -o tmp_path_retention_policy=failed)
if [[ "$shard_role" != legacy ]]; then
  pytest_args+=(-p ci_backend_shards)
  if [[ "$shard_role" == reference ]]; then
    pytest_args+=(--collect-only)
  else
    # A failed generator cannot turn an empty argv into a full/subset rerun.
    work_run python "$shard_helper" validate-bundle "$MTG_CI_REFERENCE_DIR" "$evidence/binding.json"
    work_run python "$shard_helper" worker-argv "$MTG_CI_REFERENCE_DIR/plan.json" \
      "$evidence/binding.json" "$scratch" "$MTG_CI_SHARD" > "$work/assigned-argv"
    mapfile -d '' -t assigned_argv < "$work/assigned-argv"
    ((${#assigned_argv[@]} > 0)) || exit 2
    pytest_args+=("${assigned_argv[@]}")
  fi
  # Fail before spawning pytest if setup has exhausted the original work budget.
  python "$shard_helper" remaining >/dev/null
fi
mkfifo "$work/pytest-output"
set +e
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "$storage_python" -I -B \
  "$storage_script" stream "$evidence" pytest.log <"$work/pytest-output" 3>&- &
sink_pid=$!
pin_diagnostic "$sink_pid"
if [[ "$shard_role" == legacy ]]; then
  /usr/bin/env --default-signal=INT python "${pytest_args[@]}" \
    3>&- >"$work/pytest-output" 2>&1 &
else
  /usr/bin/setsid /usr/bin/env --default-signal=INT python "${pytest_args[@]}" \
    3>&- >"$work/pytest-output" 2>&1 &
fi
pytest_pid=$!
pytest_started=1
pin_diagnostic "$pytest_pid"
if [[ "$shard_role" != legacy ]]; then
  python "$shard_helper" watch "$pytest_pid" "$$" "$MTG_CI_WORK_DEADLINE" \
    "$evidence/deadline.json" </dev/null 3>&- &
  watcher_pid=$!
  pin_diagnostic "$watcher_pid"
fi
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "$storage_python" -I -B \
  "$storage_script" watch "$evidence" "$pytest_pid" </dev/null 3>&- &
pressure_pid=$!
pin_diagnostic "$pressure_pid"
evidence_status=0
if [[ -n "$watcher_pid" ]]; then
  # A failed watcher must not leave an indefinitely waiting parent. wait -n
  # returns a genuine status for whichever of these two owned children ends.
  first_wait=
  wait -n -p first_wait "$pytest_pid" "$watcher_pid"; first_status=$?
  if [[ "$first_wait" == "$pytest_pid" ]]; then
    pytest_status=$first_status
  else
    watcher_status=$first_status
    if ((first_status != 0)); then
      evidence_status=2
      close_diagnostic pytest "$pytest_pid" 0
      if [[ "$diagnostic_wait_status" == UNKNOWN ]]; then exit 2; fi
      pytest_status=$diagnostic_wait_status
    else
      # The watcher returns zero only after the exact registered leader is gone.
      wait "$pytest_pid"; pytest_status=$?
    fi
    watcher_pid=
  fi
else
  wait "$pytest_pid"; pytest_status=$?
fi
pytest_pid=
if [[ "$shard_role" != legacy ]]; then
  # Work completion itself must precede the original deadline, even if the
  # leader exited between the watcher's last probe and its deadline check.
  python "$shard_helper" remaining >/dev/null || evidence_status=2
fi
# Preserve the genuine wait result before any diagnostic can block or fail.
printf '%s\n' "$pytest_status" > "$evidence/pytest-exit-code.txt" || evidence_status=1
begin_closeout
if [[ -n "$watcher_pid" ]]; then
  close_diagnostic watcher "$watcher_pid" 20
  watcher_status=$diagnostic_status
  watcher_pid=
  if ((watcher_status != 0)); then evidence_status=2; fi
fi
if [[ "$shard_role" != legacy ]]; then
  timeout --signal=TERM --kill-after=2s 5s python "$shard_helper" group-quiet \
    "$evidence/deadline.json.identity.json" "$evidence/group-quiet-after-wait.json" \
    && group_after_wait_quiet=true || { group_after_wait_quiet=false; evidence_status=2; }
fi
close_diagnostic pressure "$pressure_pid" 50
pressure_status=$diagnostic_status
pressure_pid=
close_diagnostic sink "$sink_pid" 50
sink_status=$diagnostic_status
sink_wait_status=$diagnostic_wait_status
sink_pid=
statuses=("$pytest_status" "$sink_status")
set -e
printf '%s\n' "$sink_wait_status" > "$evidence/tee-exit-code.txt" || evidence_status=1
printf 'stop\n' >&3
close_diagnostic sampler "$sampler" 50
if ((diagnostic_status != 0)); then evidence_status=2; fi
sampler=
exec 3>&-
sample_disk >> "$evidence/disk-samples.log" 2>&1 || evidence_status=1
audit_status=0
audit_until=$(($(monotonic_second) + 120))
if [[ "$shard_role" == reference ]]; then
  # collect-only has no execution phases and never receives a phase-pass audit.
  timeout --signal=TERM --kill-after=2s 120s python "$shard_helper" reference \
    "$GITHUB_WORKSPACE" "$evidence" "$evidence/binding.json" "$evidence/runtime-identity.json" \
    "$evidence/plan.json" || audit_status=$?
else
  timeout --signal=TERM --kill-after=2s 120s python "$scratch/.github/scripts/ci_backend_evidence.py" \
    "$evidence" "${statuses[0]}" > "$evidence/coverage.json" || audit_status=$?
  if [[ "$shard_role" == worker && "$audit_status" == 0 ]]; then
    audit_remaining=$((audit_until - $(monotonic_second)))
    if ((audit_remaining <= 0)); then
      audit_status=2
    else
      timeout --signal=TERM --kill-after=2s "${audit_remaining}s" python "$shard_helper" worker-context \
        "$MTG_CI_REFERENCE_DIR/plan.json" "$evidence/shard-observation.json" "$MTG_CI_SHARD" || audit_status=$?
    fi
  fi
fi
work_exit_stage=PYTEST
if ((statuses[0] != 0)); then exit "${statuses[0]}"; fi
work_exit_stage=SINK
if ((statuses[1] != 0)); then exit "${statuses[1]}"; fi
work_exit_stage=CONTROL
if ((pressure_status != 0 || diagnostic_failed != 0)); then exit 2; fi
work_exit_stage=EVIDENCE
if ((evidence_status != 0)); then exit "$evidence_status"; fi
work_exit_stage=AUDIT
exit "$audit_status"
