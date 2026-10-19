#!/usr/bin/env bash

_mtg_browser_program_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

run_browser_program() {
  (($# >= 2)) || return 2
  local program=$1
  shift
  [[ "$program" =~ ^[a-z0-9][a-z0-9._-]{0,79}$ \
    && -f "$_mtg_browser_program_directory/$program" \
    && ! -L "$_mtg_browser_program_directory/$program" ]] || return 2
  local status=0
  "$@" || status=$?
  if ((status)); then
    # No command arguments, environment values, error text or game data are copied.
    printf '\n::error title=Browser program failure::{"schema":1,"program":"%s","exit_code":%d}\n' \
      "$program" "$status" >&2 || :
  fi
  return "$status"
}

report_browser_bootstrap_failure() {
  (($# == 2)) || return 2
  local status=$1 line=$2
  [[ "$status" =~ ^[1-9][0-9]{0,2}$ && "$line" =~ ^[1-9][0-9]{0,5}$ ]] || return 2
  ((status <= 255)) || return 2
  printf '\n::error title=Browser bootstrap failure::{"schema":1,"program":"bootstrap","source_line":%d,"exit_code":%d}\n' \
    "$line" "$status" >&2
}
