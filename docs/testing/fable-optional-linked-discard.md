# Optional Linked Discard / Draw

## Scope And Source

Qualified on immutable `6f9e29ec2e8ea7f1ebb880a4f553960b887edafb`, source archive
SHA256 `1427d34aa99f6f1ddb2bae0bfa85adeb4a8bc172812a73964123537a08edf1d3`.
Only `rules_engine/linked_discard.py::linked_discard_effect` changes. Existing
functions, inference/event collection, stack producer, costs, handlers, AI,
coverage and public schemas remain unchanged.

The helper recognizes the **complete** optional own-hand discard-up-to-N followed
by `If you do, draw that many cards` instruction, optionally inside its complete
Saga chapter-line envelope. The envelope is needed because the existing admission
caller checks printed chapter lines, while resolution compiles extracted bodies.
No loose `you may` rewrite, named-card branch, fixed draw substitute, new choice
state or diagnostic bypass is added. Unknown tails, foreign recipients and changed
conditions/count linkage do not match.

The existing descriptor retains `up_to=True`, the printed maximum and
`followup_effect={effect_key:draw_cards,payload:{},count_field:amount}`.
The existing caller supplies `self_discard=True`; existing handlers and choice
completion use the actual selected count and original effect controller.

## Canonical Paid Acceptance

The new test uses an intact full two-face Scryfall Fable response, not shortened
playable Oracle. Its source, hash and inherited canonical fixture dependencies are
pinned in `tests/fixtures/fable_optional_linked_discard/provenance.json`.
Initial boards contain explicit canonical untapped lands; paid casts consume them.
Actual checked priority/turn progression produces chapters I/II/III. There are no
injected stack objects/events or direct chapter-publication calls in this module.
The current hand is configured after the genuine draw step to exercise 0/1/2/3
eligible-card boundaries; this is a controlled rules fixture, not a natural game.

Both seats exercise explicit decline/one/two identities, zero eligible cards,
counted draws and discard history, opposing-hand invariance, training actor-private
observations/full legal-view intents, snapshot/resume, stale/foreign/duplicate/
over-limit/wrong-actor rejection and metadata tampering. Paid Naturalize destroys
the Saga before chapter II resolves; private controller and linked count remain
correct. Canonical Leyline discard-to-exile and Stinkweed Imp nested draw choices
retain counted follow-up and resume once. Actual chapter-I token and final-face
controls remain ordinary passing assertions.

## Gate And Limits

Final **five complete pure modules: 92 PASS, 86.96 seconds, exit 0**, no JUnit
errors/failures/skips. New module: 56 cases; unchanged neighbors: 36 cases.
All original 44 baseline cases/functions are unchanged; 12 controls were added.
Native/public SQLite and every socket audit event are denied before imports,
including bare socket construction. Alias controls cover DBAPI/native constructors.
This is a Python isolation guard, not an OS syscall sandbox or HTTP certificate.

The first 44-case run had 6 passes/38 failures: 34 setup assertions incorrectly
expected root Oracle on a genuine two-face response, plus four grammar failures.
Only that setup assertion was corrected to accept authentic face data. The sealed
corrected baseline had 6 passes/38 failures in 4.41 seconds: 34 payable normal cast
attempts were rejected by existing linked-discard admission before payment, plus
four missing-body grammar failures. No bypass was used. The first fixed gate had
80 passes/72.83 seconds; the final gate adds controls. These overlapping counts
must not be summed. Raw ledgers and exact JUnit nodes are retained separately.

`test_linked_discard` and `test_saga_live` are mixed HTTP/SQL modules and are not
run or pruned in this pure qualification. Actual HTTP/cold SQLite/UI acceptance
requires a separately granted integration gate. This does not certify all Fable
faces/Reflection abilities, arbitrary Saga/linked-discard clauses, natural full
games, AI policy quality, balance or release readiness.

## Reproduce

Use the archived pre-import guard/runner and the unchanged external qualified
Python environment, from the isolated source root:

```bash
timeout 600 "$MTG_TEST_PYTHON" evidence/run_pure.py -q \
  backend/tests/test_fable_optional_linked_discard.py \
  backend/tests/test_sagas.py \
  backend/tests/test_saga_counter_events.py \
  backend/tests/test_fable_goblin_treasure.py \
  backend/tests/test_draw_restrictions.py
```

No dependency installation, SQLite fixture or application server is required.
Completed artifacts belong on mounted verified RCHFiles, never execute SQLite on
NFS. Source/test preimages and preservation proofs are in the qualification archive.
