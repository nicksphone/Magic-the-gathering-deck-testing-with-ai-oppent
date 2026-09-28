# Death-replacement boundary audit (2026-09-28)

Status: open. This is a code/data audit, not a claim that replacement effects are certified.

## Implemented follow-up

- New combat damage now delegates lethal checks to the shared SBA path; the legacy `combat_die` resume path is retained only for saved snapshots.
- Supported simultaneous death destinations are computed before any permanent leaves. The real Lorcan, Warlock Collector / Arrogant Poet case covers a subtype-scoped replacement source dying in the same batch as its target. This does not freeze multiple human choices across the batch.
- A shared non-death graveyard destination operation and global "from anywhere" death candidate now support canonical Rest in Peace moves. Its entry trigger uses the stack and an exile-all-graveyards handler. Direct graveyard writes left in the engine are death branches with preselected destinations; unusual replacement interactions still need certification.
- Five older tests that called an altered or blank fixture `Rest in Peace` now use the canonical Oracle text. Other synthetic named-card fixtures remain a separate audit task.
- Live HTTP action tests now cast Lightning Bolt on Doomed Traveler under Rest in Peace and cast Rest in Peace into occupied graveyards. The first verifies that no dies-trigger Spirit appears; both verify exile destinations after SQLite controller restore. This does not cover simultaneous human replacement choices.
- The shared destination check now also recognizes the [current Scryfall Oracle opponent-card wording for Leyline of the Void](https://scryfall.com/card/dsk/106/leyline-of-the-void). Tests separate card owner from controller, exclude tokens, and destroy Leyline simultaneously with an opposing enchantment. An HTTP action and SQLite restore cover an opponent-owned spell; its opening-hand ability is a separate unsupported pregame mechanic.
- [Comprehensive Rules 704.5d](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf) token disappearance now has an SBA path: generated tokens are removed from graveyard/exile lists and marked internally ceased after their move and trigger collection. A canonical Bastion of Remembrance trigger test checks that this cleanup does not erase the dies event. Re-moving a departed token before SBA and unusual token-copy interactions remain unverified.
- [Comprehensive Rules 111.8](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf) now has a bounded pre-SBA guard for supported graveyard return, cast, dredge, escape, mass exile and discard paths. Generated token identity is stored separately from mutable types and survives snapshots, with a type-changed token/nontoken-trigger regression. Direct library/exile moves still span multiple handlers and need a transfer-level audit before this rule is certified globally.

## Evidence

- At audit time, `combat._resolve_damage_step` used a combat-only sequential `_remove_dead_creatures` before the shared SBA pass. The implemented follow-up replaces that new-action path with shared SBA; saved `combat_die` continuations still use their legacy resume path.
- `replacement._DIE_EXILE_RE` recognizes phrases such as `if a creature you control would die, exile it instead`. A read-only query of the local 108-row card cache found no real card with that exact wording. The cache is not the full card corpus, so this is not proof that none exists.
- Several tests in `test_prevention_replacement_edges.py` name a fixture `Rest in Peace` but substitute `If a creature/permanent you control would die, exile it instead.` The [current Scryfall Oracle record for Rest in Peace](https://scryfall.com/card/big/4/rest-in-peace) instead applies to a card or token going to a graveyard from anywhere. These tests exercise synthetic behavior, not that card.
- [Lorcan, Warlock Collector](https://scryfall.com/search?q=%21%22Lorcan%2C+Warlock+Collector%22) is a real, narrower death-replacement example: a Warlock you control would die, exile it instead. The subtype clause was missing at audit time; the implemented follow-up now covers it with a real-card regression.
- Two strict expected-failure tests using canonical Rest in Peace text initially reproduced incorrect battlefield-death and discard destinations. Both now pass and their expected-failure markers were removed. Additional real-card fixtures cover stack resolution, cycling, dredge milling, cost discard, 0 loyalty, self-destruction and simultaneous destruction.
- The 1,004-test isolated suite, full browser harness, and two-game replay pass after the SBA-wave fix. None contains a canonical, human-choice, simultaneous-death replacement fixture, so this boundary remains unverified.

## Next implementation gate

1. Replace altered named-card fixtures with exact cached/Scryfall Oracle text or explicitly synthetic text without attributing it to a real card. Do not infer coverage from a card name attached to invented wording.
2. Expand and certify event-level graveyard replacement handling beyond the supported "from anywhere" clause. Verify every remaining replacement family and its source/affected-player ordering against canonical fixtures, not altered named-card text.
3. Preserve a frozen simultaneous event set across human choices, snapshots and restart; do not let a choice for one event silently alter another simultaneous event's applicable sources. Default destinations are now evaluated before the batch moves, but human multi-choice continuation is not yet covered.
4. Add golden real-card tests for ordinary combat, simultaneous deaths, choice/resume, exile instead of death, no false dies trigger, and APNAP ordering. Validate through the HTTP action route and deterministic replay before claiming support.

No card rules were invented or changed in this audit. Existing synthetic fixtures are left intact until the replacement model is corrected; deleting them now would remove regression coverage without adding valid real-card coverage.
