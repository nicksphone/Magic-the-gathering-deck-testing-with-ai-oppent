# Spell and Ability Counterability Scope

This repair replaces substring checks that incorrectly gave activated abilities their source spell's protection and treated battlefield-only protection as intrinsic to the source spell. Canonical Scryfall fixtures cover Allosaurus Shepherd, Destiny Spinner, Stifle, Counterspell, Llanowar Elves, Cultivate and Lightning Bolt.

The [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt) distinguish spells and abilities in sections 112 and 113. Default battlefield scope is described in 113.6; a card's own uncounterability operates on the stack under 113.6g. Countering a stack ability does not move its source permanent (701.6).

## Supported behavior

- The shared `spell_cant_be_countered` reader recognizes standalone self clauses naming the spell or using "This spell".
- Standalone battlefield clauses protecting spells you control are checked at counter resolution. Supported scopes are one printed color or card type, or an "and" union of two such scopes. Allosaurus Shepherd's green-spell scope and Destiny Spinner's creature/enchantment scope are regression-covered.
- Ordinary and taxed counters use the same rule check. A protected spell remains a legal counterspell target; its protection prevents the counter operation rather than rejecting the cast.
- Spell-only source text no longer protects a stacked activated ability. Explicit structured ability-protection flags are retained.
- Copies use their saved spell characteristics and their own controller. Removing the physical original does not erase intrinsic protection; another player's battlefield protector does not protect the copy.
- Snapshot restore and a human Stifle browser path exercise these rules without moving the ability's source permanent.

## Known Limitations and Next Upgrades

These tests do not certify conditional protection, protection granted by temporary effects or mana spending, subtype combinations, ability-removal/dependency layers, arbitrary ability-specific Oracle protection, or AI valuation of an otherwise ineffective counter with useful secondary effects. Broader counter grammars, Fuse and long-run strategic quality remain on the active plan. No card-name branch implements these fixture cards.
