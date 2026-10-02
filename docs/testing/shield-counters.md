# Shield counters and effect destruction

## Rules and scope

Shield counters now have rules-defined consequences rather than only a stored
number or an AI weight. These effects are independent of printed abilities and
are not keyword counters. The implementation follows Comprehensive Rules 122.1c,
510.2 and 615.12, and the [official New Capenna release notes](https://magic.wizards.com/en/news/feature/streets-new-capenna-release-notes-2022-04-20).
The September 25, 2026 [Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
used for this work are retained with test evidence on RCHFiles.

- Positive damage to a shielded permanent removes one shield counter and is
  prevented. Zero/negative damage and off-battlefield objects do not spend one.
- Damage that cannot be prevented still removes one counter but retains actual
  damage consequences. Ordinary amount-based prevention shields are not spent
  on unpreventable damage. A supported free damage-reduction replacement is not
  prevention and still applies.
- Simultaneous combat damage from multiple blockers uses one shield effect and
  removes one counter. Each first-strike/regular combat step is a separate event.
  The event context is scoped to the actual state, not another match or AI copy.
- Supported single-target and bulk effect-driven destruction share the same
  indestructible/shield checks. Indestructible makes destruction impossible and
  does not spend a shield. Shields do not regenerate, tap or remove from combat.
- Lethal damage/deathtouch, zero toughness, sacrifice and exile do not gain an
  extra shield-based survival check. Zone resets clear counters and timestamps.
  Partial removal preserves the original timestamp; the final removal clears it.
- Creature, planeswalker and other permanent damage use the same shield effect.
  Actual damage retains loyalty/lifelink/infect/wither/deathtouch consequences;
  prevented damage does not produce them. The shared creature damage-result
  operation now records deathtouch for noncombat as well as combat damage.

## Ordering and AI

The scalar permanent-damage replacement adapter offers the counter effect as a
stable virtual source (`shield-counter:<permanent ID>`), alongside supported
static reduction/prevention sources. This is an effect identifier, not a new card.
Human stack damage and the existing spell-damage batch path use the affected
controller's choice and durable continuation. Used sources are not applied again
when a chain resumes; snapshot/SQLite restore preserves the virtual source and
remaining amount. If a free reduction reduces damage to zero, the shield is not
spent. Shield-protected destruction does not ask for a later die-zone replacement
which will not occur.

Canonical Lashknife Barrier data exposed an important distinction: its current
Oracle clause reduces creature damage; it is not a prevention effect. This
bounded clause now participates even when damage cannot be prevented and does
not affect noncreature permanents. The engine recognizes the generic
source-controller/creature scope of combat-damage prevention prohibitions, tested
with actual Questing Beast data; it does not unlock the opponent's sources or
noncombat damage.

Automatic resolution and the AI's offered permanent-damage choice apply free
static reductions before spending a shield. Decision tests compare authoritative
snapshots before/after ranking; no opponent hand/library inspection is needed.
This is a rules-backed resource preference, not expert tactical certification.

## Validation

`tests/fixtures/shield_counters.json` records actual Scryfall payloads and IDs for
Lashknife Barrier, Questing Beast and Urza's Armor; existing canonical fixtures
supply Grizzly Bears and the seed supplies Lightning Bolt/Ugin. Instructions
placed directly on a test stack are explicitly synthetic effect fixtures, not
invented card text or competitive decks.

`tests/test_shield_counters.py` exercises both seats, multiple counters and damage
amounts, unpreventable damage, bulk creature/artifact/enchantment destruction,
indestructibility, non-destruction zone changes, effective deathtouch, actual
multi-block combat, first-strike boundaries, private choice ownership, AI
preferences, snapshot continuation and HTTP/SQLite restoration.

## Acceptance evidence

Final-source checks on October 2, 2026:

- **2,614 backend tests passed**, with 285 deprecation warnings, in an isolated
  source checkout/database. Superseded runs/failures are kept separately.
- **274 focused checks passed**, with four deprecation warnings, including both
  seats through real HTTP action, rejection and SQLite restoration routes.
- Frontend lint, contract tests and TypeScript/Vite build passed; the existing
  sequential Chromium suite passed **104 scenario assertions**.
- Four-deck/six-pair seat-balanced replay: **12 logical games**, two repeatability
  executions per game, zero reported determinism failures/drift or timeouts.
  The smoke run did not produce a full per-decision anomaly trace or establish
  broad balance/AI strength.
- Evidence is retained on RCHFiles under
  `diagnostics/shield-counters/20261002T020938Z/`, including official rules,
  canonical fixtures, final and superseded logs and isolated checkout archives.
  Installed dependencies were reused; no clean-install or visual/pointer
  certification is claimed. Live services remain LAN-bound to `0.0.0.0`.

## Known Limitations and Next Upgrades

- Full affected-player ordering across simultaneous combat packets, protection,
  amount-based shields, damage redirection and counter-conversion replacements
  is not completed. Combat currently uses the deterministic shared automatic
  reduction/counter order. The mechanics inventory retains an explicit shield
  competing-prevention fidelity flag; a metadata match is not certification.
- General regeneration and other competing destruction replacements, partial
  prevention source allocation and arbitrary Oracle replacement clauses still
  need a unified resumable event model. This milestone does not certify them.
- Counter-removal watcher triggers and arbitrary resource-counter spending or
  movement remain open. Removing a shield here does not prove those mechanics.
- Decayed/Exalted multiplicity, keyword variants, full ability suppression,
  broader layer dependencies, strategic AI evidence and operational gates remain
  on the finish plan. UI redesign remains deferred.
