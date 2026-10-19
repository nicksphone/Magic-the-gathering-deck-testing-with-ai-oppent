# Control Resolution Frame Consumer

The only production change is `stack_engine.resolve_top_of_stack`. It extends
existing real popped-item transport to `temporary_control_instruction` and
direct containing `effect_sequence` instructions. It never edits a copy producer.

The genuine cast producer must retain `__control_source_frame` with exactly
`stack_id`, `source_card_id`, `cast_controller`, `label`, and `source_reference`.
The reference contains nonnegative integer `incarnation` and
`zone_change_sequence` (booleans rejected). Capture the physical reference after
moving the actual card to STACK, before publication; bind announcement fields
from the returned `add_to_stack` item, never `stack[-1]`.

Copies inherit that receipt unchanged. The actual resolving identity is instead
`__resolving_item`, serialized from the actual popped item, with nested
`__resolving_item` stripped. Cast ID/controller do not replace copy ID/controller.
The scheduler must use the actual resolving actor and retained physical reference,
not current source metadata. No public schema changes are involved.

Required receipt validation happens before early pop, target pruning, bestow
mutation, replacement handling, or effect dispatch. Normal frames must match
announcing ID/controller; spell copies can retain original announcement identity.
Missing, malformed, foreign-source and unknown-copy receipts reject atomically.

The frozen dependency has no producer receipt or corrected scheduler. Eight new
genuine paid copy episodes therefore remain ordinary strict failures until that
separate dependency is supplied. No injected valid receipts certify the route.
Malformed persisted-frame tests deliberately corrupt genuine paid announcements;
these supplementary tests demonstrate rejection, not legal receipt production.
Original independent eight-episode diagnostic artifacts remain untouched.

All qualification is SQL/socket-denied. Existing activation, graveyard and search
shuffle transport modules are tested whole, without exclusions. HTTP remains HOLD.
