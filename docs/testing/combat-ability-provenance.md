# Combat ability provenance and stack timing

## Implemented increment

Recognized printed combat restrictions now use the same supported all-ability
loss query as mana, triggers and statics. This covers land-gated attack/block
permission, unconditional can't-attack/can't-block, mandatory attack/block,
attack/block-alone wording, only-flying blocking, unconditional unblockability,
minimum blocker counts and additional/any-number blocking capacity. Effective
keywords remain separate: a later Menace/Decayed grant can still restrict blocks
without restoring lost printed Oracle text.

Mogg Flunkies' actual combined attack-or-block-alone wording is recognized.
Rejecting a lone direct attack no longer taps the creature. Duplicate blocker
IDs cannot act as multiple creatures for direct declaration checks. Unlimited
blocking capacity no longer inherits the previous arbitrary 99-attacker cap. These fixes
are shared by live checked actions and existing AI legality helpers, not card-name
exceptions.

Bushido, Rampage and Flanking now produce ordinary, counterable triggered stack
objects rather than immediate stat changes during declaration. Simultaneous
block events are collected before APNAP placement. Attacker/blocker first-event
markers prevent "becomes blocked"/"blocks" instances from repeating per pair;
Flanking remains once per qualifying pair and ability instance. Numeric
Bushido/Rampage values and instance counts are preserved instead of treating
Scryfall's unique keyword-family metadata as another instance.

Rampage determines its bonus when its trigger resolves, using current creatures
blocking that attacker; subsequent departures do not recompute the resolved
bonus. Original recipient incarnations and known blocker incarnations survive
snapshots. Flanking is non-targeted, persists independently of its source and
does not follow a blinked blocker. Suppression before declaration prevents
intrinsic triggers; ability loss after a trigger was stacked does not cancel it.
Checked combat damage cannot bypass a live stack.

Player-shroud/hexproof sources and recognized battlefield spell-counter
protection also honor supported ability loss. A spell's own can't-be-countered
text remains a stack characteristic, not a battlefield ability to be suppressed.

Small-board Master block search settles announced triggers before damage and
no longer drops a potential Bushido trade solely on pre-trigger base stats.
Combat keyword boards can enter existing bounded attack search earlier. Search
uses detached state; it does not claim optimal play or a general learned policy.

## Canonical evidence and rules

`backend/tests/fixtures/combat_ability_provenance.json` retains complete canonical
Scryfall rows, IDs, URLs and retrieval dates for 17 cards, including Hand of Honor,
Craw Giant, Benalish Cavalry, Stifle, Lightning Bolt, Topiary Stomper, Mogg
Flunkies, Palace Guard, Aegis of the Gods, True Believer and Prowling Serpopard.
Acceptance applies to the specific clauses above, not every ability on every
row (for example, Colossus' paid untap or Stomper's full search is not certified
by this increment). Fixture boards and explicit gained-keyword/new-blocker
state setups are not fabricated tournament decks or evidence of balance.

Wizards' [Comprehensive Rules](https://magic.wizards.com/en/rules), September 25,
2026: 509.1 (declaration restrictions/requirements), 509.3a/509.3b/509.3d (event
multiplicity), 603.3b (APNAP), 702.23 (Rampage), 702.25 (Flanking), 702.45
(Bushido), 113.7a (stack independence), 400.7 (new objects) and 514.2 (cleanup).
The official text is retained with test evidence on RCHFiles.

## Validation

Golden tests cover both seats, before/after resolution stats, genuine Stifle and
Lightning Bolt responses, instance counts, multi-blocker timing, original-object
binding, suppression/cleanup, player targeting, counter protection and SQLite
restore through HTTP. A direct-effect fixture explicitly tests a new blocker
joining before Rampage resolution. The AI decision fixture checks a profitable
Bushido block and unchanged authoritative snapshot.

The first focused failures were fixture issues (the shared add helper does not
own a player stack zone; rejected HTTP writes restore detached state). They were
repaired without weakening expectations. Updated historical synthetic combat
fixtures now require a stack and priority resolution before their buffs appear.
Final-source validation on October 2, 2026: **151 focused checks** and **2,809
isolated backend tests** pass (303 deprecation warnings; 311.27 seconds for the
full suite). Frontend lint/unit/build and the full Chromium harness pass.
An additional canonical 101-attacker/Palace Guard stress probe verifies actual
unlimited assignments, snapshot restore and one-block capacity after suppression.
Twelve logical seat-balanced smoke games each repeat twice with no reported
drift, timeouts or anomaly labels. Failed/superseded and final checks, canonical
fixtures, official rules and closed source/browser copies are retained on
RCHFiles under `diagnostics/combat-ability-provenance/20261002T054017Z/`.
Reused dependencies and DOM-driven browser testing do not establish
clean-install or visual acceptance. Alpha UI redesign remains deferred.

## Known Limitations and Next Upgrades

- Full ability provenance, arbitrary non-keyword grants, conditional restrictions,
  dependencies and comprehensive type/color/text layers remain incomplete.
- This increment covers declaration events. General effects that add/remove
  blockers, combat-reference incarnation tracking across every route, and all
  mandatory-combat optimization/choice combinations still need broader fixtures.
- The existing AI search has small-board bounds and does not enumerate every
  multi-block-capacity or conditional block sequence. Larger/complex boards and
  strategically timed responses still need decision-quality and latency evidence.
- Corpus-wide replay/restart, long-session deployment and operational release
  gates remain open. Small smoke samples are repeatability checks, not proof of
  universal Magic rules, expert AI or forced matchup win-rate bounds.
