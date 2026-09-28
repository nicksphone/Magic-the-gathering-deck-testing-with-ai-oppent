# Combat lifelink gain-event boundary (2026-09-28)

Status: common gain-life trigger and supported combat gain-replacement paths repaired with focused real-card tests. Broader cross-event ordering remains open.

Verification: the initial event-only increment passed 1,108 backend tests with 1 strict expected failure. The follow-up replacement fix passes 1,113 backend tests in an isolated source/database copy, frontend lint/build/unit and the full Chromium harness. The browser harness did not exercise a lifelink-specific scenario; no broad matchup matrix was run for this increment.

## Rules evidence

The [Magic 2015 release notes](https://magic.wizards.com/en/news/feature/magic-2015-core-set-release-notes-2014-07-07) explain that each lifelink creature dealing combat damage produces a separate life-gaining event, but one creature damaging multiple recipients simultaneously produces one event. Ajani's Pridemate is the real trigger fixture; Vampire Nighthawk supplies lifelink.

## Repair

- `_combat_damage_step` accumulates actual dealt damage per lifelink source, applies each source's gain before state-based actions, and emits one `life_gain` event per source. The existing trigger-staging path combines those gain triggers with combat damage and death triggers before stack ordering.
- Four fixtures cover unblocked gain, one source damaging two blockers, two sources damaging a player, and a locked lifelink controller. They assert life totals and Ajani's Pridemate trigger counts. Existing life-lock tests also verify damage dealt to a locked player can grant an unlocked opponent lifelink.

## Remaining gate

- Combat gains now route through the shared life-gain replacement handler, with a serialized continuation for multiple human replacement choices. The former strict Archive expected failure now passes. Focused tests cover separate gains, human choice through a snapshot, and a dying lifelink source whose state-based death waits for the choice. Do not infer general life-gain/replacement fidelity from these bounded examples.
- Extend golden tests to gain doublers, gain-prevention effects, damage dealt to multiple kinds of recipient, first/double-strike substeps, lock changes during combat and APNAP ordering after death replacements.

## Cross-effect follow-up

Real Nefarious Lich and Boon Reflection Oracle clauses now cover a human choice between gain-to-draw and doubling, including a second lifelink source waiting while the first draw replacement resolves. The selected order changes the draw count; no gain-life trigger fires when Nefarious Lich replaces the gain. A separate double-strike snapshot regression verifies Archive doubles each damage window exactly once. These focused cases do not establish arbitrary replacement-chain or APNAP correctness.

Validation after the cross-effect fixtures: 1,115 backend tests pass in an isolated source/database copy. The preceding frontend lint/build/unit and full Chromium harness pass; no new browser scenario specifically exercises these cards.
