# Human legend keeper and retained replacement continuation

Scope: SBA legend producer/new completion helpers and two narrow engine pending
branches. No API schema, training, UI, AI, keyword, events or Jason death-function
changes. The standalone human path uses the existing graveyard plan/cause/entry
ABI; Jason0484 is not a consumed dependency. Automatic-only groups keep the prior
fixed-first path. In mixed groups the automatic actor's first keeper is retained
while every human group receives an explicit choice.

## Keeper and replacement flow

Duplicate groups are captured in active-player/nonactive-player order. Each human
chooses exactly one keeper per same-name group, without moving any loser. All
human keeper groups finish before any replacement choice or departure. Groups
retain exact controller, owner, incarnation and zone sequence, and are checked
against the current complete duplicate-group membership at every completion.
A leave/reenter object with the same ID is stale, not the retained source object.

After all keeper choices, candidate plans for EVERY loser are captured. Human
competing replacement source IDs are selected explicitly, including multiple
sources with the same destination. Every prior plan and all current candidates
must remain identical through later choices and cold restoration. Once all
choices exist, every static cause is prepared before the first simultaneous LBF.
All losers' battlefield membership is removed before individual retained-plan
execution. Only actual graveyard entries publish dies events; library/exile
replacements never publish false dies. Entry identity and owner destinations
belong to the shared executor, not a second hand-written zone mover.

If a human competing-source continuation is disabled, completion rejects before
mutating pending state, logs, zones or events. No library/exile default is chosen.
This also rejects an implicit first-source choice when every offered source has
the same destination. Automatic actors retain the existing same-destination policy.
Invalid or stale pending choices do not silently regenerate new source references.
The existing paused-resolution helper transfers its continuation metadata to the
next pending choice and resumes it after the final keeper/replacement completion.

## Exact existing-contract metadata

Generic legal moves spread pending mechanic fields. These two NEW top-level keys
therefore appear in whole legal views for `kind = legend_keeper`:

- `legend_group_index`: integer selecting a retained group.
- `legend_context`: object with the following JSON-safe retained context.

`legend_context.groups` is a list of:
`{player_id: int, name: lower-case string, card_ids: list[string],
references: {card_id: [incarnation: int, zone_sequence: int, owner: int]}}`.
Only public battlefield group members are included, never hand/library contents.
`legend_context.keepers` maps decimal group-index strings to exact keeper IDs.
`legend_context.plans` maps loser IDs to chosen plan objects (initially empty).
`legend_context.candidates`, present after keeper collection, maps every loser ID
to its exact offered list of plan objects.
A plan object has fields `card_id`, `origin`, `owner`, `controller`, `incarnation`,
`sequence`, `destination`, `replacement_source_id`, `source_incarnation`,
`source_sequence`, `reveal_shuffle`. Zones are strings; references are integers
or null; the replacement ID is a string or null; reveal_shuffle is boolean.

Replacement pending uses existing keys `event = die_zone`, `player_id`,
`target_card_id`, `options = [{source_id, name}, ...]`, plus
`resume_kind = legend_keeper_die` and the same server-retained `legend_context`.
Public replacement legal moves retain their existing flat shape and do not spread
this context. Existing resolving-item/continuation fields are preserved by the
existing resume helper, not accepted from action payloads.

Neither retained key is actor-authoritative. The only new workflow inputs are
existing typed actions `choose_mechanic` with exactly one `card_ids` entry and
`choose_replacement` with an exact offered `replacement_source_id`. HTTP extra
context/index fields are forbidden; direct trusted-core extra fields are ignored.
No handler reads keeper/group/plan context from the submitted action.

The training lookup-intent display/context allowlist is outside this patch's
scope. It may reject these new mechanic metadata keys until a separate narrow
consumer extension is qualified. This is NOT UI/training workflow completion.

## Evidence boundaries

Original55 is byte-identical. Its two unrelated full-canonical Kozilek draw-four
assertions remain ordinary red; no skips, xfails or weakened Oracle/assertions.
All original keeper continuations pass on this product. Canonical Isamaru,
Progenitus, Rest in Peace and Act of Treason payloads remain unchanged.

Paid episodes use explicit funded mana, not natural mana-development claims.
Real HTTP process-restart tests run seed, keeper and replacement in three distinct
processes against owned local SQLite; invalid actions and idempotent replay retain
root/controller/SQL snapshots. Memory/file HTTP and actor-private view controls
are independent of trusted core stale and simultaneous-board diagnostic seams.
Multi-group/three-copy/foreign-owner simultaneous boards and source roundtrips
are explicitly controlled setups, not claimed as naturally executed entries or
causal source-removal HTTP episodes. No new Oracle or fake stack/event is created.

Actual consumer probe result on the final frozen engine, both seats: whole engine
move + explicit card_ids is rejected with `Mechanic choice contract cannot carry
requested fields`; state stays byte-equivalent. The existing
`observe(seat).pending_choice.prompts[0].hint` omits both new metadata keys, and
its projected hint + explicit card_ids DOES materialize the intended existing
typed action through lookup_intent without changing root state. Wrong-seat
materialization rejects. Thus the existing projected prompt path works; only
whole-engine/API-view echo compatibility needs a separate narrow context guard
extension. Any such extension must compare both metadata keys with authoritative
pending state before stripping them, never infer keeper IDs or trust supplied
plans. This patch deliberately does not extend training or UI code.
