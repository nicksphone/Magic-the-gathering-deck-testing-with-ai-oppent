#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Original isolated caller of the Forge Team/Card-Forge native engine. See NOTICE.md.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?usage: bash run.sh /absolute/BUILD-IDENTITY.json /absolute/local/scratch-parent}
SCRATCH=${2:?fresh local scratch parent required}
test "${IDENTITY:0:1}" = / && test "${SCRATCH:0:1}" = /
case $(findmnt -T "$SCRATCH" -n -o FSTYPE | tail -1) in nfs*|cifs) echo 'Local scratch required' >&2; exit 2;; esac
K=$(jq -r .forge "$IDENTITY")
J=$(jq -r .jdk "$IDENTITY")
CP=$(jq -r '.runtime_classpath | join(":")' "$IDENTITY")
test "$(basename "$K")" = forge-61e9442c433711a82258daca3236f936a1d6f70e
for file in c/craw_wurm.txt j/jace_beleren.txt f/forest.txt f/fog.txt e/experimental_frenzy.txt; do
    cmp "$K/forge-gui/res/cardsfolder/$file" "$HERE/canonical/${file#*/}"
done
RUN=$(mktemp -d "$SCRATCH/native-fog-boundary.XXXXXXXX")
mkdir "$RUN/classes" "$RUN/source" "$RUN/home" "$RUN/tmp"
cp "$IDENTITY" "$RUN/BUILD-IDENTITY.input.json"
cp "$HERE/NativeFogBoundaryRegression.java" "$RUN/source/"
printf '%s\n' "$CP" > "$RUN/qualified-classpath.txt"
printf '%s\n' "$RUN"
sha256sum "$J/bin/java" "$J/bin/javac" "$J/release" "$RUN/source/NativeFogBoundaryRegression.java" > "$RUN/explicit-inputs.sha256"
"$J/bin/java" -version > "$RUN/jdk-version.log" 2>&1
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$RUN/source" -cp "$CP" \
    -d "$RUN/classes" "$RUN/source/NativeFogBoundaryRegression.java" \
    > "$RUN/compile.stdout.log" 2> "$RUN/compile.stderr.log"
ARGV=(bwrap --unshare-net --unshare-pid --ro-bind / / --bind "$RUN" "$RUN" --proc /proc --dev /dev
    --chdir "$K/forge-gui-desktop" env -i PATH="$J/bin:/usr/bin:/bin" HOME="$RUN/home" LANG=C.UTF-8
    "$J/bin/java" -Xmx1500m -Djava.awt.headless=true -Duser.home="$RUN/home"
    -Djava.io.tmpdir="$RUN/tmp" -Dsentry.dsn= --add-opens java.base/java.lang=ALL-UNNAMED
    -cp "$RUN/classes:$CP" forge.evaluation.NativeFogBoundaryRegression "$RUN")
printf '%q ' "${ARGV[@]}" > "$RUN/launch.argv.txt"
set +e
timeout -k 5s 180 strace --seccomp-bpf -f -qq -e trace=network -o "$RUN/network.private.strace" \
    "${ARGV[@]}" > "$RUN/stdout.private.log" 2> "$RUN/stderr.private.log"
STATUS=$?
set -e
printf '%s\n' "$STATUS" > "$RUN/exit-code.txt"
sha256sum --check "$RUN/explicit-inputs.sha256" > "$RUN/explicit-inputs.after.log"
test ! -e "$RUN/class-origins.after.json" || cmp "$RUN/class-origins.json" "$RUN/class-origins.after.json"
test ! -e "$RUN/summary.json" || cat "$RUN/summary.json"
exit "$STATUS"
