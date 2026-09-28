# Death-replacement boundary audit (2026-09-28)

Status: open. This is a code/data audit, not a claim that replacement effects are certified.

## Implemented follow-up

- New combat damage now delegates lethal checks to the shared SBA path; the legacy `combat_die` resume path is retained only for saved snapshots.
- Supported simultaneous death destinations are computed before any permanent leaves. The real Lorcan, Warlock Collector / Arrogant Poet case covers a subtype-scoped replacement source dying in the same batch as its target. This does not freeze multiple human choices across the batch.

## Evidence

- At audit time, `combat._resolve_damage_step` used a combat-only sequential `_remove_dead_creatures` before the shared SBA pass. The implemented follow-up replaces that new-action path with shared SBA; saved `combat_die` continuations still use their legacy resume path.
- `replacement._DIE_EXILE_RE` recognizes phrases such as `if a creature you control would die, exile it instead`. A read-only query of the local 108-row card cache found no real card with that exact wording. The cache is not the full card corpus, so this is not proof that none exists.
- Several tests in `test_prevention_replacement_edges.py` name a fixture `Rest in Peace` but substitute `If a creature/permanent you control would die, exile it instead.` The [current Scryfall Oracle record for Rest in Peace](https://scryfall.com/card/big/4/rest-in-peace) instead applies to a card or token going to a graveyard from anywhere. These tests exercise synthetic behavior, not that card.
- [Lorcan, Warlock Collector](https://scryfall.com/search?q=%21%22Lorcan%2C+Warlock+Collector%22) is a real, narrower death-replacement example: a Warlock you control would die, exile it instead. The subtype clause was missing at audit time; the implemented follow-up now covers it with a real-card regression.
- Two strict expected-failure tests now use canonical Rest in Peace text: a creature dying on the battlefield and a card discarded from hand both incorrectly reach the graveyard. They must remain expected failures until a shared graveyard-destination replacement path covers both and the rest of the engine's graveyard moves. An unexpected pass fails the focused suite.
- The 1,004-test isolated suite, full browser harness, and two-game replay pass after the SBA-wave fix. None contains a canonical, human-choice, simultaneous-death replacement fixture, so this boundary remains unverified.

## Next implementation gate

1. Replace altered named-card fixtures with exact cached/Scryfall Oracle text or explicitly synthetic text without attributing it to a real card. Do not infer coverage from a card name attached to invented wording.
2. Define event-level graveyard replacement handling, including non-death zone moves required by Rest in Peace. Keep card-specific applicability and replacement-source state explicit.
3. Preserve a frozen simultaneous event set across human choices, snapshots and restart; do not let a choice for one event silently alter another simultaneous event's applicable sources. Default destinations are now evaluated before the batch moves, but human multi-choice continuation is not yet covered.
4. Add golden real-card tests for ordinary combat, simultaneous deaths, choice/resume, exile instead of death, no false dies trigger, and APNAP ordering. Validate through the HTTP action route and deterministic replay before claiming support.

No card rules were invented or changed in this audit. Existing synthetic fixtures are left intact until the replacement model is corrected; deleting them now would remove regression coverage without adding valid real-card coverage.
