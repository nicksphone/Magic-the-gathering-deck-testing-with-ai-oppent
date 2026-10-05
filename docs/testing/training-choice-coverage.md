# Complete Training Choice Coverage

Parent composition with the published combat query batches passes **172 checks**
across choice coverage, environment, dataset, action contract, autoplay safety
and combat query performance. This is a bounded adapter/legality gate, not
neural training or evidence of seasoned-player decision quality.

This bounded adapter qualification uses the authoritative existing action models
and `checked_action`, not a replacement rules engine or an exhaustive action
enumerator. It does not certify expert play or introduce model dependencies.

## Consumer Boundary

`encode_action` / `decode_action` preserve the full canonical normalized action,
including mode-specific targets, explicit X=0, ordered lists and payment lists.
`lookup`, `step` and encoded identifiers stay strict: move-display fields are not
executable parameters. `lookup_intent` is a separate convenience boundary using
the parent-owned `ai.action_contract.complete_action` helper, then ordinary
`lookup`. Display metadata such as card_name/mana_cost/cost_options/target_hints
is filtered by the helper's actual action-model field map. Missing authoritative
targets, cost IDs, selected cards, X or malformed nested parameters are never
chosen by the adapter. No new action schema or AI normalizer is supplied here.

`prompts` remains a partial legal decision surface. Mechanic hints identify the
appropriate payload: `choice_id` for draw/land-entry/saga-entry, `damage_assignment`
for combat damage, and `card_ids` for existing list-selection mechanics. Counts,
ranges, options and order semantics come from the engine. A payload of the wrong
kind is rejected even where an engine legacy `.get(..., [])` might otherwise
permit an empty selection. Trigger ordering is an explicit complete permutation;
trigger targets and optional effects carry the actual stack ID; replacement
choices carry the actual replacement source ID. These describe consumer choices,
not private engine continuations.

## Actor-Private Observations

The acting seat's `pending_choice.prompts` contains the same allowlisted partial
descriptions as `prompts()`. The nonacting seat receives only the pending kind
and owner, never owned options, inspection rows, continuation payloads or prompt
data. No new top-level observation fields are introduced. RNG, replay logs,
starting decks, future observations and effect continuation packets remain private.

Current engine inspection rows authorize the actor to inspect nonselectable
misses as well as selectable hits (Recruitment Officer). They are added to that
actor's `known_cards` so downstream public aliases can cover every inspected ID;
the opponent does not receive them. Hidden information is not reconstructed from
snapshots or opposing legal moves. Views, prompts, masks, intent lookup and trial
execution operate on copies; rejected actions preserve all root fields, pending
continuations, logs, payments and RNG. Returned prompt objects are detached.

## Qualified Actual Families

The new tests retain tactical positions using existing fixture metadata, never
rewrite names, costs, types or Oracle text. Both seats are exercised. The fixed
builtin provenance remains the trusted envelope; these added canonical tactical
instances are fixture positions, not new naturally dealt deck distributions.

| Family | Actual qualified choices |
| --- | --- |
| Cryptic Command | Two announced modes, per-mode card and stack targets, empty nontarget mode payload, actual counter/return resolution |
| Abrade | Single explicit mode and actual artifact target/resolution |
| Sickening Dreams | Explicit X=0 and X=2, exact selected discard costs, actual payments and symmetric damage |
| Opt / Impulse | Private partition/selection, subsequent ordered bottom-card permutation, actual draw/resolution continuation |
| Recruitment Officer | Paid inspection, eligible hit versus unselectable misses, explicit decline, alias coverage and private visibility |
| Reclamation Sage + Soul Warden | Simultaneous trigger permutation, target choice, optional accept, actual destruction after continuation |
| Graveyard Trespasser | Ward pay/decline tokens, subsequent exact discard selection and original-spell continuation |
| Hardened Scales + Doubling Season | Actual counter-replacement ordering and affected-controller continuation; original engine computes the result |
| Stinkweed Imp + Opt | Draw replacement uses explicit choice_id, actual five-card dredge rather than a guessed draw |
| Cleanup | Explicit exact-count hand discard from an actual end-step transition |

Each replay fixture checks encode/decode equality, trial lookup and mask root
immutability, an invalid choice's rejection, then restores at the current boundary
and executes both encoded and decoded actions to equal complete snapshots. These
snapshots include private engine fields and are evaluator-only, never policy input.
Adversarial tests change unauthorized hand/library identities, opponent list,
private RNG and logs without changing actor observations or prompts. Existing
adapter and dataset privacy/terminal/origin/grouping checks are also run.

## Remaining Coverage And Limits

- The API encoding is parameterized, not a finite action menu. Arbitrary modal,
  target-distribution, combat assignment and ordered-list combinations are not
  exhaustively enumerated or certified by these retained fixtures.
- Existing canonical face selection, resource/hybrid casting, attack/block and
  mana choices retain their earlier adapter checks; this patch does not claim
  new exhaustive qualification of those mechanics, cycling, loyalty X or every
  scalar land/saga-entry variant.
- Resource/hybrid payments on mana abilities remain blocked where the current
  ManaAbilityAction has no fields to express them. No API schema is expanded.
- Trigger hint generation emits all permutations only through six simultaneous
  triggers; larger groups offer a representative hint. A complete proposed
  permutation is still encoded and checked by the engine, not inferred here.
- Only the engine's current authorized hints enter pending observations. They
  are not a universal action mask, a full feature-state sufficiency claim or a
  way to choose unresolved future cards at cast time.
- Changed observations and adapter source change engine_hash; old snapshots
  cannot be restored under this revision. Preserve old evidence and start a
  fresh run rather than relabeling its provenance.
