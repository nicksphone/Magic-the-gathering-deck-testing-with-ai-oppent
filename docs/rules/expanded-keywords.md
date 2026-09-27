# Expanded keyword engine contracts

Updated: 2026-09-27. Reference: [Wizards Comprehensive Rules, September 25](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).

This is core engine coverage, not a guarantee that every card carrying these keywords works. Canonical metadata ingestion does not implement unrelated clauses in that card's Oracle text.

## Implemented foundations

- Infect turns post-prevention damage to players into poison and damage to creatures into -1/-1 counters. Wither changes creature damage only. Toxic adds poison when combat damage reaches a player. Ten poison counters cause a state-based loss. Poison persists and is exposed in player views.
- Ninjutsu is an activated ability from hand. `ninjutsu` actions require `card_id` and `return_card_id`; the latter must be an unblocked attacker. Mana and returning that creature are costs. Resolution puts the source onto the battlefield tapped and attacking the same defender. Availability continues after damage until combat ends; damage cannot resolve twice after reload.
- Annihilator creates an attack trigger, then pauses for the defending player to select the required number of distinct controlled permanents. Choices survive snapshots and emit sacrifice/death events. `choose_mechanic` actions use `card_ids` for sacrifice choices.
- Escape contributes a graveyard casting option, checking and exiling the required number of other graveyard cards. `cast_spell` uses `from_graveyard`, `cost_choice.id = escape` and optional `escape_exile_ids`. Explicit invalid selections are rejected before mana payment. Common mandatory additional costs are retained. Supported escapes-with counters are applied before entry triggers.
- Prototype contributes an alternative cost option and changes mana cost/power/toughness on the stack and battlefield. Original characteristics survive snapshots and are restored on battlefield departure or in another zone. It does not certify copy/layer interactions or all characteristic-dependent spell restrictions.
- Dredge offers an optional replacement for each individual draw when the graveyard source and enough library cards exist. `choose_mechanic` uses `choice_id = draw` to decline, or the eligible graveyard card ID to dredge. Milling replaces the draw and returns that card to hand without a draw event.
- Pending mechanic choices contain their owning `player_id` and options. Unrelated actions, phase progression, stack resolution and state-based actions cannot proceed while a resolving mechanic choice remains pending. AI selects supported choices before normal heuristics. Multi-draw and nested effect sequences resume their remaining effects without resolving the spell twice.
- Turn draws use the same draw handler as spells. Activated abilities, cycling and loyalty abilities use stack entries without emitting spell-cast triggers.

## Regression coverage

`backend/tests/test_expanded_keyword_mechanics.py` covers poison/prevention, mixed damage sources, zero toughness versus indestructible, Ninjutsu costs/timing, Annihilator ownership/duplicate selections, Escape payment and exile validation, Prototype restoration, optional/insufficient-library Dredge, multi-draw/nested continuation and snapshot recovery. Existing combat, cost, event, AI and analytics suites remain relevant integration checks. Composed effect fixtures test infrastructure rather than claiming those compositions are a real card's Oracle text.

## Remaining work

- Draw/sacrifice/cleanup choice controls and shared live face hydration are now exposed. Ninjutsu and alternative-cost action UI integration plus complete human/browser workflows remain open.
- Multiple interacting draw/death replacements need full affected-player ordering, optional decline and resumable nested-choice coverage. Current handling is not a general replacement solver.
- First-strike and ordinary damage still execute in one engine call rather than separate priority windows. Simultaneous player losses/draws need explicit adjudication.
- Damage last-known information, noncombat damage keyword interactions, keyword removal/grant layers, Prototype copies/restrictions and arbitrary escaped-condition clauses need additional fixtures.
- Escape with optional kicker, Commander ninjutsu, unusual printed keyword formatting, and deep strategic evaluation of these actions are not certified.
- Morph/Manifest, Suspend, Discover, Craft, Mutate, Banding and complete Battle protector/defense/transformed-casting rules remain unfinished.

No rule or card data was changed to force a matchup win rate.

## Validation notes

The frontend production build passes. A seeded Mono Red Aggro versus Dimir Control BO3 completed two logical games, 30 total turns, with no timeout or determinism failure; results are recorded in `docs/plans/baselines/2026-09-27-expanded-keywords-replay.json`. This is a regression smoke test, not evidence of balance, expert AI or coverage of every new mechanic.

The earlier 753-test keyword validation used local image assets. The later `d68641b` repair tracks the generic fallback; 758 tests passed with fresh Python dependencies and initially empty database/image cache. Cleanup validation is recorded separately in `CHANGELOG.md`; these checks do not certify browser or all-card rules completeness.

Final backend result: **753 passed**, 113 deprecation warnings, 86.34 seconds. The expanded-keyword test module contains 21 regressions. Python compilation and `git diff --check` also pass.
