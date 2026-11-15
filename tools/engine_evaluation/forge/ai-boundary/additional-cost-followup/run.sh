#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Original bounded read-only caller of Forge Team/Card-Forge native code. See NOTICE.md.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?absolute base BUILD-IDENTITY.json required}
FINAL=${2:?absolute current final candidate directory required}
OUT=${3:?new absolute local output directory required}
test "${IDENTITY:0:1}" = / && test "${FINAL:0:1}" = / && test "${OUT:0:1}" = / && test ! -e "$OUT"
case $(findmnt -T "$(dirname "$OUT")" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
test "$(jq -r .content_id "$FINAL/MANIFEST.json")" = ff89fd32da4e011d9e8f9af613a07a484894171ba7e4045c3932fcfaed4de398
test "$(jq -r .build_id "$IDENTITY")" = 59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605
K=$(jq -r .forge "$IDENTITY"); J=$(jq -r .jdk "$IDENTITY")
CACHE=$(jq -r .cache "$IDENTITY"); Q=$(dirname "$IDENTITY")
CP=$(jq -r '.runtime_classpath|join(":")' "$IDENTITY")
while read -r ENTRY; do case "$ENTRY" in "$CACHE"/*|"$Q"/*) ;; *) exit 2;; esac; done < <(jq -r '.runtime_classpath[]' "$IDENTITY")
for FILE in c/craw_wurm.txt j/jace_beleren.txt s/skirge_familiar.txt s/swamp.txt d/darkness.txt t/tendrils_of_agony.txt f/forest.txt; do
    cmp "$K/forge-gui/res/cardsfolder/$FILE" "$HERE/canonical/${FILE#*/}"
done
mkdir -p "$OUT/source" "$OUT/classes" "$OUT/home" "$OUT/tmp"
cp "$HERE/NativeAdditionalCostFollowup.java" "$OUT/source/"
cp "$IDENTITY" "$OUT/BASE-BUILD-IDENTITY.json"
cp "$FINAL/MANIFEST.json" "$OUT/CURRENT-MANIFEST.json"
cp "$FINAL/IDENTITY.json" "$OUT/CURRENT-IDENTITY.json"
(cd "$FINAL/shadow"; sha256sum -c ../payloads.sha256) > "$OUT/current-payloads.before.log"
sha256sum "$OUT/source/NativeAdditionalCostFollowup.java" "$J/bin/java" "$J/bin/javac" "$J/release" \
    "$FINAL/MANIFEST.json" "$FINAL/IDENTITY.json" "$K/forge-ai/src/main/java/forge/ai/simulation/ComboPlan.java" \
    "$K/forge-ai/target/classes/forge/ai/simulation/ComboPlan.class" > "$OUT/INPUT-PINS.sha256"
for NAME in ComputerUtil ComputerUtilCost ComputerUtilMana; do
    sha256sum "$FINAL/source/forge-ai/src/main/java/forge/ai/$NAME.java" >> "$OUT/INPUT-PINS.sha256"
done
(cd "$HERE"; sha256sum NativeAdditionalCostFollowup.java run.sh NOTICE.md canonical/*.txt) > "$OUT/TEST-PINS.sha256"
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$OUT/source" -cp "$CP" -d "$OUT/classes" \
    "$OUT/source/NativeAdditionalCostFollowup.java" > "$OUT/compile.stdout.log" 2> "$OUT/compile.stderr.log"
RUNTIME="$FINAL/shadow:$CP:$OUT/classes"
printf '%s\n' "$RUNTIME" > "$OUT/runtime-classpath.txt"
ARGV=(bwrap --unshare-net --unshare-pid --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64
    --ro-bind /bin /bin --ro-bind /etc /etc --proc /proc --dev /dev --tmpfs /tmp
    --ro-bind "$CACHE" "$CACHE" --ro-bind "$Q" "$Q" --ro-bind "$FINAL/shadow" "$FINAL/shadow"
    --bind "$OUT" "$OUT" --chdir "$K/forge-gui-desktop"
    env -i PATH="$J/bin:/usr/bin:/bin" HOME="$OUT/home" LANG=C.UTF-8
    "$J/bin/java" -Xmx768m -XX:MaxMetaspaceSize=192m -XX:ActiveProcessorCount=1 -XX:+UseSerialGC
    -Djava.awt.headless=true -Duser.home="$OUT/home" -Djava.io.tmpdir="$OUT/tmp" -Dsentry.dsn=
    --add-opens java.base/java.lang=ALL-UNNAMED -cp "$RUNTIME" forge.evaluation.NativeAdditionalCostFollowup "$OUT")
printf '%q ' "${ARGV[@]}" > "$OUT/launch.argv.txt"
set +e
nice -n 10 timeout -k 5s 180 strace --seccomp-bpf -f -qq -e trace=network -o "$OUT/network.private.strace" \
    "${ARGV[@]}" > "$OUT/stdout.private.log" 2> "$OUT/stderr.private.log"
CODE=$?
set -e
printf '%s\n' "$CODE" > "$OUT/exit-code.txt"
sha256sum -c "$OUT/INPUT-PINS.sha256" > "$OUT/INPUT-PINS.after.log"
(cd "$HERE"; sha256sum -c "$OUT/TEST-PINS.sha256") > "$OUT/TEST-PINS.after.log"
(cd "$FINAL/shadow"; sha256sum -c ../payloads.sha256) > "$OUT/current-payloads.after.log"
if test "$CODE" -gt 1 || test ! -f "$OUT/summary.json"; then echo "Native harness error (exit $CODE)"; exit 2; fi
cmp "$OUT/class-origins.json" "$OUT/class-origins.after.json"
jq -e --slurpfile m "$FINAL/MANIFEST.json" --arg root "$FINAL/shadow/" \
    '[$m[0].identity.payloads[] as $p | any(.[]; .class==$p.class_name and .sha256==$p.sha256 and .resource==("file:"+$root+($p.path|sub("^./";""))))]|all' \
    "$OUT/class-origins.json" >/dev/null
cat "$OUT/summary.json"; printf '\n'
exit "$CODE"
