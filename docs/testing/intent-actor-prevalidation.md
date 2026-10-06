# Intent Actor Prevalidation

## Scope
Frozen baseline: special-land audit patch `1f4c702cd4d2c99c727f74c096f6f22ba4c87c13ec3a7e5568b583d720e54911`, qualified source archive `8aec593043684088a2caaa0564bd742961e67481498d77ad61258e15776832b2`, on published d3 plus unchanged 381/52 dependencies. No moving parent source, rebasing, API/schema/helper/engine changes, nullable action redesign or new card data.

Production delta is one entry call inside `TrainingEnvironment.lookup_intent`: `_seat(self.acting_seat if seat is None else seat)`. Existing `_seat` admits built-in integer 1 or 2, rejecting the audited bool/string/float/out-of-range/list/dict forms, consistent with the public `PlayerID` StrictInt/range boundary for those inputs. Reuse avoids a second validator or new import/binding. Explicit `None` remains the same authoritative current-actor shorthand as omitted seat; it is NOT an invalid explicit HTTP PlayerID. Invalid current actor/terminal None rejects before helpers. Wrong valid seat remains subject to existing checked legality; no early ownership semantics added.

Whole-module byte/AST preservation proof removes only this entry call and recovers the exact preimage, including all 21 model bindings and every existing branch. The incremental patch has exactly three paths: environment, NEW tests, this document. No frozen dependencies duplicated.

## Qualification
Unchanged special-land audit: **164 PASS**, 2 warnings, 49.46s. All original 12 desired before-helper assertions ordinary green; both seats Sacred Foundry chosen entry and Crucible/Ramunap graveyard origin remain explicit. All eight real loopback HTTP flows, private views, raw422, stale409, full-root/SQLite invariants and actual process restarts retained.

NEW actor controls: **512 PASS**, 2 warnings, 16.28s. Invalid actors cover all 21 recognized intent dispatch envelopes plus unknown fallback, both seats; real delegating complete_action/legal_moves/serialize_card_view spies show no helper calls. Partial dispatch envelopes deliberately are not claimed as valid canonical actions. Public PlayerID TypeAdapter independently rejects the same malformed input forms. Null/omitted-current-actor controls include invalid authority and terminal None.

Positive canonical whole-view controls cover both seats shockland tapped/pay, both graveyard grants, immediate mana, pass, Delver/Officer private choices, foretell, ninjutsu, spell/ability and attack/block. Omitted/None/explicit valid actor normalize identically, wrong seat rejects without root/input mutation, and wire snapshot roundtrip plus full-episode copy replay matches execution. No inferred targets/costs/entry/origin or invented Oracle.

Two NEW test-only setup errors are retained with source/log/XML: first copied only game state, losing training step counts (16 failed/496 passed); second attempted trusted training.restore on deliberately synthetic canonical positions without deck provenance (12 failed/500 passed). Final replay preserves the complete training object and roundtrips its state through existing serializers. No original audit assertions adapted, no provenance invented, no production restore change or training.restore certification for synthetic positions.

Fresh whole affected neighbor modules and final artifact receipts are listed in the terminal report. No full-suite/card-family certification or frontend claim. Warnings are existing framework deprecations.

## Reproduce
Use `/home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python`; every frozen declared pin matches package metadata, pip check passes. Reconstruct the qualified source locally, apply this increment, set `.private-choice-audit-source` to the exact isolated root path; never execute this audit in a tracked/live checkout or with NFS SQLite.

```sh
python -m pytest -q backend/tests/test_training_intent_actor_prevalidation.py
python -m pytest -v -s backend/tests/test_land_consumer_variants.py backend/tests/test_land_consumer_variants_http.py
```

Neighbor module inventory, invocation logs, failed NEW drafts, preimages, AST proof, interpreter pins and private synthetic database/process evidence are archived on verified mounted project NFS. Parent/main/live are untouched.
