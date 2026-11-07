#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Builds our adapter and the separately licensed Forge native input patches.
# The Forge Team/Card-Forge engine and dependencies must already be built.
set -euo pipefail
FORGE=$(cd -- "$(dirname -- "$0")/.." && pwd)
REPO=$(cd -- "$FORGE/../../.." && pwd)
[[ $# == 1 && "$1" == /* ]] || { echo 'usage: FORGE_CP=... [JAVAC=...] bash build.sh /absolute/fresh/output' >&2; exit 2; }
CP=${FORGE_CP:?Set FORGE_CP to the pinned Forge compiled dependency classpath}
CP=${CP%:}
case ":$CP:" in *::* ) echo 'Classpath must not contain an empty entry' >&2; exit 2;; esac
OUT=$(realpath -m -- "$1")
case "$OUT/" in "$REPO/"*) echo 'Output must be outside the repository' >&2; exit 2;; esac
[[ ! -e "$OUT" && ! -L "$OUT" ]] || { echo 'Output must be fresh' >&2; exit 2; }
mapfile -t SOURCES < "$FORGE/stdio/build.sources"
[[ ${#SOURCES[@]} == 23 ]]
for i in "${!SOURCES[@]}"; do
    [[ "${SOURCES[i]}" != /* && "${SOURCES[i]}" != *..* ]]
    SOURCES[i]="$FORGE/${SOURCES[i]}"
    [[ -f "${SOURCES[i]}" ]]
done
mkdir -p -- "$OUT"
exec "${JAVAC:-javac}" -J-Xmx2g -J-XX:ActiveProcessorCount=1 \
    --release 17 -proc:none -implicit:none -sourcepath '' \
    -cp "$CP" -d "$OUT" "${SOURCES[@]}"
