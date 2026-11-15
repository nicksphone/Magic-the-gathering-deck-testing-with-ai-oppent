#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Additive correction to Forge Team/Card-Forge code; frozen parent stays unchanged.
set -euo pipefail
umask 077
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${1:?qualified base identity required}; OUT=${2:?fresh absolute local output required}
bash "$HERE/../known-mana/build.sh" "$IDENTITY" "$OUT"
test "$(cat "$OUT/CONTENT-ID.txt")" = 74e0cc8af0915195b8a0a353439847206997c3c0f9ba9b520731ce3708ae8d9b
cp "$OUT/IDENTITY.json" "$OUT/BASE-IDENTITY.json"
cp "$OUT/MANIFEST.json" "$OUT/BASE-MANIFEST.json"
cp "$OUT/sources.sha256" "$OUT/BASE-sources.sha256"
cp "$OUT/payloads.sha256" "$OUT/BASE-payloads.sha256"
cp "$HERE/empty-known-sources.patch" "$OUT/inputs/"
cp "$HERE/build.sh" "$OUT/inputs/empty-source-build.sh"
patch --batch --forward --fuzz=0 -p1 -d "$OUT/source" < "$HERE/empty-known-sources.patch" > "$OUT/empty-source-patch.log"
J=$(jq -r .jdk "$IDENTITY"); CP=$(jq -r '.runtime_classpath|join(":")' "$IDENTITY")
SOURCES=()
for NAME in ComputerUtil ComputerUtilCost ComputerUtilMana; do SOURCES+=("$OUT/source/forge-ai/src/main/java/forge/ai/$NAME.java"); done
"$J/bin/javac" --release 17 -implicit:none -sourcepath "$OUT/source" -cp "$CP" -d "$OUT/shadow" \
    "${SOURCES[@]}" > "$OUT/guarded-compile.stdout.log" 2> "$OUT/guarded-compile.stderr.log"
(cd "$OUT/shadow"; find . -type f -printf '%P\n' | sort) > "$OUT/guarded-emitted-payloads.txt"
cmp "$OUT/expected-payloads.txt" "$OUT/guarded-emitted-payloads.txt"
(cd "$OUT/source"; sha256sum forge-ai/src/main/java/forge/ai/*.java) > "$OUT/sources.sha256"
(cd "$OUT/shadow"; find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$OUT/payloads.sha256"
sha256sum "$J/bin/java" "$J/bin/javac" "$J/release" "$IDENTITY" "$OUT/inputs/"* > "$OUT/explicit-inputs.sha256"
python3 - "$OUT" <<'PY'
import hashlib, json, sys
from pathlib import Path
p=Path(sys.argv[1]); parent=json.loads((p/'BASE-MANIFEST.json').read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
sources=[{'path':v['path'],'sha256':sha(p/'source'/v['path'])} for v in parent['identity']['sources']]
payloads=[{**v,'sha256':sha(p/'shadow'/v['path'])} for v in parent['identity']['payloads']]
assert [s for s in sources if s != next(v for v in parent['identity']['sources'] if v['path']==s['path'])][0]['path'].endswith('/ComputerUtilMana.java')
assert sum(s!=v for s,v in zip(sources,parent['identity']['sources']))==1
assert sum(s!=v for s,v in zip(payloads,parent['identity']['payloads']))==1
identity={'schema':'forge-known-mana-empty-source-v1','base_build_id':parent['identity']['base_build_id'],
          'parent_content_id':parent['content_id'],'parent_identity':parent['identity'],
          'delta_patch_sha256':sha(p/'inputs/empty-known-sources.patch'),
          'builder_sha256':sha(p/'inputs/empty-source-build.sh'),'sources':sources,'payloads':payloads,
          'required_base_launch_sha256':parent['identity']['required_base_launch_sha256']}
content_id=hashlib.sha256((json.dumps(identity,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
manifest={'content_id':content_id,'identity':identity,'shadow':str(p/'shadow'),
          'runtime_classpath':parent['runtime_classpath'],'scope':'empty scoped source guard; separate build, not a full-game claim'}
for name,value in [('IDENTITY.json',identity),('MANIFEST.json',manifest),('sources.json',sources),('payloads.json',payloads)]:
 (p/name).write_text(json.dumps(value,indent=2)+'\n')
(p/'CONTENT-ID.txt').write_text(content_id+'\n')
bundle={'schema':1,'sources':{v['path']:v['sha256'] for v in sources},
        'classes':{v['path'].removeprefix('./'):v['sha256'] for v in payloads}}
(p/'APPROVED-BUNDLE.json').write_text(json.dumps(bundle,indent=2)+'\n')
print('Guarded candidate content ID:',content_id)
PY
