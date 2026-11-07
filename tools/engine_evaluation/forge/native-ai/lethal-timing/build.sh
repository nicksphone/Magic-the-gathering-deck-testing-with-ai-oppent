#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Separate one-source increment; never modifies the qualified base or ff89 parent.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?qualified base identity required}; OUT=${2:?fresh absolute local output required}
test "${OUT:0:1}" = / && test ! -e "$OUT"
case $(findmnt -T "$(dirname "$OUT")" -n -o FSTYPE | tail -1) in nfs*|cifs) exit 2;; esac
test "$(sha256sum "$IDENTITY" | cut -d' ' -f1)" = cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0
K=$(jq -r .forge "$IDENTITY"); J=$(jq -r .jdk "$IDENTITY")
CP=$(jq -r '.runtime_classpath|join(":")' "$IDENTITY")
REL=forge-ai/src/main/java/forge/ai/ability/DamageDealAi.java
test "$(sha256sum "$K/$REL" | cut -d' ' -f1)" = 67b2d16a5aae9ef30760d6000f53b5abc4162a8b60df10b0f38ca493a5ae71eb
mkdir -p "$OUT/source/$(dirname "$REL")" "$OUT/shadow" "$OUT/inputs"
cp "$K/$REL" "$OUT/source/$REL"
cp "$IDENTITY" "$OUT/BASE-IDENTITY.json"
cp "$HERE/build.sh" "$HERE/lethal-player-timing.patch" "$OUT/inputs/"
sha256sum "$K/$REL" "$J/bin/java" "$J/bin/javac" "$J/release" "$IDENTITY" "$OUT/inputs/"* > "$OUT/inputs.sha256"
patch --batch --forward --fuzz=0 -p1 -d "$OUT/source" < "$OUT/inputs/lethal-player-timing.patch" > "$OUT/patch.log"
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$OUT/source" -cp "$CP" -d "$OUT/shadow" \
    "$OUT/source/$REL" > "$OUT/compile.stdout.log" 2> "$OUT/compile.stderr.log"
(cd "$OUT/shadow"; find . -type f -printf '%P\n' | sort) > "$OUT/emitted-payloads.txt"
printf '%s\n' forge/ai/ability/DamageDealAi.class > "$OUT/expected-payloads.txt"
cmp "$OUT/expected-payloads.txt" "$OUT/emitted-payloads.txt"
(cd "$OUT/source"; sha256sum "$REL") > "$OUT/sources.sha256"
(cd "$OUT/shadow"; sha256sum forge/ai/ability/DamageDealAi.class) > "$OUT/payloads.sha256"
python3 - "$OUT" <<'PY'
import hashlib, json, sys
from pathlib import Path
p = Path(sys.argv[1])
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
source = 'forge-ai/src/main/java/forge/ai/ability/DamageDealAi.java'
payload = 'forge/ai/ability/DamageDealAi.class'
identity = {
    'schema': 'forge-lethal-player-timing-v1',
    'base_build_id': json.loads((p/'BASE-IDENTITY.json').read_text())['build_id'],
    'required_base_launch_sha256': 'ee58d6110017448391e210c1722d6f1450904c239cc297282f34e4ed4c588562',
    'qualified_parent_content_id': 'ff89fd32da4e011d9e8f9af613a07a484894171ba7e4045c3932fcfaed4de398',
    'source': {'path': source, 'sha256': sha(p/'source'/source)},
    'payload': {'path': payload, 'sha256': sha(p/'shadow'/payload)},
    'builder_sha256': sha(p/'inputs/build.sh'),
    'patch_sha256': sha(p/'inputs/lethal-player-timing.patch'),
    'base_identity_sha256': sha(p/'BASE-IDENTITY.json'),
    'jdk_inputs': {name: sha(Path(json.loads((p/'BASE-IDENTITY.json').read_text())['jdk'])/name)
                   for name in ['bin/java', 'bin/javac', 'release']},
}
content = hashlib.sha256((json.dumps(identity, sort_keys=True, separators=(',', ':'))+'\n').encode()).hexdigest()
manifest = {'content_id': content, 'identity': identity, 'shadow': str(p/'shadow'),
            'scope': 'One-class increment only; parent composition and app qualification are separate.'}
(p/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
(p/'CONTENT-ID.txt').write_text(content+'\n')
print(json.dumps(manifest, indent=2))
PY
sha256sum -c "$OUT/inputs.sha256" > "$OUT/input-readback.log"
