# Library Choice Context Correction

Three-path increment over the immutable audited source archive SHA256
`b0a6c5d4625e9a5035550061980611528622cd0e1008d3edbd9df822ae1b5d14`
at `private-library-choice-audit/mtg-library-choice-audit-0pdTOz`.
The earlier audit document/report describes the frozen original REDs, not this
correction. Original 288-case test files and canonical fixtures remain unchanged.

## Exact Product Seam

Only the mechanic `context` set in `TrainingEnvironment.lookup_intent` changes:
`controller`, `amount`, `bottom_ids`, `effect_key`, `continuation_controller`,
`continuation_effects`, `counter_continuation_queue`, `draw_continuation_queue`.
These are actual fields from the audited actor-owned legal views, not aliases.
Every supplied context value must exist in the current actor's pending state
and match its canonical JSON exactly. Existing actor/type validation, copied
legal-view generation, display validation and unknown-field guards remain.
After validation, metadata is stripped; unchanged `MechanicChoice` checks the
explicit chosen payload before unchanged completion and checked trial execution.

No client continuation is executed, no choice is inferred and no blanket
display allowlist added. Nullable siblings retain declared compatibility.
Raw API action bodies still reject metadata packets. No model/helper/API/engine/
AI/frontend edits and no foretell/combat/Ninjutsu integration writes. Parent can
compose the single context-set hunk with disjoint branches using AST parity.

## Qualification

Original 288 assertions are run unchanged. New controls cover all eight fields
in all nine audited initial/order positions, both seats: null, nested alias,
boolean and JSON float type tampering reject before completion; exact sparse
context and dictionary key-order differences normalize without root mutation.
Wrong actor/controller, unavailable contexts, stale whole views, missing explicit
selection and hidden prefix/foreign-hand observation controls remain strict.
Additional actual HTTP cases verify every context tamper returns 422 without
changing state/controller/SQLite, exact whole views survive backend restart and
normalize only the submitted selection, and raw action API remains strict.

Canonical coverage remains Opt/Preordain, Consider/Notion Rain and
Impulse/Memory Deluge, both seats, printed offered costs only. Full Oracle/raw
fixture/provenance facts unchanged. Prior alias/privacy/replay/order/downstream
effect and 48-restart controls remain; no blanket card-family/flashback/policy
certification or natural-history claim. HTTP is the frozen guarded test-only
Training bridge plus actual production legal/action/restore paths, not a claimed
production Training endpoint or actual-App gate. Training trusted provenance
restore and new hotseat authentication are not certified.

## Reproduction

Use a fresh LOCAL source-only copy of the exact audit tar, no Git/DB/cache/
runtime/dependencies or environment secrets. Apply this three-path delta and
mark its unit-test source before using the external interpreter:

```sh
printf '%s' "$PWD" > .private-choice-audit-source
/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q -s \
 backend/tests/test_library_choice_intent_audit.py \
 backend/tests/test_library_choice_http_audit.py \
 backend/tests/test_library_choice_context_correction.py
```

All gates/receipts/preimages and hashes are in terminal evidence. Runtime SQLite
is always local, ports random loopback, only spawned processes stopped. Archive
private synthetic receipts/SQLite on verified NFS before process-checked cleanup.
