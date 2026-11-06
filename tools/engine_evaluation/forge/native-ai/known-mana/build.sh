#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Owned three-source increment over Forge Team/Card-Forge work. See NOTICE.md.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?absolute base BUILD-IDENTITY.json required}
OUT=${2:?new absolute local candidate directory required}
test "${IDENTITY:0:1}" = / && test "${OUT:0:1}" = / && test ! -e "$OUT"
case $(findmnt -T "$(dirname "$OUT")" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
K=$(jq -r .forge "$IDENTITY"); J=$(jq -r .jdk "$IDENTITY")
CP=$(jq -r '.runtime_classpath|join(":")' "$IDENTITY")
test "$(basename "$K")" = forge-61e9442c433711a82258daca3236f936a1d6f70e
test "$(jq -r .build_id "$IDENTITY")" = 59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605
(cd "$K"; sha256sum -c "$HERE/upstream-preimages.sha256")
mkdir -p "$OUT/source/forge-ai/src/main/java/forge/ai" "$OUT/shadow" "$OUT/inputs"
for NAME in ComputerUtil ComputerUtilCost ComputerUtilMana; do
    cp "$K/forge-ai/src/main/java/forge/ai/$NAME.java" "$OUT/source/forge-ai/src/main/java/forge/ai/"
done
cp "$IDENTITY" "$OUT/inputs/BASE-BUILD-IDENTITY.json"
cp "$HERE/../hasAFogEffect-actor-knowledge.patch" "$HERE/known-card-affordability.patch" \
    "$HERE/preimages.sha256" "$HERE/upstream-preimages.sha256" "$HERE/build.sh" "$HERE/NOTICE.md" "$OUT/inputs/"
cp "$HERE/../../LICENSE" "$OUT/LICENSE"
patch --batch --forward --fuzz=0 -p1 -d "$OUT/source" < "$HERE/../hasAFogEffect-actor-knowledge.patch" > "$OUT/identity-patch.log"
(cd "$OUT/source"; sha256sum -c "$HERE/preimages.sha256") > "$OUT/preimages.log"
patch --batch --forward --fuzz=0 -p1 -d "$OUT/source" < "$HERE/known-card-affordability.patch" > "$OUT/known-card-patch.log"
SOURCES=("$OUT/source/forge-ai/src/main/java/forge/ai/ComputerUtil.java"
    "$OUT/source/forge-ai/src/main/java/forge/ai/ComputerUtilCost.java"
    "$OUT/source/forge-ai/src/main/java/forge/ai/ComputerUtilMana.java")
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$OUT/source" -cp "$CP" -d "$OUT/shadow" "${SOURCES[@]}" \
    > "$OUT/compile.stdout.log" 2> "$OUT/compile.stderr.log"
printf '%s\n' 'forge/ai/ComputerUtil.class' 'forge/ai/ComputerUtilCost$1.class' \
    'forge/ai/ComputerUtilCost.class' 'forge/ai/ComputerUtilMana.class' > "$OUT/expected-payloads.txt"
(cd "$OUT/shadow"; find . -type f -printf '%P\n' | sort) > "$OUT/emitted-payloads.txt"
cmp "$OUT/expected-payloads.txt" "$OUT/emitted-payloads.txt"
(cd "$OUT/shadow"; find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$OUT/payloads.sha256"
(cd "$OUT/source"; sha256sum forge-ai/src/main/java/forge/ai/*.java) > "$OUT/sources.sha256"
sha256sum "$J/bin/java" "$J/bin/javac" "$J/release" "$IDENTITY" \
    "$OUT/inputs/"* > "$OUT/explicit-inputs.sha256"
"$J/bin/java" -version > "$OUT/JDK-VERSION.txt" 2>&1
jq -Rn '[inputs|capture("^(?<sha256>[a-f0-9]+)  (?<path>.*)$")|. + {class_name:(.path|sub("^./";"")|sub("[.]class$";"")|gsub("/";"."))}]' < "$OUT/payloads.sha256" > "$OUT/payloads.json"
jq -Rn '[inputs|capture("^(?<sha256>[a-f0-9]+)  (?<path>.*)$")]' < "$OUT/sources.sha256" > "$OUT/sources.json"
jq -Rn '[inputs|capture("^(?<sha256>[a-f0-9]+)  (?<path>.*)$")]' < "$HERE/preimages.sha256" > "$OUT/preimages.json"
jq -Rn '[inputs|capture("^(?<sha256>[a-f0-9]+)  (?<path>.*)$")]' < "$HERE/upstream-preimages.sha256" > "$OUT/upstream-preimages.json"
jq -n --arg base "$(jq -r .build_id "$IDENTITY")" --arg basefile "$(sha256sum "$IDENTITY"|cut -d' ' -f1)" \
    --arg identity_patch "$(sha256sum "$HERE/../hasAFogEffect-actor-knowledge.patch"|cut -d' ' -f1)" \
    --arg increment_patch "$(sha256sum "$HERE/known-card-affordability.patch"|cut -d' ' -f1)" \
    --arg builder "$(sha256sum "$HERE/build.sh"|cut -d' ' -f1)" \
    --arg java "$(sha256sum "$J/bin/java"|cut -d' ' -f1)" --arg javac "$(sha256sum "$J/bin/javac"|cut -d' ' -f1)" \
    --arg release "$(sha256sum "$J/release"|cut -d' ' -f1)" --slurpfile payloads "$OUT/payloads.json" --slurpfile sources "$OUT/sources.json" \
    --slurpfile preimages "$OUT/preimages.json" --slurpfile upstream "$OUT/upstream-preimages.json" \
    '{schema:"forge-known-mana-shadow-v1",forge_revision:"61e9442c433711a82258daca3236f936a1d6f70e",
      base_build_id:$base,base_identity_sha256:$basefile,identity_patch_sha256:$identity_patch,
      increment_patch_sha256:$increment_patch,builder_sha256:$builder,
      compiler:{release:17,implicit:"none",java_sha256:$java,javac_sha256:$javac,jdk_release_sha256:$release},
      required_base_launch_sha256:"ee58d6110017448391e210c1722d6f1450904c239cc297282f34e4ed4c588562",
      source_preimages:$preimages[0],upstream_source_preimages:$upstream[0],
      sources:$sources[0],payloads:$payloads[0]}' > "$OUT/IDENTITY.json"
ID=$(jq -cS . "$OUT/IDENTITY.json" | sha256sum | cut -d' ' -f1)
jq -n --arg id "$ID" --slurpfile identity "$OUT/IDENTITY.json" --arg shadow "$OUT/shadow" \
    --slurpfile base "$IDENTITY" '{content_id:$id,identity:$identity[0],shadow:$shadow,
      runtime_classpath:([$shadow]+$base[0].runtime_classpath),
      scope:"separate native known-mana increment; not application/save qualification"}' > "$OUT/MANIFEST.json"
printf '%s\n' "$ID" > "$OUT/CONTENT-ID.txt"
(cd "$K"; sha256sum -c "$HERE/upstream-preimages.sha256") > "$OUT/upstream.after.log"
printf 'Candidate content ID: %s\n' "$ID"
