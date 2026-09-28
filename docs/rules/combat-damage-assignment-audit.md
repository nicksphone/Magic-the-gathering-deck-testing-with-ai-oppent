# Combat Damage Assignment Audit

Current rules source: [Magic Foundations update bulletin](https://magic.wizards.com/en/news/announcements/foundations-update-bulletin). Damage assignment order was removed in 2024. A controller may divide a creature's combat damage among the creatures it is fighting without assigning lethal damage first, except that trample still requires lethal damage assigned to all blockers before excess reaches the defender.

## Verified Current Behavior

- `rules_engine/combat.py` applies damage automatically on entry to a combat-damage step. A blocker shared across attackers now has one effective-power budget per step; this prevents illegal duplicated damage.
- A multiply blocked attacker assigns damage in blocker-list order, generally assigning lethal damage to each before moving on. A blocker shared across attackers assigns all its damage to the first attacker. Both defaults are legal assignments in ordinary cases, but neither gives the controller the choice required by current rules.
- `RulesEngine.next_step` enters combat damage and resolves it before priority. That timing is correct only after all required damage-assignment decisions have been collected. The first-strike and regular steps need separate assignments.
- `choose_mechanic` currently accepts card IDs or one choice ID. It has no validated numeric distribution. The UI therefore cannot display or submit a damage split, and AI cannot compare legal alternatives.

## Required Implementation

1. Before applying combat damage, compute all combatants, their effective power, eligible recipients, first/double-strike membership and trample constraints from one stable pre-damage state. Do not reveal or apply any damage while a required assignment remains pending.
2. Add a durable pending combat-assignment record with the acting controller, source creature, eligible recipients, power budget and damage-step identity. Expose typed legal moves and a bounded action containing a non-negative integer amount for each recipient. Reject missing, extra, duplicate, wrong-seat, stale-step and over-budget assignments without changing state or SQLite.
3. Collect choices in active-player-then-defending-player order where both sides must assign. Resume the same damage step only after all assignments are valid. Deal that step's combat damage simultaneously, then run state-based actions and triggers before priority. Repeat the process in the regular step when first/double strike created two steps.
4. Render per-recipient numeric controls from legal moves for the human controller, including combatant names, current effective stats and a visible budget. Keep hidden information hidden. AI should evaluate bounded legal allocations using board value and lethal/race consequences, not a fixed blocker-list order.
5. Snapshot and restore each pending assignment and accumulated choice. Test API, AI-vs-AI, human-vs-human, browser response windows and deterministic replay from the same seeds.

## Acceptance Fixtures

- A real 3-power attacker blocked by 2/2 and 3/3 creatures may put all 3 damage on the 3/3, rather than being forced to damage the first blocker. Neither creature dies before simultaneous combat damage is applied.
- Palace Guard blocking Llanowar Elves and Elvish Mystic assigns exactly its 1 power total; its controller can choose either attacker. Lifelink and deathtouch use the selected amounts, not duplicated source power.
- Trample cannot assign excess to a player, planeswalker or battle until all blockers have lethal damage assigned, accounting for deathtouch and damage already marked.
- First-strike and regular damage assignments are separate choice windows. A legal response between them may change recipients, power, toughness or keyword eligibility as current rules permit.
- Invalid or stale assignments return structured 4xx with identical authoritative memory, snapshot and database state. A pending choice survives backend restart and yields the same later game state and replay hash.

This is a rules-fidelity release gate, not a cosmetic UI task. The current deterministic fallback remains intentionally documented until these fixtures pass through live HTTP and browser controls.
