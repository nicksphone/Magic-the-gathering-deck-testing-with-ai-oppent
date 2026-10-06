# Non-mana null-field audit follow-up

## Strict result

Original audit plus this NEW follow-up: **32 strict failures, 26 passing
controls**, 54 datetime deprecation warnings, 73.47 seconds, exit 1. No skips,
deselection or expected-failure markers. All failures are final consumer
`ActionRejected` assertions: 16 original non-null witnesses and 16 NEW null
witnesses. This is reproduced unsafe normalization, not a qualified fix.

The incremental patch adds one test module and this document only. It depends
on the frozen original tests/report patch SHA256
`e9000e2c4c0b008537eb6f6cff5962e4d4b795ab1989ea90b7273ab83164ac30`.
Production, original test/doc, main and parent source remain unchanged.

## Null versus supported choices

Canonical Lightning Bolt cast and Recruitment Officer activation, both seats:
unsupported top-level `target_card_id`, `source_zone`, `face_index`, and the
per-family unsupported cost field (`payment_choices` for cast, `cost_choice`
for activation) remain extra fields even when explicitly `null`. Strict lookup
and actual raw HTTP reject every such request with root/controller/local DB
unchanged. `lookup_intent` silently drops the key and accepts the remaining
action. Before each final strict RED assertion, the test proves normalized
execution through trusted replay and actual HTTP plus resolution/restart.
Officer's authorized private selection is completed in trusted replay, with
opposing prompt/identity privacy checks inherited from the original fixture.

Supported choices have independently passing execution controls, both seats:

- Bolt nested `targets.target_player` damages the chosen opponent to 17 life
  and leaves the visible creature alive. Nested `targets.target_card_id` instead
  kills the chosen Grizzly Bears and leaves the opponent at 20 life. Whole actual
  legal-move metadata does not replace either explicit chosen target.
- Sickening Dreams nested `targets.x_value: 1` and typed
  `cost_choice.discard_card_ids` consume the selected Opt, preserve unselected
  Savannah Lions, and produce 19 life for each player. The actual offered
  `cost_choice.id` is supplied; no inferred discard/X choice or invented card.
- `targets: null` is invalid for these action models. Unknown nested
  `targets.unknown_choice: null` is also rejected, not stripped. Strict lookup,
  intent and actual HTTP preserve the rejected root and DB.

These controls compare canonical actions after public schema normalization,
then assert exact chosen target/cost values. Public schema default false origin
flags are not unsupported request fields. The initial run's six overly strict
dict-equality failures (22 failed/8 passed, 39.71 seconds) are preserved as
test-construction history; only those comparisons changed, not production or
strict rejection expectations. Final supported controls all pass.

## Exact provenance and limits

This uses the **older read-only parent copy** frozen in
`nonmana-intent-audit-P7QbxQ`, with its exact 870 parent-source and 872 tested-source
manifests retained. It does NOT claim qualification of the subsequently reported
latest parent ROOT containing perf9b, fixed-cost b919 or the two AI forwarding
helpers (652 ordinary passes). The parent reports environment unchanged, but
that does not make these full source compositions identical.

The added test increases the final backend manifest to 873 files; hashes before
and after tests/AST refresh accompany the archive. SQLite executes locally only;
finished archival DB bytes are copied and compared on verified NFS. External
network connections are forbidden by the imported actual HTTP fixture. Existing
privacy/alias byte-equality controls rerun unchanged in the serial composed audit.

These unsupported top-level spell/ability fields are not new aliases or new
engine choices. Proper nullable OPTIONAL fields are not universally prohibited;
the boundary is the actual action schema. This does not qualify every non-mana
family, alternate-zone or multi-face card, UI, AI policy or NN competence.

Any production remedy remains separately scoped: pre-normalization rejection of
non-schema requested keys with an explicit qualified display-metadata allowlist,
preserving typed choices and whole-view controls. No such fix is in this patch.

## Reproduce

Apply the original tests/report patch, then this incremental NEW-tests/doc patch
to an equivalent source with the existing dependencies. From `backend`:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_nonmana_intent_audit.py tests/test_nonmana_null_intent_audit.py
```

Expected frozen-baseline outcome is exit 1, 32 strict failures and 26 passes.
