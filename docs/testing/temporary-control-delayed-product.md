# Complete Temporary Control And Loss-Of-Control Tap

## Frozen Source

Own disposable source is extracted from the immutable current composition tar
`qualified-source.tar.gz`, SHA256
`6c35136afad30c37d120303fc9487ae7076d77dc3070375dd12cc7722608968d`.
This is an archive hash, not a Git commit. No moving parent or main source was read.
Canonical Ray of Command, Act of Treason and Cloudshift rows and official intake
receipts are inherited unchanged from `fixtures/temporary_control_audit`.

## Scope And Timing

The additive anchored compiler recognizes the complete instruction to untap an
opponent's creature, gain control until end of turn, grant haste until end of
turn, and create a delayed tap on loss of control. No card-name dispatch or
inferred target is used. Unknown trailing instructions fail closed rather than
grant a supported prefix. Existing Act of Treason compilation is not replaced.

Ray does not schedule a next-end-step tap. Its actual printed condition is loss
of control. At ordinary cleanup the duration ends first, a genuine delayed
trigger is published, and players receive priority before the tap resolves.
Stifle can counter that tap without reversing control expiry. An earlier real
control change or battlefield departure can also satisfy the condition.

The existing delayed-trigger list stores the resolving controller, source ID,
pre-departure spell reference, and affected object's incarnation and zone-change
sequence. Snapshot serialization needs no new field or schema. Collection uses
real committed control changes or the existing pre-departure battlefield event;
ordinary APNAP, resolution staging and cleanup repeat publish the trigger.
Resolution cannot tap a same-ID reentered object. No StackItem is fabricated by
the effect handler and no new tap target is selected.

Same-cleanup temporary control changes retain the underlying controller rather
than restoring an already-expired temporary controller. This is not a general
replacement of continuous control layers, Aura dependencies or multiplayer rules.

Production changes are confined to `oracle_effects.py`, `handlers.py`,
`keyword_triggers.py`, `registry.py`, and the cleanup control-return emitter in
`engine.py`. Events, targeting helpers, serializers, API schemas and planners
remain unchanged.

## Measured Ledger

- First whole two-module cohort: 50 passed, 6 failed, 2 warnings, 30.98 seconds,
  exit 1. Four unchanged historical Ray assertions expect a tap at the first
  cleanup boundary, before the real delayed trigger resolves. Two new privacy
  fixture failures allocated an extra object only in the comparison state;
  this was corrected to swap two existing hidden objects without changing the
  allocator or inventory. The raw run is preserved.
- Corrected whole four-module pure cohort: 34 passed, 2 warnings, 16.38 seconds,
  exit 0. SQLite connections and network connections are denied across the
  entire cohort. Both-seat paid casts, Stifle, cleanup repeat, early second Ray,
  response blink, old-object tap rejection, private identity permutation and
  snapshot restart are included. Source hashes are identical before and after.
- Twelve new HTTP/cold-SQL cases are drafted but unexecuted. The proposed whole
  nine-module follow-up collects 149 cases; collection is not qualification.
  The exclusive SQLite slot is queued after Jason and Meitner. No HTTP, database
  atomicity or full-neighbor acceptance is claimed by the pure-stage artifact.

All original 32 core and 12 HTTP audit assertions remain byte-identical. Their
first-cleanup tap witnesses are diagnostic, not grounds to make a delayed
trigger resolve without priority. Any later test adaptation requires a separate
explicit delta and must preserve the historical archives and raw results.

## Rules Evidence And Limits

The official Comprehensive Rules PDF retrieved for this stage is
`https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf`.
CR 514.3a explains cleanup trigger priority and repeat cleanup; CR 603.7c
preserves the referenced object without following a zone-change/reentry;
CR 603.7d retains the resolving spell's controller; CR 603.10d uses pre-change
information for loss-of-control conditions. Raw PDF, retrieval time and checksum
are preserved in evidence.

No Battle, arbitrary control-layer framework, multiplayer, extra-turn schedule,
AI competence, browser or live-deployment qualification is claimed.
