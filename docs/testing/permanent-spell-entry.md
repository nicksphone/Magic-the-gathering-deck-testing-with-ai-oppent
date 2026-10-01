# Permanent Spell Entry Counters

## Implemented Scope

Normal resolving permanent spells prepare supported initial counters while the
recipient remains on the stack. Existing scalar replacement/prohibition logic
sees its projected controller without treating incoming global abilities as
battlefield sources. Choices persist through snapshots; entry, counters and
entry triggers commit once after the choices finish, before state-based actions.

The packet supports printed planeswalker loyalty (including the selected modal
face), compleated life-payment adjustment, intrinsic Saga lore, printed X +1/+1
entry counters, supported escape counters and the existing one-shot entry-counter
record. Same-kind X/one-shot counters aggregate before scalar modification.

Read Ahead offers the controller a starting chapter before entry. On the entry
turn, only the chapter matching the resulting lore count can trigger; this also
applies to later lore events that turn. Later turns use normal crossed thresholds.
Consequently doubling chosen chapter two on a three-chapter Saga produces four
lore and no chapter trigger, allowing final sacrifice at the next SBA check.
See [current Wizards rules 702.155 and 714](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.pdf).

The UI renders the choice for either human seat. AI currently chooses chapter
one to retain future chapters; it does not yet optimize Read Ahead for the board.
Coverage diagnostics warn about incomplete Read Ahead entry routes and phasing.
The Phasing of Zhalfir is a canonical choice fixture, not a claim its phasing
chapter effects are implemented. Card fixtures retain canonical source IDs.

## Verification

- 2,382 isolated backend tests pass (229 warnings, 184.16 seconds). The full
  tracked-source copy matched all modified backend files by byte comparison;
  focused tests created only its disposable database, never the live database.
- 146 focused counter/Saga checks and 44 entry/modal-face checks pass. A modal
  planeswalker regression verifies both entry loyalty and original identity/no
  loyalty after destruction. The diagnostic fixture now expects the newly
  reported phasing gap; the old duck-typed stack fixture uses a real StackItem.
- Frontend lint, unit contracts and TypeScript/Vite build pass. Full Chromium
  passes, including seat-two pre-entry chapter selection, one exact chapter,
  recovery/restart, sideboarding and natural human/AI BO3 flows.
- Eight seeded seat-paired games repeat complete results/logs across sixteen
  executions without timeout. This is repeatability evidence, not a balance
  estimate or professional-AI benchmark.
- Graphify AST refresh passes: 7,430 nodes, 18,568 edges, 320 communities.
Completed evidence is on RCHFiles under project diagnostics
`permanent-spell-entry/`; earlier failing runs are preserved separately.

## Known Limitations and Next Upgrades

[Shared entry routes](entry-routes.md) now extend this packet to created tokens,
permanent-spell copies, supported graveyard/library returns and green-creature
hand placement. Special opening and unusual exile-return routes remain open.
General projected continuous/copy
characteristics, arbitrary entry replacements, simultaneous multi-kind ordering,
and cast-linked one-shot expiry semantics remain unfinished. [Compleated ordering
and entry commit](entry-replacement-order.md) now use shared scalar choices without
retroactive incoming global bans. Recipient projection
currently preserves existing types/face and changes controller only. Arbitrary
Saga chapter effects, phasing, gained/suppressed chapter abilities and deeper AI
chapter selection remain open. No universal rules or professional-AI certification
is implied by the bounded tests or small replay sample.
