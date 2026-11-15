#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Original bounded review caller using frozen Forge candidate/tests. See NOTICE.md.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?absolute BUILD-IDENTITY.json required}
RUN=${2:?new absolute local output directory required}
test "${IDENTITY:0:1}" = / && test "${RUN:0:1}" = / && test ! -e "$RUN"
case $(findmnt -T "$(dirname "$RUN")" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
K=$(jq -r .forge "$IDENTITY"); J=$(jq -r .jdk "$IDENTITY")
CP=$(jq -r '.runtime_classpath|join(":")' "$IDENTITY")
test "$(jq -r .build_id "$IDENTITY")" = 59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605
cmp "$K/forge-gui/res/cardsfolder/e/elvish_spirit_guide.txt" "$HERE/canonical/elvish_spirit_guide.txt"
for file in c/craw_wurm.txt j/jace_beleren.txt f/forest.txt f/fog.txt; do
    cmp "$K/forge-gui/res/cardsfolder/$file" "$HERE/../canonical/${file#*/}"
done
mkdir -p "$RUN/test-source" "$RUN/tests"
cp "$IDENTITY" "$RUN/BUILD-IDENTITY.input.json"
cp "$HERE/NativeHiddenManaFollowup.java" "$RUN/test-source/"
sha256sum "$J/bin/java" "$J/bin/javac" "$J/release" "$RUN/test-source/NativeHiddenManaFollowup.java" > "$RUN/inputs.sha256"
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$RUN/test-source" -cp "$CP" -d "$RUN/tests" \
    "$RUN/test-source/NativeHiddenManaFollowup.java" > "$RUN/compile.stdout.log" 2> "$RUN/compile.stderr.log"
OVERALL=0
for MODE in original candidate; do
    # Run all twenty existing checks with their unchanged frozen source/assertions.
    set +e
    bash "$HERE/../../native-ai/qualify.sh" "$IDENTITY" "$RUN" "$MODE" \
        > "$RUN/$MODE.existing-qualification.stdout.log" 2> "$RUN/$MODE.existing-qualification.stderr.log"
    CODE=$?
    set -e
    printf '%s\n' "$CODE" > "$RUN/$MODE.existing-qualification.exit"
    EXPECTED=0; test "$MODE" != original || EXPECTED=1
    test "$CODE" -eq "$EXPECTED"
    QUALIFIED=$(head -1 "$RUN/$MODE.existing-qualification.stdout.log")
    test -d "$QUALIFIED"
    printf '%s\n' "$QUALIFIED" > "$RUN/$MODE.existing-root.path"
    RUNTIME="$CP:$RUN/tests"
    if test "$MODE" = candidate; then
        printf '60ec0579438008e0c5a1eba4ef0ffde6b77f3eaf7ab9865c8fa3a2a1b97a1bfc  %s/candidate/shadow/forge/ai/ComputerUtil.class\n' "$QUALIFIED" | sha256sum -c - > "$RUN/candidate.frozen-class-check.log"
        RUNTIME="$QUALIFIED/candidate/shadow:$RUNTIME"
    fi
    CASE="$RUN/$MODE.followup"
    mkdir -p "$CASE/home" "$CASE/tmp"
    printf '%s\n' "$RUNTIME" > "$CASE/runtime-classpath.txt"
    ARGV=(bwrap --unshare-net --unshare-pid --ro-bind / / --bind "$RUN" "$RUN" --proc /proc --dev /dev
        --chdir "$K/forge-gui-desktop" env -i PATH="$J/bin:/usr/bin:/bin" HOME="$CASE/home" LANG=C.UTF-8
        "$J/bin/java" -Xmx1500m -Djava.awt.headless=true -Duser.home="$CASE/home" -Djava.io.tmpdir="$CASE/tmp"
        -Dsentry.dsn= --add-opens java.base/java.lang=ALL-UNNAMED -cp "$RUNTIME"
        forge.evaluation.NativeHiddenManaFollowup "$CASE")
    printf '%q ' "${ARGV[@]}" > "$CASE/launch.argv.txt"
    set +e
    timeout -k 5s 180 strace --seccomp-bpf -f -qq -e trace=network -o "$CASE/network.private.strace" \
        "${ARGV[@]}" > "$CASE/stdout.private.log" 2> "$CASE/stderr.private.log"
    CODE=$?
    set -e
    printf '%s\n' "$CODE" > "$CASE/exit-code.txt"
    test "$CODE" -le 1
    test "$CODE" -eq 0 || OVERALL=1
    cmp "$CASE/class-origins.json" "$CASE/class-origins.after.json"
    printf '%s follow-up: ' "$MODE"; cat "$CASE/summary.json"; printf '\n'
done
sha256sum -c "$RUN/inputs.sha256" > "$RUN/inputs.after.log"
exit "$OVERALL"
