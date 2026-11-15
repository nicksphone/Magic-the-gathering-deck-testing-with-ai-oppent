#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Owned single-source shadow build of Forge Team/Card-Forge work. See NOTICE.md.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?BUILD-IDENTITY.json required}
OUT=${2:?new absolute local output directory required}
test "${OUT:0:1}" = / && test ! -e "$OUT"
case $(findmnt -T "$(dirname "$OUT")" -n -o FSTYPE | tail -1) in nfs*|cifs) echo 'Local build required' >&2; exit 2;; esac
K=$(jq -r .forge "$IDENTITY")
J=$(jq -r .jdk "$IDENTITY")
CP=$(jq -r '.runtime_classpath | join(":")' "$IDENTITY")
test "$(basename "$K")" = forge-61e9442c433711a82258daca3236f936a1d6f70e
(cd "$K"; sha256sum --check "$HERE/ComputerUtil.preimage.sha256")
mkdir -p "$OUT/source/forge-ai/src/main/java/forge/ai" "$OUT/shadow"
SOURCE=forge-ai/src/main/java/forge/ai/ComputerUtil.java
cp "$K/$SOURCE" "$OUT/source/$SOURCE"
patch --batch --forward --fuzz=0 -p1 -d "$OUT/source" < "$HERE/hasAFogEffect-actor-knowledge.patch" > "$OUT/patch.log"
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$OUT/source" -cp "$CP" \
    -d "$OUT/shadow" "$OUT/source/$SOURCE" > "$OUT/compile.stdout.log" 2> "$OUT/compile.stderr.log"
mapfile -t EMITTED < <(cd "$OUT/shadow"; find . -type f | sort)
test "${#EMITTED[@]}" = 1 && test "${EMITTED[0]}" = ./forge/ai/ComputerUtil.class
sha256sum "$OUT/source/$SOURCE" "$OUT/shadow/forge/ai/ComputerUtil.class" > "$OUT/candidate.sha256"
sha256sum "$HERE/hasAFogEffect-actor-knowledge.patch" "$HERE/ComputerUtil.preimage.sha256" "$HERE/build.sh" > "$OUT/build-inputs.sha256"
"$J/bin/javap" -c -p "$OUT/shadow/forge/ai/ComputerUtil.class" > "$OUT/ComputerUtil.javap.txt"
(cd "$K"; sha256sum --check "$HERE/ComputerUtil.preimage.sha256") > "$OUT/upstream.after.log"
