# Combat Intent Consumer Audit

Test-only evidence on the frozen wASfmI source-only copy plus the qualified
trigger-order and small-choice guards. No production change is included.

## Result

The complete 72-case audit finished with 32 sole rejection failures and 40
ordinary passes, 123 warnings, exit 1, in 63.54 seconds. No skips, xfails,
deselection or contradictory acceptance witnesses. This is NOT a green gate.

All 32 failures are `lookup_intent` accepting unsupported top-level
`unknown_choice`, `targets`, `payment_choices` or `defender_id`, including null,
for both seats and both combat families. Strict `lookup` and real HTTP first
reject the same requests; HTTP returns 422 with full root/controller/SQLite
dump unchanged. The consumer filters these keys through `complete_action`
because combat is absent from its pre-normalization public-model guard.

The 40 passes comprise 16 malformed nested/duplicate assignment rejections,
12 independent whole-view/action/HTTP resolution and restart controls, and
12 actor-private observation/prompt byte-invariance controls.

## Public Contracts

`AttackAction`: `type=attack`, `attackers` ID list, `attack_targets` attacker-ID
to defender-string map, ordered `bands` ID lists, optional `hybrid_choices`.
`BlockAction`: `type=block`, `blocks` attacker-ID to blocker-ID-list map,
optional `hybrid_choices`. These are flat typed maps/lists, not nested
defender/payment objects. Nested object/null replacements and duplicate
band/block entries reject through lookup, intent and actual HTTP.

Canonical controls use unchanged existing fixture card fields: Grizzly Bears,
Ugin, the Spirit Dragon (deliberate split player/planeswalker attack),
Benalish Hero plus Invisible Stalker (explicit band), Propaganda (four mana
for two attackers), Wall of Glare (two attackers blocked by one wall), and
resolved War Cadence (one payment per distinct blocker, not per pair).
Both seats execute exact assignments, replay encoded versus typed actions,
restore pending boundaries, complete real HTTP combat and restore outcomes.
Opposing hidden hand/library identity permutations and order changes produce
identical aliased observation/prompt bytes. Public combat identities remain
fixed; this is not a claim of all-action alias coverage.

## Narrow Proposal, Not Implemented

Add public `AttackAction` and `BlockAction` to the existing `lookup_intent`
pre-normalization map only, with qualified display metadata, preserving all
15 existing guards and raw API/engine/helper behavior. Reject unknown requests
even null before completion; never infer attackers, bands, defenders, blocks
or payment branches from suggestions.

Observed raw attack display keys: `options`, `defenders`, `banding_attackers`,
`attack_taxes`, `attack_costs`, `declaration_limits`. Raw block display keys:
`attackers`, `blockers`, `legal_blocks`, `blocker_capacities`,
`target_requirements`, `block_taxes`, `block_costs`, `declaration_limits`.
In block views, `attackers` is a presentation list of `{id,name}` objects,
NOT the authoritative attack ID list. Any approved follow-up must qualify that
shape and reject chosen-ID/object/null reinterpretations; do not blindly
allow arbitrary metadata or silently swallow a requested assignment.

No canonical hybrid combat tax was invented: current typed hybrid support
and grammar-boundary fixtures are not evidence of a real canonical selectable
hybrid combat payment. Generic costs above are real canonical mechanisms.
No exhaustive combat, policy competence or deployment claim is made.

## Historical Draft

The first new-test draft finished 36 failures/36 passes in 59.23 seconds:
the same 32 consumer failures plus four test-only `CardInstance.damage`
AttributeErrors. Its source/logs remain archived. After terminal, only the new
control assertion was corrected to inspect `counters['__damage_marked']`;
the entire 72-case audit then ran with fresh local SQLite as reported above.
