# Public Defender Leaf Audit

TESTS ONLY over frozen55eb + strategic-leafad498/b86 + characterization5877.
No production changes, natural replay, tactical stubs, fake events or new Oracle.
This audits defender block declarations, not the earlier20 attack witnesses.

Two blocker families: official full Sheoldred, the Apocalypse and Torrential
Gearhulk, plus official Monastery Swiftspear as the small attacking creature.
Untouched full official Scryfall responses/provenance inherited from7627 under
fixtures/empty_hand_attack_witness; their checksum verification runs on import.
Funded retained positions are expressly not natural gameplay. Creature/land setup
uses full canonical payloads, then every attack/block/priority/damage continuation
is a real checked action. Libraries are private, not manually revealed or copied
into agent knowledge. Both seats have real legal defender views before choosing.

120 cases = ten labels x two seats x two blocker families x three groups.
Labels: Aggro, Burn, Control, Tempo, Midrange, Ramp, Drain, Aristocrats, Tokens,
Tribal. These are invocation labels, not ten independently expert-certified AIs.

Safe40: Sheoldred/Gearhulk legally kill a attacking Swiftspear and survive with no
life loss, mana tap, or spent held Counterspell. AI chose block in all40 cases.
Current-lethal-trade40: the4/5 attacker would immediately win if unblocked; each
cross-family block trades both actual creatures and prevents lethal. AI blocks40.
Race40: both large creatures would trade on a block. Taking the current hit
preserves the blocker, whose checked next-turn attack wins in the explicitly
no-intervening-play branch. AI chose no block40. Actual draw/Sheoldred draw triggers
are resolved rather than invented/skipped. Future draws and responses remain
unknown to policy; this group records conditional forecast/outcome, not a claim
that every no-block is unconditionally correct against arbitrary unseen cards.

Each record captures snapshot, whole legal actions, actor-projected view and legal
moves, actual decision/reason, passive forecast observations, checked alternatives
and actual chosen prefix. Snapshot replay chooses the same action; roots remain
byte-equivalent. Analysis verifies library identities are masked in all120 views.
Only test code wraps next-board forecast and delegates unchanged product behavior.

Actual: new120 pass108.92s; seven whole combat/resource/heuristics/recurring/info/
strategic-pass/score-reuse modules263 pass2warnings23.01s. No skips/xfails/deselections.
No new adequacy failure observed. Response-rich boards, public activated blockers,
complex trample/damage allocation and unsupported animation remain unqualified.
The unchanged2 strict Mutavault failures and original historical ledgers are not
retested, adapted, or claimed closed by this new audit. The original20 desired
attack cases are not duplicated or rerun here. No natural-game strength claim.
