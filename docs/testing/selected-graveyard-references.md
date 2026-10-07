# Selected Graveyard Object References

This incremental repair is qualified over the frozen B inventory source, not
the moving parent composition. It changes three runtime seams only:
`events._remember_trigger_target`, the internal selected-trigger validation in
`effect_casts`, and explicit new-target selection for copied graveyard-casting
triggers in `keyword_actions.finish_mechanic_choice`.

The existing `__trigger_target_reference` is a JSON list of two nonnegative
integers: `[object_incarnation, zone_change_sequence]`. It belongs to the
authoritatively selected `target_card_id`. It is captured at automatic/human
selection, retained through copying and optional pending snapshots, and never
rebuilt during resolution or admission. Explicitly choosing a new copy target
captures that new object; KEEP preserves the original seal even after reentry.

Trigger provenance fields are checked by presence, not truthiness. Partial or
malformed markers, missing legacy selected-trigger seals and malformed/stale
seals cannot authorize a cast. Existing optional pending may still decline and
complete. Generic unsealed permissions and AI preselection probes remain
unchanged. This does not change ordinary flashback/escape admission, schemas,
compiler coverage or source-departure rules. A Gearhulk leaving the battlefield
does not cancel its already-triggered permission.

Qualification includes both seats, actual funded paid Gearhulk casts and ETB,
automatic/human selection, paid Cremate/Unsummon responses, paid Lithoform
Engine ability copying and KEEP/new-target choices, optional acceptance/decline,
native snapshot roundtrips, root-pure invalid choices, and malformed references.
All cards use complete inherited official raw fixtures with checked hashes.
Funded retained setup is not natural play. Graveyard exile/reentry probes are
trusted native transitions, not claimed paid causal ABA episodes. Faulted
metadata is derived from real pending production, never invented pending.
No HTTP, SQL or process-restart qualification is claimed under this pure grant.

The original two B desired ABA assertions remain byte-unchanged and now pass.
B coverage receipts remain structural: this reference repair does not certify
all supported instructions or all graveyard permissions.
