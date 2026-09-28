# Death-replacement boundary audit (2026-09-28)

Status: open. This is a code/data audit, not a claim that replacement effects are certified.

## Evidence

- `combat._resolve_damage_step` calls the combat-only `_remove_dead_creatures` before the shared state-based-action pass. The combat path processes lethal creatures sequentially and can pause at the first human replacement choice. The shared SBA path has separate lethal batching and choice handling. Those paths can disagree about simultaneity, which sources remain on the battlefield, and when death triggers are collected.
- `replacement._DIE_EXILE_RE` recognizes phrases such as `if a creature you control would die, exile it instead`. A read-only query of the local 108-row card cache found no real card with that exact wording. The cache is not the full card corpus, so this is not proof that none exists.
- Several tests in `test_prevention_replacement_edges.py` name a fixture `Rest in Peace` but substitute `If a creature/permanent you control would die, exile it instead.` The [current Scryfall Oracle record for Rest in Peace](https://scryfall.com/card/big/4/rest-in-peace) instead applies to a card or token going to a graveyard from anywhere. These tests exercise synthetic behavior, not that card.
- [Lorcan, Warlock Collector](https://scryfall.com/search?q=%21%22Lorcan%2C+Warlock+Collector%22) is a real, narrower death-replacement example: a Warlock you control would die, exile it instead. The current regular expression does not cover that subtype clause.
- The 1,004-test isolated suite, full browser harness, and two-game replay pass after the SBA-wave fix. None contains a canonical, human-choice, simultaneous-death replacement fixture, so this boundary remains unverified.

## Next implementation gate

1. Replace altered named-card fixtures with exact cached/Scryfall Oracle text or explicitly synthetic text without attributing it to a real card. Do not infer coverage from a card name attached to invented wording.
2. Define event-level graveyard replacement handling, including non-death zone moves required by Rest in Peace. Keep card-specific applicability and replacement-source state explicit.
3. Converge combat lethal handling onto the shared SBA death path. Preserve a frozen simultaneous event set across human choices, snapshots and restart; do not let a choice for one event silently alter another simultaneous event's applicable sources.
4. Add golden real-card tests for ordinary combat, simultaneous deaths, choice/resume, exile instead of death, no false dies trigger, and APNAP ordering. Validate through the HTTP action route and deterministic replay before claiming support.

No card rules were invented or changed in this audit. Existing synthetic fixtures are left intact until the replacement model is corrected; deleting them now would remove regression coverage without adding valid real-card coverage.
