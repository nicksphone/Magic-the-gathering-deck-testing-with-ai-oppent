#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Isolated callers of unchanged Forge tests plus narrow owner controls. See NOTICE.md.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
BASE=${1:?absolute Q BUILD-IDENTITY.json}
CANDIDATE=${2:?absolute directory containing MANIFEST.json and shadow/}
OUT=${3:?fresh absolute LOCAL output}
shift 3
test "${BASE:0:1}" = / && test "${CANDIDATE:0:1}" = / && test "${OUT:0:1}" = / && test ! -e "$OUT"
case $(findmnt -T "$(dirname "$OUT")" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
test "$(jq -r .build_id "$BASE")" = 59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605
K=$(jq -r .forge "$BASE"); J=$(jq -r .jdk "$BASE"); CACHE=$(jq -r .cache "$BASE"); Q=$(dirname "$BASE")
CP=$(jq -r '.runtime_classpath|join(":")' "$BASE")
while read -r ENTRY; do case "$ENTRY" in "$CACHE"/*|"$Q"/*) ;; *) exit 2;; esac; done < <(jq -r '.runtime_classpath[]' "$BASE")
BOUNDARY=$(cd "$HERE/../.." && pwd); NATIVE=$(cd "$BOUNDARY/../native-ai" && pwd)
for FILE in c/craw_wurm.txt j/jace_beleren.txt f/forest.txt f/fog.txt e/experimental_frenzy.txt; do
    cmp "$K/forge-gui/res/cardsfolder/$FILE" "$BOUNDARY/canonical/${FILE#*/}"
done
for FILE in f/future_sight.txt t/telepathy.txt s/spore_frog.txt; do
    cmp "$K/forge-gui/res/cardsfolder/$FILE" "$NATIVE/canonical/${FILE#*/}"
done
cmp "$K/forge-gui/res/cardsfolder/e/elvish_spirit_guide.txt" "$BOUNDARY/hidden-mana-followup/canonical/elvish_spirit_guide.txt"
for FILE in c/craw_wurm.txt j/jace_beleren.txt s/skirge_familiar.txt s/swamp.txt d/darkness.txt t/tendrils_of_agony.txt f/forest.txt; do
    cmp "$K/forge-gui/res/cardsfolder/$FILE" "$HERE/../canonical/${FILE#*/}"
done
mkdir -p "$OUT/source" "$OUT/tests"
cp "$BOUNDARY/NativeFogBoundaryRegression.java" "$NATIVE/NativeFogKnowledgeControls.java" \
    "$BOUNDARY/hidden-mana-followup/NativeHiddenManaFollowup.java" \
    "$BOUNDARY/hidden-mana-followup/known-controls/NativeKnownManaControls.java" \
    "$HERE/../NativeAdditionalCostFollowup.java" "$HERE/NativeHeldPieceOwnerControls.java" "$OUT/source/"
sha256sum "$OUT/source/"*.java "$J/bin/java" "$J/bin/javac" "$J/release" "$BASE" \
    "$CANDIDATE/MANIFEST.json" "$CANDIDATE/IDENTITY.json" "$HERE/run-tests.sh" > "$OUT/inputs.sha256"
(cd "$CANDIDATE/shadow"; sha256sum -c ../payloads.sha256) > "$OUT/payloads.before.log"
"$J/bin/javac" -J-Xmx768m -J-XX:ActiveProcessorCount=1 --release 17 -implicit:none -sourcepath "$OUT/source" \
    -cp "$CANDIDATE/shadow:$CP" -d "$OUT/tests" "$OUT/source/"*.java > "$OUT/compile.stdout.log" 2> "$OUT/compile.stderr.log"
RUNTIME="$CANDIDATE/shadow:$CP:$OUT/tests"
printf '%s\n' "$RUNTIME" > "$OUT/runtime-classpath.txt"
if test "$#" = 0; then set -- NativeFogBoundaryRegression NativeFogKnowledgeControls NativeHiddenManaFollowup \
    NativeKnownManaControls NativeAdditionalCostFollowup NativeHeldPieceOwnerControls; fi
TOTAL=0
for CLASS in "$@"; do
    case "$CLASS" in NativeFogBoundaryRegression|NativeFogKnowledgeControls|NativeHiddenManaFollowup|NativeKnownManaControls|NativeAdditionalCostFollowup|NativeHeldPieceOwnerControls) ;; *) exit 2;; esac
    CASE="$OUT/$CLASS"; mkdir -p "$CASE/home" "$CASE/tmp"
    ARGV=(bwrap --unshare-net --unshare-pid --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64
        --ro-bind /bin /bin --ro-bind /etc /etc --proc /proc --dev /dev --tmpfs /tmp
        --ro-bind "$CACHE" "$CACHE" --ro-bind "$Q" "$Q" --ro-bind "$CANDIDATE/shadow" "$CANDIDATE/shadow"
        --bind "$OUT" "$OUT" --chdir "$K/forge-gui-desktop" env -i PATH="$J/bin:/usr/bin:/bin"
        HOME="$CASE/home" LANG=C.UTF-8 "$J/bin/java" -Xmx768m -XX:MaxMetaspaceSize=192m
        -XX:ActiveProcessorCount=1 -XX:+UseSerialGC -Djava.awt.headless=true -Duser.home="$CASE/home"
        -Djava.io.tmpdir="$CASE/tmp" -Dsentry.dsn= --add-opens java.base/java.lang=ALL-UNNAMED
        -cp "$RUNTIME" "forge.evaluation.$CLASS" "$CASE")
    printf '%q ' "${ARGV[@]}" > "$CASE/launch.argv.txt"
    set +e
    nice -n 10 timeout -k 5s 180 strace --seccomp-bpf -f -qq -e trace=network -o "$CASE/network.private.strace" \
        "${ARGV[@]}" > "$CASE/stdout.private.log" 2> "$CASE/stderr.private.log"
    CODE=$?
    set -e
    printf '%s\n' "$CODE" > "$CASE/exit-code.txt"
    if test "$CODE" -gt 1 || test ! -f "$CASE/summary.json"; then echo "ERROR $CLASS exit=$CODE"; exit 2; fi
    test "$CODE" = 0 || TOTAL=1
    cmp "$CASE/class-origins.json" "$CASE/class-origins.after.json"
    jq -e --slurpfile manifest "$CANDIDATE/MANIFEST.json" --arg root "file:$CANDIDATE/shadow/" \
        '[.[] as $o | $manifest[0].identity.payloads[] | select(.class_name==$o.class) |
          ($o.sha256==.sha256 and $o.resource==($root+(.path|sub("^./";""))))] | length>0 and all' \
        "$CASE/class-origins.json" > /dev/null
    printf '%s ' "$CLASS"; cat "$CASE/summary.json"; printf '\n'
done
sha256sum -c "$OUT/inputs.sha256" > "$OUT/inputs.after.log"
(cd "$CANDIDATE/shadow"; sha256sum -c ../payloads.sha256) > "$OUT/payloads.after.log"
exit "$TOTAL"
