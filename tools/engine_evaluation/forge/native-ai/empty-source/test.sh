#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Synthetic boundary harness for Forge Team/Card-Forge code; see ../NOTICE.md.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?qualified base identity required}; SHADOW=${2:?candidate shadow required}
OUT=${3:?fresh absolute local output required}
test "${OUT:0:1}" = / && test ! -e "$OUT"
case $(findmnt -T "$(dirname "$OUT")" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
K=$(jq -r .forge "$IDENTITY"); J=$(jq -r .jdk "$IDENTITY")
CACHE=$(jq -r .cache "$IDENTITY"); Q=$(dirname "$IDENTITY")
CP="$SHADOW:$(jq -r '.runtime_classpath|join(":")' "$IDENTITY")"
mkdir -p "$OUT/classes" "$OUT/home" "$OUT/tmp"
sha256sum "$HERE/NativeEmptyKnownSources.java" "$SHADOW/forge/ai/"*.class > "$OUT/before.sha256"
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$HERE" -cp "$CP" -d "$OUT/classes" \
    "$HERE/NativeEmptyKnownSources.java" > "$OUT/compile.log" 2>&1
set +e
timeout -k 5s 180 strace --seccomp-bpf -f -qq -e trace=network -o "$OUT/network.private.strace" \
    bwrap --unshare-net --unshare-pid --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
    --ro-bind /bin /bin --ro-bind /etc /etc --proc /proc --dev /dev --tmpfs /tmp \
    --ro-bind "$CACHE" "$CACHE" --ro-bind "$Q" "$Q" --ro-bind "$SHADOW" "$SHADOW" --bind "$OUT" "$OUT" \
    --chdir "$K/forge-gui-desktop" env -i PATH="$J/bin:/usr/bin:/bin" HOME="$OUT/home" LANG=C.UTF-8 \
    "$J/bin/java" -Xmx1500m -Djava.awt.headless=true -Duser.home="$OUT/home" -Djava.io.tmpdir="$OUT/tmp" \
    -Dsentry.dsn= --add-opens java.base/java.lang=ALL-UNNAMED -cp "$CP:$OUT/classes" \
    forge.evaluation.NativeEmptyKnownSources "$OUT" > "$OUT/stdout.private.log" 2> "$OUT/stderr.private.log"
CODE=$?
set -e
printf '%s\n' "$CODE" > "$OUT/exit-code.txt"
sha256sum -c "$OUT/before.sha256" > "$OUT/after.log"
test -f "$OUT/summary.json"
cat "$OUT/summary.json"
exit "$CODE"
