# Granted-target audit: runnable checks

No backend production is duplicated here. Six unchanged-owned modules and their support/full-raw canonical data are included. Only test_granted_target_producers.py has the reviewed strengthening: real copied-occurrence StackItem cardinality and exact per-grant/object quota delta before repeat-mark/final restore. Producer cases use explicitly retained boards/mana; no-choice uses the real copy handler rather than paying a copy card. Synthetic boundaries are not canonical paid deck proof.

## Explicit modes

- boundary56: whole producers16 + diagnostics8 + publication32. No filtering, skips or xfails.
- composed140: boundary56 plus both whole AI modules (12 + 48) and original whole equip21/attachments3. This requires the sibling `audit/gate2-granted-target-AI` package. No filters, skips or xfails; all shared fixtures occur once.
- composed265: fourteen whole modules combining boundary56, compiler33, AI attachment/forecast60, new simulation-frontier16, original equip/attachments24 and four existing AI-neighbor modules76. This covers the shared AI-only uncertainty boundary while retaining known-card resolution, first priority passes and actual offered responses. No original assertion is adapted.
- paid24-original: original unchanged 24 test bodies, helper, recipe and historical shuffle witnesses. On historical implementation the result was 22PASS/2 setup FAIL; before implementation it was 8PASS/16 first-trigger FAIL. Do not silently present this as green CI.
- paid24-qualified: SAME original 24 bodies, ONLY the two new_incarnation fixture seed overrides declared in paid24-reentry-inputs.json and paid24-reentry-node-seeds.json. Other22 seeds unchanged. Separate real paid result24PASS131.22s; historical run had a documented transient running-capacity floor exception, not a continuous floor claim.
- compiler33: whole compiler/layer synthetic controls.
- incarnation4: additive real paid recipient/grant reentry witnesses; not replacements for original failed inputs.

paid24-qualified patching is opt-in runner mode only, never automatic conftest/CI behavior. Both seed metadata files and original witness files are byte-preserved. Raw provenance contains an archival NFS location as historical provenance only; tests do not read that bulk path. No download, reinstall or external runtime lookup is required.

## Native reproduction

Use a LOCAL immutable source-only checkout, an already qualified CPython3.12.3 venv, a NEW empty LOCAL evidence directory outside source/venv, and independently sealed source/runtime JSON maps. No SQL/network/socket/child is permitted. This wrapper retains the reviewed pre-app-import native denial controls, four deliberate canaries, full before/after source/runtime/RNG/thread/FD checks, all155 seed rows, 300-second alarm and16MiB evidence cap. Native controls are NOT an OS/arbitrary-child-file sandbox. Launch requires strictly >3GiB+128MiB free; evidence writes enforce3GiB floor. This runtime contract remains the qualified2037 full/1558 nonpip map plus original four-link manifest, not arbitrary new environment/platform qualification.

From project root, set these operator-supplied LOCAL paths:

```sh
PY=path/to/qualified/venv/bin/python
E=path/to/new-local-evidence
SOURCE_PINS=path/to/sealed-source-files.json
RUNTIME_PINS=path/to/sealed-runtime-full-pins.json
RUNTIME_MANIFEST=path/to/sealed-runtime-manifest.json
mkdir "$E"
timeout --signal=TERM --kill-after=15s 315s "$PY" -B \
  audit/gate2-granted-target/run_native.py boundary56 "$E" \
  "$SOURCE_PINS" "$RUNTIME_PINS" "$RUNTIME_MANIFEST"
```

Default source is this bundle's project root; MTG_AUDIT_SOURCE may explicitly select a separate immutable local source-only checkout for bundle qualification. Whole source pins must cover the actual integration source including this bundle if installed there. Evidence must NOT be inside source. Runtime manifest must contain actual nonpip hashes and symlink_targets; runtime-full map covers all regular venv files. Do not supply inferred old equality or build a fresh runtime implicitly.

Use a fresh E for each explicitly selected mode. paid24-original and paid24-qualified are separate commands/ledgers, never an implicit retry or fallback. run_native.py is path/mode factoring of the executed reviewed runner, with the same qualified-input hook used in the separately recorded paid run. Its adaptation diff is supplied with the handoff; only actually executed modes are qualified.

Keep whole original test_copy_stack_characteristics separately: its four Tibalt failures are prepayment complete-body admission blockers shared with a53, not waived by this suite. No classifier/corpus/API/AI edits, SQL/browser/1872 matrix or whole-card readiness claim.
