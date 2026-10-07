# Intrinsic-Mana Combat Leaf: Stage 1

`AIAgent._complete_strategic_combat_leaf` can finish an already announced,
response-free public combat against noncreature effective lands when their full
reminder-stripped functional Oracle text is empty, effective type line is present,
authoritative basic subtype grants mana and the current tap-mana query is positive.
There is no Basic-label, card-name or card-color heuristic, score bonus or added
search depth. Tapped readiness is ignored for classification, ability loss is not.

The existing hand/graveyard/exile, stack/pending, effectful response, own unsupported
combat and public creature/crackback guards remain. Null Oracle is unknown. Empty
text coerced upstream from absent data cannot be distinguished from true empty
Oracle by this gate; this is not a blanket metadata readiness certificate. Wastes,
functional mana-only text and non-subtyped/unknown lands remain conservatively out.

Full canonical raw Underground Sea and Tropical Island cases cover both seats,
Sheoldred and Gearhulk, current checked damage, snapshot replay and root purity.
Canonical Dryad Arbor, functional Mutavault and both Bala Ged faces remain unknown.
Explicitly labeled metadata damage and resolved layer receipt probes test null,
types, card color and all-ability suppression, without inventing Oracle or claiming
paid spell causality. The actual paid Flashback/Bolt and crackback controls are
unchanged. No SQL/network operations are required by this qualification.

The separate adaptation of `test_public_combat_boundary_audit.py` changes only the
80 dual cases' old helper-is-None characterization to a nonnull leaf expectation.
All other desired attack, legal damage, reservation/root purity and 12 response
controls are retained. The 40 inert-graveyard desired attacks remain strict RED;
no stage2 grave inventory work or full132-green claim. Immutable original tests
and all failed ledgers stay archived. Earlier natural BEFORE/AFTER actions remain
2610 normalized entries byte-identical, not evidence of natural strength gain.
