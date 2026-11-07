#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Original isolated test caller of Forge Team/Card-Forge native code. See NOTICE.md.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?absolute base BUILD-IDENTITY.json required}
SHADOW=${2:?absolute shadow directory or NONE required}
OUT=${3:?new absolute local test directory required}
shift 3
test "${IDENTITY:0:1}" = / && test "${OUT:0:1}" = / && test ! -e "$OUT"
case $(findmnt -T "$(dirname "$OUT")" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
K=$(jq -r .forge "$IDENTITY"); J=$(jq -r .jdk "$IDENTITY")
CACHE=$(jq -r .cache "$IDENTITY"); Q=$(dirname "$IDENTITY")
CP=$(jq -r '.runtime_classpath|join(":")' "$IDENTITY")
while read -r ENTRY; do case "$ENTRY" in "$CACHE"/*|"$Q"/*) ;; *) echo 'Unapproved base CP root' >&2; exit 2;; esac; done < <(jq -r '.runtime_classpath[]' "$IDENTITY")
mkdir -p "$OUT/source" "$OUT/tests"
BOUNDARY="$HERE/../../ai-boundary"
cp "$BOUNDARY/NativeFogBoundaryRegression.java" "$HERE/../NativeFogKnowledgeControls.java" \
    "$BOUNDARY/hidden-mana-followup/NativeHiddenManaFollowup.java" \
    "$BOUNDARY/hidden-mana-followup/known-controls/NativeKnownManaControls.java" "$OUT/source/"
for file in c/craw_wurm.txt j/jace_beleren.txt f/forest.txt f/fog.txt e/experimental_frenzy.txt; do cmp "$K/forge-gui/res/cardsfolder/$file" "$BOUNDARY/canonical/${file#*/}"; done
for file in f/future_sight.txt t/telepathy.txt s/spore_frog.txt; do cmp "$K/forge-gui/res/cardsfolder/$file" "$HERE/../canonical/${file#*/}"; done
cmp "$K/forge-gui/res/cardsfolder/e/elvish_spirit_guide.txt" "$BOUNDARY/hidden-mana-followup/canonical/elvish_spirit_guide.txt"
sha256sum "$OUT/source/"*.java "$J/bin/java" "$J/bin/javac" "$J/release" > "$OUT/inputs.sha256"
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$OUT/source" -cp "$CP" -d "$OUT/tests" \
    "$OUT/source/NativeFogBoundaryRegression.java" "$OUT/source/NativeFogKnowledgeControls.java" \
    "$OUT/source/NativeHiddenManaFollowup.java" "$OUT/source/NativeKnownManaControls.java" \
    > "$OUT/compile.stdout.log" 2> "$OUT/compile.stderr.log"
RUNTIME="$CP:$OUT/tests"
if test "$SHADOW" != NONE; then test "${SHADOW:0:1}" = /; RUNTIME="$SHADOW:$RUNTIME"; fi
printf '%s\n' "$RUNTIME" > "$OUT/runtime-classpath.txt"
if test "$#" = 0; then set -- NativeFogBoundaryRegression NativeFogKnowledgeControls NativeHiddenManaFollowup NativeKnownManaControls; fi
TOTAL=0
for CLASS in "$@"; do
    case "$CLASS" in NativeFogBoundaryRegression|NativeFogKnowledgeControls|NativeHiddenManaFollowup|NativeKnownManaControls) ;; *) exit 2;; esac
    CASE="$OUT/$CLASS"; mkdir -p "$CASE/home" "$CASE/tmp"
    # Bind only public engine/JDK inputs and the qualified payload root, not host mounts.
    ARGV=(bwrap --unshare-net --unshare-pid --ro-bind /usr /usr --ro-bind /lib /lib
        --ro-bind /lib64 /lib64 --ro-bind /bin /bin --ro-bind /etc /etc --proc /proc --dev /dev
        --tmpfs /tmp --ro-bind "$CACHE" "$CACHE" --ro-bind "$Q" "$Q" --bind "$OUT" "$OUT")
    if test "$SHADOW" != NONE; then ARGV+=(--ro-bind "$SHADOW" "$SHADOW"); fi
    ARGV+=(--chdir "$K/forge-gui-desktop" env -i PATH="$J/bin:/usr/bin:/bin" HOME="$CASE/home" LANG=C.UTF-8
        "$J/bin/java" -Xmx1500m -Djava.awt.headless=true -Duser.home="$CASE/home" -Djava.io.tmpdir="$CASE/tmp"
        -Dsentry.dsn= --add-opens java.base/java.lang=ALL-UNNAMED -cp "$RUNTIME" "forge.evaluation.$CLASS" "$CASE")
    printf '%q ' "${ARGV[@]}" > "$CASE/launch.argv.txt"
    set +e
    timeout -k 5s 180 strace --seccomp-bpf -f -qq -e trace=network -o "$CASE/network.private.strace" \
        "${ARGV[@]}" > "$CASE/stdout.private.log" 2> "$CASE/stderr.private.log"
    CODE=$?
    set -e
    printf '%s\n' "$CODE" > "$CASE/exit-code.txt"
    if test "$CODE" -gt 1 || test ! -f "$CASE/summary.json"; then echo "ERROR $CLASS (exit $CODE)"; exit 2; fi
    test "$CODE" -eq 0 || TOTAL=1
    cmp "$CASE/class-origins.json" "$CASE/class-origins.after.json"
    printf '%s ' "$CLASS"; cat "$CASE/summary.json"; printf '\n'
done
sha256sum -c "$OUT/inputs.sha256" > "$OUT/inputs.after.log"
exit "$TOTAL"
