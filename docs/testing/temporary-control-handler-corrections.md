# Independent Temporary-Control Handler Corrections

Base: immutable `temporary-control-delayed-pure-stage` production patch
`78d62df2116fd146892277a92655e6dfdc359cdb5c320caf33d8afa0a7238d8d`.

Two independent corrections in `effects/handlers.py` only:

- A newer indefinite control instruction removes the older until-end-of-turn
  restoration cache, including when the controller does not change. It does not
  emit a manufactured control-change event or remove a waiting Ray record.
- The complete temporary-control instruction uses its actual resolving controller
  for "you gain control", rather than a controller inherited from a copied payload.
  Generic `change_control` still respects explicit `new_controller` (Act route unchanged).

Pure qualification denies all SQLite connections and socket connections.
The new whole module has 16 ordinary passing tests, including actual paid Dominate,
Twincast, Counterspell, subsequent Ray control loss, snapshot/replay and Act controls.
The unchanged two paid Dominate regressions change from 0 pass / 2 strict failures
to 2 pass. The unchanged eight copied-spell episodes now have zero controller
failures but still eight strict retained-copy-frame failures. Those diagnostic
scripts still exit 1; this is not a whole-product success claim.

No engine, stack, source-frame, schema or delayed-record edits are included.
Different-expiry control layering remains unsupported; this is not a layer-model
implementation. Ray149 SQL/HTTP qualification remains unstarted and on HOLD.
