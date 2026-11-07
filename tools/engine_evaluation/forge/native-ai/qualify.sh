#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Original controlled-native qualification caller. See NOTICE.md; no deployment.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?BUILD-IDENTITY.json required}
SCRATCH=${2:?absolute local scratch parent required}
MODE=${3:?original or candidate required}
case "$MODE" in original|candidate) ;; *) exit 2;; esac
test "${SCRATCH:0:1}" = /
case $(findmnt -T "$SCRATCH" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
K=$(jq -r .forge "$IDENTITY"); J=$(jq -r .jdk "$IDENTITY")
CP=$(jq -r '.runtime_classpath | join(":")' "$IDENTITY")
test "$(jq -r .build_id "$IDENTITY")" = 59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605
RUN=$(mktemp -d "$SCRATCH/fog-knowledge-$MODE.XXXXXXXX")
printf '%s\n' "$RUN"
mkdir "$RUN/tests" "$RUN/test-source"
cp "$IDENTITY" "$RUN/BUILD-IDENTITY.input.json"
cp "$HERE/../ai-boundary/NativeFogBoundaryRegression.java" "$HERE/NativeFogKnowledgeControls.java" "$RUN/test-source/"
(cd "$HERE/../ai-boundary"; find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$RUN/original-nine.sha256"
for file in c/craw_wurm.txt j/jace_beleren.txt f/forest.txt f/fog.txt e/experimental_frenzy.txt; do
    cmp "$K/forge-gui/res/cardsfolder/$file" "$HERE/../ai-boundary/canonical/${file#*/}"
done
for file in f/future_sight.txt t/telepathy.txt s/spore_frog.txt; do
    cmp "$K/forge-gui/res/cardsfolder/$file" "$HERE/canonical/${file#*/}"
done
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$RUN/test-source" -cp "$CP" \
    -d "$RUN/tests" "$RUN/test-source/NativeFogBoundaryRegression.java" "$RUN/test-source/NativeFogKnowledgeControls.java" \
    > "$RUN/test-compile.stdout.log" 2> "$RUN/test-compile.stderr.log"
# Qualified CP order is untouched; test-only classes are appended, never native shadows.
RUNTIME="$CP:$RUN/tests"
if test "$MODE" = candidate; then
    bash "$HERE/build.sh" "$IDENTITY" "$RUN/candidate" > "$RUN/build.stdout.log" 2> "$RUN/build.stderr.log"
    RUNTIME="$RUN/candidate/shadow:$RUNTIME"
fi
printf '%s\n' "$RUNTIME" > "$RUN/runtime-classpath.txt"
sha256sum "$J/bin/java" "$J/bin/javac" "$J/release" "$RUN/test-source/"*.java > "$RUN/runtime-inputs.sha256"
"$J/bin/java" -version > "$RUN/jdk-version.log" 2>&1
TOTAL=0
for CLASS in NativeFogBoundaryRegression NativeFogKnowledgeControls; do
    CASE="$RUN/$CLASS"
    mkdir -p "$CASE/home" "$CASE/tmp"
    ARGV=(bwrap --unshare-net --unshare-pid --ro-bind / / --bind "$RUN" "$RUN" --proc /proc --dev /dev
        --chdir "$K/forge-gui-desktop" env -i PATH="$J/bin:/usr/bin:/bin" HOME="$CASE/home" LANG=C.UTF-8
        "$J/bin/java" -Xmx1500m -Djava.awt.headless=true -Duser.home="$CASE/home"
        -Djava.io.tmpdir="$CASE/tmp" -Dsentry.dsn= --add-opens java.base/java.lang=ALL-UNNAMED
        -cp "$RUNTIME" "forge.evaluation.$CLASS" "$CASE")
    printf '%q ' "${ARGV[@]}" > "$CASE/launch.argv.txt"
    set +e
    timeout -k 5s 180 strace --seccomp-bpf -f -qq -e trace=network -o "$CASE/network.private.strace" \
        "${ARGV[@]}" > "$CASE/stdout.private.log" 2> "$CASE/stderr.private.log"
    STATUS=$?
    set -e
    printf '%s\n' "$STATUS" > "$CASE/exit-code.txt"
    test "$STATUS" -eq 0 || TOTAL=1
    test -f "$CASE/class-origins.after.json" && cmp "$CASE/class-origins.json" "$CASE/class-origins.after.json"
    cat "$CASE/summary.json"
    printf '\n'
done
sha256sum -c "$RUN/runtime-inputs.sha256" > "$RUN/runtime-inputs.after.log"
(cd "$HERE/../ai-boundary"; sha256sum -c "$RUN/original-nine.sha256") > "$RUN/original-nine.after.log"
if test "$MODE" = candidate; then
    sha256sum -c "$RUN/candidate/candidate.sha256" > "$RUN/candidate.after.log"
fi
exit "$TOTAL"
