# Printed and conditional ward forms

Historical ward-form milestone. The later [player-counter increment](player-counters.md)
implements the named-counter ward X/gain/scaling boundary; the dynamic-cost
warning findings below describe this milestone's parent and original scope.

This increment fixes shared Oracle parsing, not whole-card interpretation or
professional AI certification. All eight fixture rows come from the local
canonical card-data cache; no names, printed costs or abilities were invented.

## Supported Increment

- Printed comma-separated keyword lists retain ward, including Flying/ward,
  Vigilance/trample/ward and nonmana sacrifice costs. Other list entries must
  match the card's keyword metadata; later activated/triggered instructions do
  not become a permanent's printed ward.
- Named self-grants match the current card name, its short name, or "this
  creature/permanent". Unconditional grants and the explicit tapped/untapped
  condition are supported. Current tap state is checked when targeting occurs;
  losing the grant afterward does not delete an already-triggered ability.
- Costs retain Oracle capitalization in human labels. Matching remains
  case-insensitive, and existing mana/life/discard/sacrifice payment handlers
  remain authoritative.
- Unsupported-cost detection scans inline and granted forms as well as printed
  lists and card faces. Minthara's experience-counter X cost now warns instead
  of silently passing this known-gap check; it is not implemented as zero.

## Evidence

The published parent `6764b35` yields no ward instances for Rith or untapped
Iymrith and no unsupported-cost warning for Minthara. The new canonical tests
exercise printed extraction, real casts and payments for both seats, loss of a
conditional grant after triggering, snapshot restoration, tapped-source
nontriggering, effect-body exclusion and case-preserving labels.

Final-source checks: **2,152 backend tests pass** (292 existing deprecation
warnings, 231.82 seconds); **53 focused ward tests pass**. Frontend lint,
TypeScript/Vite build, boundary/unit checks and the full Chromium harness pass,
including ward controls, real backend restart and natural AI/human BO3 flows.

Eight seeded, seat-paired games across Dimir Control/Tempo, Tokens/Ramp,
Midrange/Drain and Tribal/Burn repeat identical reported results and complete
logs across sixteen executions, without timeout or cast/target rejection. One
normal Spell Pierce resolution cannot collect its optional two-mana payment
from Counterspell's controller; the countered spell and continued game confirm
that this is not a rejected cast. This offline built-in smoke does not exercise
every new canonical fixture. [Machine-readable evidence](ward-forms.json).
Tests run in independent tracked-source copies, never the live match database.
The initial browser run exposed lowercased payment labels; that regression was
fixed rather than changing the expected UI label. The superseded backend run
was interrupted after this correction and is not counted as a successful gate.

## Known Limitations and Next Upgrades

Dynamic X definitions, experience-counter acquisition/anthems, arbitrary self
and global conditions, granted temporary ward, competing payment restrictions
and full ability-suppression/dependency layers remain open. No working ward
clause certifies a whole card: Rith's excess-damage trigger, Iymrith's draw
ability and Sauron's other abilities need separate semantic coverage. Keyword
lists without canonical keyword metadata are not inferred speculatively.

Pre-cast/multiple-ward strategic resource planning still needs expansion; this
increment does not change AI policy. Small seeded games and existing browser
flows verify regressions and repeatability, not deck balance, all-card support,
new-card end-to-end UI certification or seasoned-player strength. The previous
optional timed-dump native crash remains an unresolved independent diagnostic
issue; passing standard checks does not fix it.

Ward's existing triggered-ability behavior follows the official
[Introducing Ward explanation](https://magic.wizards.com/en/news/card-preview/introducing-ward-2021-03-25).
This increment changes recognition, not that timing model.
