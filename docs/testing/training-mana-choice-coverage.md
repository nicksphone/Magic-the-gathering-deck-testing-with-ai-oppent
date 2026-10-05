# Training Mana Choice Boundary

This adapter change is parent-qualified against `433b230` with 304 passing tests
across the mana-choice, choice, environment, dataset, action-contract, simulator
safety and selection-policy suites. It changes only the adapter and targeted
tests, with accompanying documentation. It is
not a mana-engine/API expansion or a claim of learned/expert competence.

## Hard Boundary

Full resource/hybrid mana selection **remains unsupported** under the permitted
scope. `api_contracts.ManaAbilityAction` carries card_id, ability_index and color,
but no payment_choices, hybrid_choices or targets.x_value. The engine's immediate
mana branch forwards only those fields to `activate_mana_ability`; its immediate
handler has no selected resource/hybrid payment arguments. Its cost routines can
choose resources/branches internally, but the adapter cannot bind a caller's
selection to that execution without engine/API changes.

Using generic `activate_ability` instead is not a safe immediate-mana bridge: the
generic execution branch adds a stack item, while an immediate mana ability must
produce mana now. Some such proposals have no legal generic engine hint at all.
This patch does not rewrite Oracle text, reorder hands to manipulate automatic
payments, monkeypatch execution, fabricate cards or duplicate mana production.
Actual admitted execution remains `checked_action` on a copy.

Verified parent evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/training-mana-433b230/`.
No live database or user match was modified by qualification.

## Implemented Safeguards

- Mana prompts now carry `encoding_supported` and `unsupported_choices`. The
  latter names resource discard/sacrifice lists, hybrid branches or X where the
  current immediate contract cannot represent them. These are capability
  diagnostics, not authoritative chosen parameters or permission to execute.
- Unsupported mana cost choices remain rejected even when the base action is
  syntactically encodable. Encoding/roundtrip is not proof of action legality.
- `lookup_intent` still uses the parent helper for display normalization, but
  first rejects requested resource/hybrid/X parameters on immediate/legacy mana
  intents. They cannot be silently filtered away and then claimed as executed.
- Legacy nonland taps cannot bypass unsupported payments or silently select
  among multiple currently productive abilities for the same color. Consumers
  must supply an explicit ability_index using the typed immediate action.
- Ownership is checked before inspecting legacy source options; opposing hidden
  payment availability is never a capability oracle. Generic stack proposals
  for engine-classified immediate mana abilities are also rejected.

No hidden hand candidates are synthesized or exported. Offered own-source hints
and public board-dependent outputs are reused; whole-root read/rejection
immutability and actor-private observation boundaries remain intact.

## Canonical Qualified Mechanisms

The tests consume existing repository fixture rows unchanged, with trusted
retained positions and matured creatures rather than invented card definitions.

| Mechanism | Bounded actual checks |
| --- | --- |
| Sol Ring / Llanowar Elves | Explicit source/index/color, immediate fixed production, tap costs, no output stack |
| Basal Thrull | Explicit source-bound self-sacrifice (no separate resource selection), immediate two black mana |
| Cabal Coffers / Cabal Stronghold | Explicit paid ability index and output color; fixed generic pool payment and counted Swamp production |
| Chromatic Star | Paid tap/self-sacrifice, selected W/G output, actual departure-trigger stack, pending draw replacement and deterministic restoration |
| Phyrexian Tower | Basic C production remains usable; arbitrary creature-sacrifice B ability explicitly unsupported; raw, intent and legacy bypasses reject |
| Urborg + Cabal Stronghold | Printed paid B versus granted tap-only B requires explicit index rather than legacy automatic selection |

Accepted actions roundtrip through canonical encoding, trial lookup and an actual
restore/replay to identical full snapshots. Invalid requests, masks and lookups
leave every root field, payment, log and RNG unchanged. Hidden library/hand
identity/order, opposing deck list, private RNG and log perturbations do not
change actor observations/prompts. The targeted tests forbid database and network
connections. Existing choice, adapter, dataset and shared-helper checks are also
included in combined qualification.

## Unsupported Domains And Next Ownership

Resource discard/sacrifice of chosen OTHER cards, hybrid/phyrexian branches,
explicit immediate mana X and mana mechanisms not recognized by the existing
engine remain unsupported. Chromatic Sphere's combined draw instruction, Skirk
Prospector's unrestricted other-Goblin sacrifice, targeting mana-like abilities,
arbitrary mixed output bundles and every possible spending restriction are not
newly certified here. Fixed source self-sacrifice is not general resource-choice
support. Paying an engine-fixed generic activation cost is not hybrid selection.

Hybrid/discard/X grammar probes are unit checks of capability classification,
NOT newly invented game-card fixtures or successful execution qualifications.
This patch has no canonical hybrid-mana success fixture and claims none.

Closing the actual selection gap requires coordinated ownership of the public
mana action fields and engine forwarding/immediate-cost path. Explicit selected
payments must survive normalization and be passed to the authoritative payment
code; merely adding a private adapter envelope cannot achieve that. Those files
are intentionally unchanged by this delta. Old evidence/snapshots retain their
original engine hashes; do not relabel them under the changed adapter.
