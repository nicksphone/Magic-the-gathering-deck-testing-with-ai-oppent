# Battlefield-entry choice boundary (2026-09-28)

Status: bounded pay-2-life land-entry repair implemented with focused rules/snapshot, browser/API and seeded replay tests. The defect and inventory below describe the pre-repair baseline. General replacement ordering and broad replay acceptance remain open.

## Rules boundary

The [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt) treat "as/enters" modifications as replacement effects (614.1c-d). A choice needed to modify entry is made before the permanent enters (614.12a); paying life requires enough life and is prohibited by a can't-lose-life effect (119.4, 119.8). Multiple applicable entry replacements need their ordering rules (616). The choice is not an ETB trigger and must not create a priority window after entry.

## Reproduced defect

An isolated 60-card fixture using the checked-in Sacred Foundry Oracle seed played the land from hand at 20 life. `RulesEngine.legal_moves` offered only `{"type":"play_land","card_id":...}`; `take_action(..., reject_invalid=True)` left the player at 20 life and the land untapped. Its printed entry clause requires either paying 2 life before entry or entering tapped. This is not merely an AI valuation problem.

## Entry-path inventory

| Path | Current behavior | Land relevance |
| --- | --- | --- |
| `rules_engine/engine.py` `play_land` | Applies only unconditional tapped text via `apply_land_entry`; no conditional choice | Hand, exile permission, and modal land face |
| `effects/handlers.py` `put_land_from_hand` | Uses effect payload's tapped flag, bypasses printed entry clause | Land from hand via an effect |
| `effects/handlers.py` `_place_searched_card` | Assigns tapped flag directly | Search-to-battlefield can find a land |
| `effects/handlers.py` `return_permanent_from_graveyard_to_battlefield` | Assigns untapped directly; also does not emit an entry event | Generic permanent return can be a land; event gap is a separate finding |
| `effects/handlers.py` `topdeck_put_permanents_battlefield` | Assigns untapped directly | Chosen permanent can be a land |
| `rules_engine/stack_engine.py` permanent spell resolution | Direct battlefield append | Normally nonland spells; share a future entry contract without enabling land casting |

Control changes and cleanup control restoration move a permanent between controller lists without a zone entry; do not treat them as ETB events. Ninjutsu and creature-only topdeck/return handlers cannot enter a land in their current admitted paths. The table identifies callers, not proof that every possible card reaches every path.

## Repair gate

1. Define one pre-entry decision/result contract in application code. It must carry the entering object's source/owner/controller, effect-imposed tapped state, applicable replacement options, choice owner, and continuation. Resolve the choice before the zone move and before ETB events. Keep SQL as storage only.
2. Route the land-capable paths above through it. A forced tapped entry must remain tapped even if a player pays for an otherwise-untapped option; effects that say "may" must not auto-pay or silently grant an untapped entry.
3. Make the human choice visible and resumable through API/UI snapshots. AI must select a legal option based on life and whether immediate untapped mana matters; it must not always spend life or always decline.
4. Add golden tests for hand/exile/modal land play, effect entry from hand/library/graveyard, exactly 1/2/20 life, can't-pay-life effects, multiple replacements, simultaneous entries, ETB trigger ordering, snapshot resume and replay equality. Rejected or stale choices must leave full state unchanged.

Do not close this item on a one-card or play-land-only patch. The supported wording now uses a shared land-capable entry path; original duals remain in built-in lists while other conditional entry families and replacement ordering are uncertified.

## Bounded repair evidence

- `backend/rules_engine/entry.py` recognizes the canonical pay-2-life/tapped Oracle clause by wording and land type, not a named-card branch. It checks available life before payment, preserves forced-tapped effects and stages multi-entry choices before cards move zones.
- Eight focused tests cover direct and exile land plays, low-life legality, AI paying only for immediately usable mana, hand/library/graveyard/topdeck effect entries, snapshot resume, two simultaneous entries and life-zero state-based-action timing. The isolated suite passed 1,098 tests; a later timestamp adjustment passed 54 focused entry/token/Oracle-effect tests.
- The loopback Chromium harness passed paid/tapped land-play buttons and a pending effect-entry decision through the real action API, then completed the existing recovery and BO3 scenarios.
- One seeded Burn versus Dimir Control AI game played Sacred Foundry, paid 2 life, finished without timeout and produced the same log hash on rerun. This is replay consistency for one case, not broad strategic or rules certification.
