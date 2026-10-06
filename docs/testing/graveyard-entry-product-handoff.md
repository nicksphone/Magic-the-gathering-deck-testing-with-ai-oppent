# Graveyard Entry Product Handoff

Candidate-only, not qualified legal episodes until the real producer is composed.
Source-only base: frozen `/tmp/mtg-static-current-compose-jry07R`.
Current events preimage `6f9ab35f`, zone preimage `135985f2`.

## Producer ABI For Lagrange

Existing `emit_event(state, event, payload)` and
`emit_event_batch(state, event, payloads)` stay unchanged. New event name:
`enters_graveyard`. Required payload:

```python
{
    "card_id": plan.card_id,
    "owner": plan.owner,
    "from_zone": plan.origin.value,
    "previous_controller": plan.controller,
    "previous_reference": {
        "incarnation": plan.incarnation,
        "zone_change_sequence": plan.sequence,
    },
    "entry_reference": {
        "incarnation": object_incarnation(card),
        "zone_change_sequence": card.zone_change_sequence,
    },
}
```

Publish only after actual owner GRAVEYARD membership and `move_to_zone` commit,
only when destination is GRAVEYARD and origin is not GRAVEYARD. No publication
for LIBRARY/EXILE replacement or failed selection/payment. Collector verifies
the entered reference against the current graveyard object and the sequence
increment. It binds the owner as controller and instruction recipient.

`execute_graveyard_entry` is the shared insertion point, immediately after the
move and before return. Producer-owner needs a local deferred-event buffer for
selected simultaneous sacrifice/discard/cost/mill batches; flush after all moves
inside existing resolution/payment trigger staging, before legacy event aliases.
Stack departure publication must wait for existing printed-face restoration in
`move_spell_from_stack`. Do not emit a second entry from legacy death/discard/mill
aliases. Producer/static receipt preparation and prepayment checks are untouched
by this worker. No zone/cost edits belong to this candidate.

## Retained Trigger And Shuffle Cause

The actual descriptor retains `__trigger_source_reference` equal to the new
graveyard object's entry reference, plus actual matched clause/index. It is
provenance, not a liveness target: Cremate can exile the source in response.
The actual popped StackItem is transported as `__resolving_item` to handlers and
sequence continuations. No collector-generated StackItem or announcing-spell
attribution. The generic resolver uses the current entire bound owner's
graveyard, not a list frozen at entry, and invokes the existing resolving-item
shuffle contract once even for an empty graveyard.

Additional helper-reader dependency requiring parent approval: existing
`shuffle_actions.shuffle_library` recomputes source_reference from the source's
current zone. For an actual triggered item carrying the above retained
reference, it must use that reference rather than the post-shuffle/exile one.
This candidate does NOT edit that helper or fake an event to work around it.
No claim of correct retained shuffle-cause reference until that hunk is admitted
and actual legal producer/response tests pass.

Original22 module and its assertions remain byte-identical. Compiler/helper
controls are supplementary, never certification from injected entry events.
No all-zone LKI, direct manual death, combat/SBA/keyword migration, static-receipt
persistability, or all-Kozilek support claim.
