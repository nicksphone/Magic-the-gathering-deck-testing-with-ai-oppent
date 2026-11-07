#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Forge Team/Card-Forge sources and native parent increment; see NOTICE.md.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
BASE=${1:?absolute Q BUILD-IDENTITY.json}
FINAL=${2:?absolute E/final}
OUT=${3:?fresh absolute LOCAL candidate directory}
test "${BASE:0:1}" = / && test "${FINAL:0:1}" = / && test "${OUT:0:1}" = / && test ! -e "$OUT"
case $(findmnt -T "$(dirname "$OUT")" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
test "$(jq -r .build_id "$BASE")" = 59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605
test "$(jq -r .content_id "$FINAL/MANIFEST.json")" = ff89fd32da4e011d9e8f9af613a07a484894171ba7e4045c3932fcfaed4de398
K=$(jq -r .forge "$BASE"); J=$(jq -r .jdk "$BASE")
CP=$(jq -r '.runtime_classpath|join(":")' "$BASE")
mkdir -p "$OUT/source/forge-ai/src/main/java/forge/ai" "$OUT/shadow" "$OUT/empty-sourcepath"
cat > "$OUT/preimages.sha256" <<'PINS'
a01fe06b0ceb8e1d2e6ecfbd719e16d59a33cf9cab57874e051f381d425beaf6  forge-ai/src/main/java/forge/ai/ComputerUtil.java
15681c6592e1d843b384945bcd67f81b1ce9cbbbd2aea29be1f5c5cfcdbe30a1  forge-ai/src/main/java/forge/ai/ComputerUtilCost.java
6928620486da73f525fc5eb5e9369d47a2ceeb444706f4711da173e481948c54  forge-ai/src/main/java/forge/ai/ComputerUtilMana.java
PINS
(cd "$FINAL/source"; sha256sum -c "$OUT/preimages.sha256") > "$OUT/preimages.before.log"
(cd "$FINAL/shadow"; sha256sum -c ../payloads.sha256) > "$OUT/parent-payloads.before.log"
sha256sum "$BASE" "$FINAL/MANIFEST.json" "$FINAL/IDENTITY.json" "$J/bin/java" "$J/bin/javac" "$J/release" \
    "$K/forge-ai/src/main/java/forge/ai/simulation/ComboPlan.java" \
    "$K/forge-ai/target/classes/forge/ai/simulation/ComboPlan.class" \
    "$HERE/known-held-piece.patch" "$HERE/build.sh" > "$OUT/inputs.sha256"
for NAME in ComputerUtil ComputerUtilCost ComputerUtilMana; do
    cp "$FINAL/source/forge-ai/src/main/java/forge/ai/$NAME.java" "$OUT/source/forge-ai/src/main/java/forge/ai/"
done
cp "$HERE/known-held-piece.patch" "$HERE/NOTICE.md" "$OUT/"
patch --batch --fuzz=0 -p1 -d "$OUT/source" < "$HERE/known-held-piece.patch" > "$OUT/patch.log"
printf '%s\n' "$CP" > "$OUT/compiler-classpath.txt"
CMD=("$J/bin/javac" -J-Xmx768m -J-XX:ActiveProcessorCount=1 --release 17 -implicit:none
    -sourcepath "$OUT/empty-sourcepath" -cp "$CP" -d "$OUT/shadow")
for NAME in ComputerUtil ComputerUtilCost ComputerUtilMana; do
    CMD+=("$OUT/source/forge-ai/src/main/java/forge/ai/$NAME.java")
done
printf '%q ' "${CMD[@]}" > "$OUT/compile.argv.txt"
nice -n 10 "${CMD[@]}" > "$OUT/compile.stdout.log" 2> "$OUT/compile.stderr.log"
printf '%s\n' 'forge/ai/ComputerUtil.class' 'forge/ai/ComputerUtilCost$1.class' \
    'forge/ai/ComputerUtilCost.class' 'forge/ai/ComputerUtilMana.class' > "$OUT/expected-payloads.txt"
(cd "$OUT/shadow"; find . -type f -printf '%P\n' | LC_ALL=C sort) > "$OUT/emitted-payloads.txt"
cmp "$OUT/expected-payloads.txt" "$OUT/emitted-payloads.txt"
(cd "$OUT/shadow"; while read -r P; do sha256sum "$P"; done < "$OUT/expected-payloads.txt") > "$OUT/payloads.sha256"
(cd "$OUT/source"; sha256sum forge-ai/src/main/java/forge/ai/*.java) > "$OUT/sources.sha256"
jq -Rn '[inputs | capture("^(?<sha256>[a-f0-9]{64})  (?<path>.+)$")]' < "$OUT/preimages.sha256" > "$OUT/preimages.json"
jq -Rn '[inputs | capture("^(?<sha256>[a-f0-9]{64})  (?<path>.+)$")]' < "$OUT/sources.sha256" > "$OUT/sources.json"
jq -Rn '[inputs | capture("^(?<sha256>[a-f0-9]{64})  (?<path>.+)$") | . + {class_name:(.path|sub(".class$";"")|gsub("/";"."))}]' \
    < "$OUT/payloads.sha256" > "$OUT/payloads.json"
hash() { sha256sum "$1" | cut -d ' ' -f 1; }
jq -n --slurpfile pre "$OUT/preimages.json" --slurpfile sources "$OUT/sources.json" --slurpfile payloads "$OUT/payloads.json" \
    --arg base "$(jq -r .build_id "$BASE")" --arg base_sha "$(hash "$BASE")" \
    --arg parent "$(jq -r .content_id "$FINAL/MANIFEST.json")" --arg parent_sha "$(hash "$FINAL/MANIFEST.json")" \
    --arg patch "$(hash "$HERE/known-held-piece.patch")" --arg builder "$(hash "$HERE/build.sh")" \
    --arg java "$(hash "$J/bin/java")" --arg javac "$(hash "$J/bin/javac")" --arg release "$(hash "$J/release")" \
    --arg cp "$(hash "$OUT/compiler-classpath.txt")" \
    '{schema:"forge-known-held-piece-shadow-v1",forge_revision:"61e9442c433711a82258daca3236f936a1d6f70e",
      base_build_id:$base,base_identity_sha256:$base_sha,parent_content_id:$parent,parent_manifest_sha256:$parent_sha,
      required_base_launch_sha256:"ee58d6110017448391e210c1722d6f1450904c239cc297282f34e4ed4c588562",
      increment_patch_sha256:$patch,builder_sha256:$builder,
      compiler:{release:17,implicit:"none",java_sha256:$java,javac_sha256:$javac,jdk_release_sha256:$release,classpath_sha256:$cp},
      source_preimages:$pre[0],sources:$sources[0],payloads:$payloads[0]}' > "$OUT/IDENTITY.json"
ID=$(jq -Sc . "$OUT/IDENTITY.json" | sha256sum | cut -d ' ' -f 1)
jq -n --arg id "$ID" --slurpfile identity "$OUT/IDENTITY.json" '{content_id:$id,identity:$identity[0]}' > "$OUT/MANIFEST.json"
sha256sum -c "$OUT/inputs.sha256" > "$OUT/inputs.after.log"
(cd "$FINAL/source"; sha256sum -c "$OUT/preimages.sha256") > "$OUT/preimages.after.log"
(cd "$FINAL/shadow"; sha256sum -c ../payloads.sha256) > "$OUT/parent-payloads.after.log"
printf 'Candidate content_id=%s\n' "$ID"
