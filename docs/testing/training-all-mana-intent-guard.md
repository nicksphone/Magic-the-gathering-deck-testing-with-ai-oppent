# All Mana Intent Field Guard

Separate increment over frozen public consumer ae1646 and legacy guard a4cb6.
All four mana lookup_intent routes check requested fields BEFORE complete_action,
using a local four-entry map of the public API Action model classes and their
actual model_fields. No private AI catalog, duplicated parameter schemas or
helper/API/raw-action/engine edits.

An explicit display allowlist retains known public hint metadata including
required_choices. Fields outside the specific action model and display allowlist
reject even when null; ability_index/output_bundle/selected payment fields are
not display on legacy actions. Typed selections retain their actual schema fields.
Presentation cannot authorize omitted authoritative choices. Unknown requests
are tested to reject before normalization is called.

The original twelve sibling-route red tests now pass normally, unchanged; funded
raw28, Sphere index/fuel8, fixed mixed4 and basic8 controls remain unchanged.
New both-seat tests cover all four models' presentation/simple actions, unknown
requests, null unsupported legacy selections and misleading display flags.
Whole actual public typed intents and strict AI reservations remain composition
tests. Raw API defaults, encoded actions, land tap-only rules and executor internal
None behavior are untouched. No GUI/full-hand performance/NN/expert-data claim.
