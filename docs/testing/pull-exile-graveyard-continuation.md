# Closed Exile-To-Graveyard Continuation

Scope: the complete normalized instruction `Put target face-up exiled card into its owner's graveyard.` only. No general exile recursion, modal/compound expansion, or partial reward. The candidate-prefix guard returns an explicit unsupported instruction for non-complete bodies.

## Selection and Execution

`exile_card_targets` offers actual, face-up, non-departed exile cards across owners. A request requires exactly one scalar `target_card_id`. The existing announced-target reference bundle is captured at announcement and validated at resolution. Actor/caster is not substituted for affected owner. Protection and existing checked target/reference handling are retained.

The one new transport literal asks the stack resolver to attach the actual popped `StackItem` as `__resolving_item`. Compose by set union with independently owned literals; do not overwrite the stack function. The actual-frame post-resolution capture and finish/resume logic are unchanged.

Shared native graveyard-entry plans determine destinations. One plan executes through the existing committed-entry/cause executor. Multiple plans, including equal destinations, pause without selecting a default. The affected owner must choose an offered replacement source.

## Retained ABI

`pending_replacement_choice.resume_kind = exile_graveyard_entry`.

The pending record retains `player_id` (affected owner), `event = graveyard_entry`, `target_card_id`, `stack_id`, `continuation_controller`, and `options = [{source_id, name, destination}]`.

Its `exile_graveyard_context` has exactly:

- `version`: integer 1.
- `resolving_frame`: deep copy of the real popped StackItem dictionary.
- `source_kind`: `physical_spell` or `copied_spell`.
- `physical_source_reference`: `{incarnation, zone_change_sequence}` for a physical source, otherwise null.
- `target_references`: the existing complete announced-target reference bundle.
- `candidates`: mapping of offered replacement source ID to the complete native plan receipt, with origin/destination serialized as zone strings.

The existing stack post-hook supplies `resolving_item`. Before preparing a cause or clearing pending, completion validates the two frame copies, actual source/target references, affected owner, complete live plan map, complete offered options, and explicit chosen source. A copied spell uses its captured copy characteristics and survives a real paid counterspell removing the physical original. It does not inherit the physical source liveness condition.

No client-supplied retained context is accepted. Raw typed actions remain `{type: choose_replacement, replacement_source_id}`. Existing legal display fields `event`/`replacement_name` continue through the existing training display-intent adapter. No schema, training, API, UI or serializer change.

## Qualification Boundary

Funded canonical positions are not natural gameplay. Post-setup actions are checked and actually paid, with native stack frames/events and JSON snapshot restoration. No HTTP server or SQLite qualification was performed; both were forbidden before application imports.

Final original18 + new56: 72 ordinary passes and 2 ordinary failures. All 18 original cases pass unchanged, including paid Cremate -> Pull causal ABA and source Unsummon independence. New supported continuation controls pass: both owners, explicit library/exile plans, duplicate/wrong/stale/malformed rejection, paid copies KEEP/retarget with countered original, face-down paid foretell exclusion, scalar target validation and committed entry without false creature death.

The two strict failures are real Final Judgment exile bookkeeping: the card enters exile but its native reference does not advance. This handler is outside scope and untouched. Lawful actual Unmake resolves and advances the reference, enabling the genuine competing-choice episodes. No failure is hidden by skip/xfail/adaptation.

Eleven complete pure neighbor modules: 199 passes. A separately retained twelve-module attempt has 241 passes and 2 SQLite-denied HTTP setup errors; it is not a green gate or HTTP qualification.
