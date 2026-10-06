# Non-mana intent field-drop audit

## Result

Frozen current-parent source: **16 strict failures, 12 passing controls**, 87
datetime deprecation warnings, 22.69 seconds, exit 1. No skips or expected-failure
markers. This is a reproduced safety gap, not a green feature qualification.
All 16 failures are the final expected `ActionRejected` assertion; preceding
strict lookup, HTTP rejection, root/DB invariance, and actual execution checks
completed successfully. No production files were modified.

## Canonical coverage

Both seats use actual canonical Lightning Bolt (`cast_spell`) and Recruitment
Officer (`activate_ability`), with a visible opposing Grizzly Bears. Officer
inspects actual Serra Angel, Opt, Savannah Lions, Serra Angel and explicitly
selects the eligible Savannah Lions. Fixtures use existing canonical card data,
bounded trusted state construction and local SQLite; external network is blocked.

Four unsupported requested-field categories per family and seat reproduce the
gap: top-level `target_card_id`, `source_zone`, `face_index`, and a cost field not
supported by that action model (spell `payment_choices`, ability `cost_choice`).
These are NOT supported alternative encodings. Strict `lookup` and raw HTTP
reject them. `lookup_intent` instead strips the fields and accepts the remaining
action. The normalized action executes through actual HTTP and snapshot restart.
Trusted replay also verifies Bolt damages the originally selected opponent, not
the requested creature, and Officer reaches and completes its private selection.
The desired rejection assertion remains ordinary strict RED, never xfail.

Passing controls distinguish genuine legal-move presentation metadata from
choices. Whole actual move hints plus explicit chosen parameters normalize
correctly. Recognized schema fields (spell `cost_choice`, `from_graveyard`,
`selected_face_index`, nested targets; ability index, `payment_choices`, nested
targets) remain checked and reject invalid values through both consumers and
HTTP. Root snapshots and persisted DB dumps remain unchanged on rejected calls.

Actor observation/action alias bytes and prompt bytes are identical after
permuting opposing hidden identities and hidden-zone order, for both families
and seats. Officer's inspected identities and prompt details are available only
to the authorized actor; the other observer has no selection prompts. Trusted
fixture/replay code accesses full state, not exported model input. These checks
do not claim arbitrary raw card IDs are safe model features.

## Provenance and limitations

Source was copied read-only from the parent's frozen current composition,
including the all-mana intent guard and consumption forwarding fix. The 870
parent Python/JSON source hashes match before/after copying and match the copy.
The canonical static token SVG was subsequently copied to complete the runtime
dependency; the earlier collection failure is retained separately. Final audit
backend hashes are recorded before/after tests and AST graph refresh. Main and
parent source were not edited. Test databases remain local during execution.

This audit covers two action families, not every action, supported multi-face
mechanism, alternate-zone cast, or cost mechanic. Unsupported names are tested
as rejection contracts, not newly implemented choices. No NN competence or
expert-data claim. The observed whole-view controls do not establish a complete
presentation-field inventory across all families.

Proposed separately scoped follow-up: reject non-schema requested fields before
normalization for these consumers, allowing only explicitly qualified known
display metadata and using public action schemas. Preserve complete explicit
choices, raw API behavior and whole-view controls; do not infer missing choices,
accept invented aliases, or redesign the private action catalog. Production
changes require separate coordination and qualification.

## Reproduction

Run the new test on the archived frozen source with the project's existing
Python environment and dependencies:

```sh
cd backend
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_nonmana_intent_audit.py
```

Expected current result is exit 1 with 16 strict failures and 12 passes. The
tests/report patch is incremental only; source and dependency provenance,
complete logs and checksums accompany the frozen NFS archive.
