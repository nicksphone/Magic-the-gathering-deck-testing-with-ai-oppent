# Selected Modal Targets

Only `targeting.validate_cast_targets` and
`oracle_effects.infer_effect_from_oracle` change. Choose-one `mode_text` and
one-element `mode_texts` now establish the same printed selection. Previously
per-mode target validation could read an uninitialized `selected` variable.

Scalar lowering now retains its selected `mode_targets` packet, as list lowering
already did. Without it, draw lost its recipient and a counter could select the
unannounced top spell instead of the explicitly chosen lower one. Modes, targets
and payments are not inferred. Null unused selectors remain valid; two non-null
representations, unknown/duplicate/excess modes and mismatched packets reject.

## Evidence

Independent **18 complete modules passed 844 tests in 160.49 seconds**, with no
failures, errors or skips: 97 new tests, 369 native target/mode controls and 378
AI/draw controls. All 2,650 backend inputs match before/after. Native SQLite,
socket and subprocess operations were denied before project imports; the passing
cohort recorded no denials. Real media helpers wrote only to owned scratch.

Both seats use unchanged full canonical Archmage's Charm data and actual paid
checked casts. Draw reaches the chosen self/opponent recipient. Paid lower-stack
counter cases remove that spell, preserve the unselected upper spell, then
actually resolve the upper spell's draw. Announcement, payment, protection and
original-root controls remain. The original worker's 87-test prefix is unchanged;
ten parent controls cover the nullable-selector review correction.

Original red stages and the initial media-write guard failure are retained.
Eight initial parent tests used raw `model_dump()` rather than the actual API's
`model_dump(exclude_none=True)` bridge. Their failed logs/preimage are preserved;
corrected controls retain only the known unused mode selector as `None`. No
protected announcement-reference validation was weakened for that test assumption.

## Limits

All bytes/AST outside the two functions match the parent. Schemas, costs,
`action_validation.py`, captured references and saved-game formats are unchanged.
These are pure engine/AI checks, not HTTP/browser tests or a certificate for every
printed modal effect. Execution positives concern Charm's draw/counter modes;
existing multiselect controls retain their original behavior. Full raw-null
container dumps are not claimed as canonical native engine inputs.
