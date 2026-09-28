# Combat lifelink gain-event boundary (2026-09-28)

Status: common gain-life trigger path repaired with focused real-card tests. Combat gain replacements and nested human-choice continuation remain open.

Verification: 1,108 backend tests passed with 1 strict expected failure in an isolated source/database copy. Frontend lint/build/unit checks passed. No browser-specific lifelink scenario or broad matchup matrix was run for this backend-only increment.

## Rules evidence

The [Magic 2015 release notes](https://magic.wizards.com/en/news/feature/magic-2015-core-set-release-notes-2014-07-07) explain that each lifelink creature dealing combat damage produces a separate life-gaining event, but one creature damaging multiple recipients simultaneously produces one event. Ajani's Pridemate is the real trigger fixture; Vampire Nighthawk supplies lifelink.

## Repair

- `_combat_damage_step` accumulates actual dealt damage per lifelink source, applies each source's gain before state-based actions, and emits one `life_gain` event per source. The existing trigger-staging path combines those gain triggers with combat damage and death triggers before stack ordering.
- Four fixtures cover unblocked gain, one source damaging two blockers, two sources damaging a player, and a locked lifelink controller. They assert life totals and Ajani's Pridemate trigger counts. Existing life-lock tests also verify damage dealt to a locked player can grant an unlocked opponent lifelink.

## Remaining gate

- Combat life increments still bypass `effects.handlers.gain_life` replacement selection. A strict expected-failure regression using real Alhammarret's Archive text records the current 22-life result where 24 is required. Routing a human replacement choice through combat requires preserving all simultaneous damage results, gain events, state-based-action waves and trigger staging across a snapshot. Do not mark general lifelink/replacement fidelity complete on this event patch.
- Extend golden tests to gain doublers, gain-prevention effects, damage dealt to multiple kinds of recipient, first/double-strike substeps, lock changes during combat and APNAP ordering after death replacements.
