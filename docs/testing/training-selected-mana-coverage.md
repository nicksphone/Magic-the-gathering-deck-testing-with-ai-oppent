# Selected Immediate Mana Choices

This incremental consumer patch depends on the separately owned executor and
subtype-cost parser patches. It is not deployable without those dependencies.
The preceding 168-check diagnostic patch remains an immutable historical gate;
its assertions that selected payments are unrepresentable are superseded here.
Final composed counts and source hashes belong in the archived qualification
report, not in an assertion that the action schema alone supports execution.

## Caller / Executor Contract

`ManaAbilityAction` retains `card_id`, `ability_index`, and `color`, and adds:

- `payment_choices`: existing `PaymentCards`, exact discard/sacrifice ID lists.
- `hybrid_choices`: existing `HybridChoices`, one branch for each cost symbol.
- `output_bundle`: exact complete positive BASE vector with strict integer
  entries 1..100000, at most six W/U/B/R/G/C keys.

The immediate engine branch forwards these three fields unchanged as keyword
arguments to `activate_mana_ability`. There is no X parameter. The executor owns
production, replacements, resource reservations and trigger processing.

Other-card resources must be selected explicitly and completely. Source-bound
self-sacrifice has no alternative card choice and may retain its fixed cost.
Hybrid payment branches are always explicit. `output_options` is a list of
`{color, output_bundle}` pairs; `base_output_bundles` is their deduplicated list
of complete maps. Explicit color must be a positive BASE anchor. If the same
color admits multiple different vectors, the bundle is mandatory. It selects
production before replacements/trigger bonuses: BR under Reflection emits B2/R2,
under Sphere emits C1; an explicit C anchor for BR is invalid. Omitted bundle
retains the executor's legacy final-color replacement routing (including C).
Non-offered vectors reject instead of being dropped or coerced.
Consumer legality is still `checked_action`, on a full engine copy.

Internal automatic planner calls retain `None` defaults, existing reservations,
excluded sources and protected life. This does not grant consumers an automatic
other-card resource selection. Legacy generic-stack or tap routes are not a
training payment-choice workaround.

`lookup_intent` uses the shared `complete_action` model map: all three new fields
survive normalization. Only enumerated mana display fields are discarded;
requested unsupported fields, including X, are rejected instead of lost.
Strict encoded actions, lookup and step retain strict schema validation.

## Canonical Qualification Surface

`test_training_selected_mana.py` and `test_selected_mana_http.py` exercise:

- Phyrexian Tower: either actual selected other creature, both seats, immediate BB.
- Skirk Prospector: either actual selected other Goblin or the source, both
  seats, immediate R; non-Goblin, opposing and wrong-zone selections reject.
- Graven Cairns: B/R hybrid branches, exact BB/BR/RR output, both seats/anchors.
- Flooded Grove: G/U hybrid branches, exact GG/GU/UU output, both seats/anchors.
- Bog Witch: paid B activation, explicit chosen own-hand discard, both seats.
- Missing, partial, duplicate, extra, foreign, wrong-zone, invalid source/index/
  color/resource, malformed/non-offered vector and unaffordable payment rejection with
  exact root snapshots unchanged; a filterland cannot fund its own activation.
- Actor-private hints, hidden identity/order permutation byte equality,
  reversible public resource aliases, and lookup/intent/encoding parity.
- Grim Haruspex death-draw into an actual Stinkweed Imp draw/dredge pending
  boundary, nonactor privacy, snapshot restoration and deterministic replay.
- Production checked HTTP rejection, successful payments, and SQLite restoration
  before and after activation. SQLite is disposable source-local, never NFS.
  `reserved_card_ids` is rejected as an unsupported HTTP field; actual planner
  reservation semantics are a separate executor/automatic-payment gate, not a
  consumer-selectable reservation parameter.

Tower, Prospector, Haruspex and draw-choice metadata are existing repository
canonical fixtures, with no Oracle edits. Filterland fixtures are complete raw
canonical payloads supplied by the executor agent, including their source URI:

| Fixture | SHA-256 |
| --- | --- |
| `training_selected_mana/graven-cairns.json` | `b7bce54a43e1b6ab0ba5e68dfa335ffac829d578ae197de8075e2a198db46f94` |
| `training_selected_mana/flooded-grove.json` | `673c919a68c7c6c19f6cf9bf53f60acfc5851fca1315113b9efff385ecc15755` |

Training checks prohibit database/network connections. HTTP checks prohibit
external network connections and use the isolated checkout's local database.
Finished patches, logs, hashes and source evidence are archived on verified NFS.

## Remaining Boundaries

The earlier branch-only artifact remains staged/immutable; this later third-field
delta requires the confirmed frozen mixed executor. It is not exhaustive mana
choice coverage. Springleaf Drum's chosen
other-creature tap cost is outside this contract/executor expansion. It does not
add X-input production, arbitrary output partitioning, snow-output selections,
unsupported costs, or unrestricted Oracle interpretation. Existing engine
computed counts/power output are not X-input choices and require no fabricated
X action. Only actual offered options are selectable.
Secondary triggered-mana type choices (for example Mana Flare on a mixed base),
entry-color and any-color trigger selections remain separate executor/contract
limits. Selecting a primary `output_bundle` does not announce those choices.

Observations and hints contain the actor's own resource candidates and public
battlefield information, never opponent hidden identities. Raw internal IDs are
trusted engine handles, not model features; external datasets must use public
episode aliases and keep reverse mappings private. No neural dependencies,
expert-data claims or learned-policy competence claims are introduced.

## AI Boundary

Existing `AIAgent.choose_action` excludes standalone `activate_mana_ability`.
Consequently missing explicit mana materialization is not evidence that live AI
is broken. Spell-cost automatic planning must retain its `None` defaults and
resource reservations and needs composed canonical interaction qualification.
If standalone immediate mana becomes an AI proposal, the separately owned
policy needs a dedicated materializer using `cost_text`, own-resource candidates
and hybrid symbols. The generic activated-resource helper currently expects
`mana_cost` / `payment_options` and defaults to `ability_kind='activated'`; mana
specialization must use `ability_kind='mana'` and the actual ability index.
This patch makes no AI-agent changes or broad live-AI qualification claim.
Strict actual AI reservation tests also cover Deadly Dispute/Tower and Goblin
Grenade/Prospector. The composed spell caller may lack reservation propagation;
the archived qualification report records any failing gate rather than masking
it with xfail or claiming this separate consumer patch fixes that caller.

## Human UI Boundary

The existing battlefield mana button sends only source/index/color. It cannot
select these newly accepted resource/hybrid fields. Training-only enrichment of
`activation_costs` and `hybrid_symbols` is not public UI coverage: the separately
owned public mana views/UI need actual required-choice hints and controls or an
unsupported notice before human release. Checked HTTP success is not a claim of
manual GUI completeness. Current main's frozen diagnostic still masks selected
mana payments until the caller/environment and executor patches are composed.

The targeted mana fixtures retain only a canonical land in the actor's initial
hand (and add the actual canonical test spells/resources). A separate full-hand
Prospector run stalled and was stopped within its bound; its log is preserved.
Minimal tactical success is not full built-in-hand performance qualification.
