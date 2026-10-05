# Graveyard Casting Methods And Permission Opportunity

## Implemented

The shared cost collector evaluates each supported casting method using its
announced characteristics. Prototype uses its chosen mana cost and mana value;
bestow uses Enchantment, not Creature, for a per-permanent-type permission.
Ordinary and limited graveyard permissions remain subject to ownership, timing,
suppression, costs and source-local usage. Explicit stale cost choices reject.

Prototype color now follows its chosen mana cost in all casting zones, and the
stack-departure path restores printed color, mana cost and stats. Casting without
paying mana may choose prototype; this does not offer bestow or an alternative
mana cost alongside the free-cast alternative. Rules grounding:
[The Brothers' War mechanics](https://magic.wizards.com/en/news/feature/the-brothers-war-mechanics)
and [official bestow rules](https://media.wizards.com/2021/downloads/MagicCompRules%2020210202.pdf).

AI materialization compares equivalent method/payment options using other cards
in its own graveyard. It preserves a scarce type/source allowance when another
permission can cast the current card and only the scarce allowance permits a
known follow-up. This is a bounded availability heuristic, not an exhaustive
affordability, turn-sequence or optimal-play search. Explicit selected costs are
not overridden; hidden opposing cards are not read.

Legal cost views expose optional source keys and mana-value ceilings through the
validated frontend boundary. Existing cost selectors permit deliberate human
prototype/bestow and permission choices for either seat.

Goring Warplow is a complete raw Scryfall download with SHA-256 provenance.
Other fixtures reuse existing canonical downloads. No card text, stats or deck
lists were invented or changed.

## Validation

- 194 backend checks pass in an isolated source copy, including both-seat
  casting, actual payment, stale-choice rejection and HTTP/SQLite restart.
- Four focused browser flows pass: both seats, prototype and bestow, deliberate
  cost/target selection, stack reload, real resolution and final reload.
- Frontend unit tests, lint and production build pass.
- Initial restoration assertions failed because they bypassed the real stack
  departure handler. Corrected tests use that handler; failed logs are retained.
- Frozen runtime 0424b7b passes 8,848 backend tests across all 357 recursive
  files exactly once. Four initially DB-free copies match 714 source hashes.
  The complete browser suite also passes. RCHFiles evidence:
  `diagnostics/strategic-draw-counts/20261005T102232Z/graveyard-cast-methods/full-qualification`.
  Combined integration is complete in the consolidated main runtime; broader
  tactical acceptance remains open.

## Known Limitations And Next Upgrades

Qualify complete announcement ordering, granted/duration-dependent permissions,
dynamic type layers and additional casting methods. Expand opportunity decisions
to actual affordable multi-action plans, including extra-cost/resource selection.
Free prototype currently has a cost-collection regression; broader free-cast UI
and resolution combinations need acceptance coverage. These fixtures do not
certify every independent ability on the canonical cards.

This bounded family is integrated into the consolidated main runtime.
Successful games and replay repeatability are not proof of arbitrary-card
fidelity, balance or expert AI.
