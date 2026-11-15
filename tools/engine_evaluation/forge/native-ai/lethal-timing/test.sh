#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?qualified base identity required}; SHADOW=${2:?ff89 or candidate classpath prefix required}
OUT=${3:?fresh absolute local output required}
test "${OUT:0:1}" = / && test ! -e "$OUT"
test "$(sha256sum "$IDENTITY" | cut -d' ' -f1)" = cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0
case $(findmnt -T "$(dirname "$OUT")" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
K=$(jq -r .forge "$IDENTITY"); J=$(jq -r .jdk "$IDENTITY")
CACHE=$(jq -r .cache "$IDENTITY"); Q=$(dirname "$IDENTITY")
(cd "$HERE"; sha256sum -c canonical.sha256 > /dev/null)
for card in "$HERE"/canonical/*.txt; do
    name=$(basename "$card")
    cmp "$card" "$K/forge-gui/res/cardsfolder/${name:0:1}/$name"
done
CP="$SHADOW:$(jq -r '.runtime_classpath|join(":")' "$IDENTITY")"
mkdir -p "$OUT/classes" "$OUT/home" "$OUT/tmp"
sha256sum "$HERE/NativeLethalTimingControls.java" > "$OUT/before.sha256"
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$HERE" -cp "$CP" -d "$OUT/classes" \
    "$HERE/NativeLethalTimingControls.java" > "$OUT/compile.log" 2>&1
BINDS=()
IFS=: read -ra SHADOWS <<< "$SHADOW"
for path in "${SHADOWS[@]}"; do BINDS+=(--ro-bind "$path" "$path"); done
set +e
timeout -k 5s 180 strace --seccomp-bpf -f -qq -e trace=network -o "$OUT/network.private.strace" \
    bwrap --unshare-user --unshare-net --unshare-pid --unshare-ipc --unshare-uts --die-with-parent --new-session \
    --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 --ro-bind /bin /bin --ro-bind /etc /etc \
    --proc /proc --dev /dev --tmpfs /tmp --ro-bind "$CACHE" "$CACHE" --ro-bind "$Q" "$Q" \
    "${BINDS[@]}" --bind "$OUT" "$OUT" --chdir "$K/forge-gui-desktop" --clearenv \
    --setenv PATH "$J/bin:/usr/bin:/bin" --setenv HOME "$OUT/home" --setenv LANG C.UTF-8 \
    "$J/bin/java" -Xmx1500m -XX:ActiveProcessorCount=1 -Djava.awt.headless=true -Duser.home="$OUT/home" \
    -Djava.io.tmpdir="$OUT/tmp" -Dsentry.dsn= "-Xlog:class+load=info:file=$OUT/class-load.log:uptime,level,tags" \
    --add-opens java.base/java.lang=ALL-UNNAMED -cp "$OUT/classes:$CP" \
    forge.evaluation.NativeLethalTimingControls "$OUT" > "$OUT/stdout.private.log" 2> "$OUT/stderr.private.log"
CODE=$?
set -e
printf '%s\n' "$CODE" > "$OUT/exit-code.txt"
sha256sum -c "$OUT/before.sha256" > "$OUT/after.log"
test -f "$OUT/summary.json"
jq '{label,passed,failures,errors,natural_games}' "$OUT/summary.json"
exit "$CODE"
