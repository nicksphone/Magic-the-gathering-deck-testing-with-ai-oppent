# Graveyard Casting Methods And Permission Opportunity (Candidate)

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
- Parent runtime 359904ff passes 8,824 full backend tests and the complete browser
  suite. That result is not qualification of this successor. Exact-source full
  backend/browser gates and seeded decision comparisons remain required.

## Known Limitations And Next Upgrades

Qualify complete announcement ordering, granted/duration-dependent permissions,
dynamic type layers and additional casting methods. Expand opportunity decisions
to actual affordable multi-action plans, including extra-cost/resource selection.
Free prototype currently has a cost-collection regression; broader free-cast UI
and resolution combinations need acceptance coverage. These fixtures do not
certify every independent ability on the canonical cards.

The candidate is isolated; main/live are unchanged. Successful games and replay
repeatability are not proof of arbitrary-card fidelity, balance or expert AI.
