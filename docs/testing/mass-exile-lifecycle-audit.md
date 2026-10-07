# Canonical mass-exile lifecycle audit

Tests-only, immutable published 07305a18801e884ff3e4f8a3393a7132c436e990 backend source.
Source tar SHA256 d9bd64251f0e651832f995cc7dc70ed6af062a2a891b5241266793d304396716.

Final two whole modules: 46 executed, 34 PASS, 12 strict FAIL, 15.65s, pytest exit 1.
No skips, xfails, deselection, SQL connections, network, API startup or production edits.
Native sqlite3.connect and socket audit hooks precede pytest/project imports; all three
sqlite connect aliases also reject. Cached qualified Python 3.12.3, pytest 9.0.3.

Full unchanged official Scryfall responses and provenance live in
backend/tests/fixtures/mass_exile_audit. Canonical controlled starting boards are
explicit fixtures, not proof of natural creature casting. Mana is produced by actual
checked land taps. Final Judgment, Sunfall, Raise the Alarm, Ray of Command and
Descend upon the Sinful execute through checked casts and real priority responses.
No synthetic events, StackItems, rewritten Oracle or indestructible destruction.

## Strict findings
- Eight actual paid Final Judgment/Sunfall cases: own/opposing controlled creature
  inventories and owner exile routing succeed, but BF->EXILE zone_change_sequence
  remains 1 instead of 2, including after snapshot restoration.
- Four paid Ray->mass-exile cases: real delayed control-loss record remains after
  departure. Delegating emitter traces show already-EXILE objects at LBF publication,
  unchanged sequence, authentic retained PRE LKI and previous controller. Existing
  keyword collector requires the actual object still on BF at collection.

## Passing boundaries
- Full raw fixture hash/Oracle receipts, both-seat real paid tokens, Sunfall Incubator
  count including tokens and foreign creatures; no claim about transformation.
- Glorious Anthem/Humility PRE LKI, noncreature static sources survive, no false Blood
  Artist dies/life triggers. Wrong actor rejects without root/payment/RNG mutation.
- Actor-private unseen hand/library remain opaque; face-up exiled identities visible.
- Separate full canonical Descend delirium tail executes and creates its 4/4 Angel.
  This is measured support, not evidence for arbitrary unknown trailing clauses.

## Minimal proposal, not implementation grant
Own effects/handlers.py::exile_all_creatures only after owner coordination: validate
whole creature cohort, capture genuine PRE references/LKI, publish genuine leave batch
at the established PRE-mutation lifecycle boundary, then use CardInstance.move_to_zone
(EXILE) and correct owner lists exactly once. Preserve batch simultaneity, token cleanup,
static suppression, existing Sunfall moved count and no false dies. Do not broaden any
Oracle matcher or synthesize control_changed. Requalify these unchanged strict tests and
whole affected neighbors before claiming closure. No shared keyword collector change is
shown necessary by this audit.

## Historical harness ledgers
Initial collection: 0 tests, two errors from replacing socket class (SSL subclass import).
Native socket audit remained; only class replacement removed.
First executed 42: 30 PASS/12 FAIL, 14.22s. Expanded draft 46: 30 PASS/16 FAIL,
15.74s; four additional failures were test-only tuple-unpacking errors in decision_view.
Correct tuple unpack preserves all intended privacy assertions. Final 46 above is authority.
