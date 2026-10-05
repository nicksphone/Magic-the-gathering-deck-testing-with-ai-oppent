# Announced Spell Cost Modifiers

## Implemented Scope

Unconditional fixed generic taxes and discounts share whole-clause parsing.
Supported qualifiers include single colors, colorless, the existing spell-type
filters and explicit color-class unions such as "green spells and blue spells".
Own/opponent/global scope uses the source's current controller. One union clause
reduces a multicolor spell once; separate clauses stack. Generic reductions
never remove colored, snow or specifically colorless mana requirements.

Affordability and real payment use the chosen spell's colors. Prototype uses its
announced cost/color rather than the original colorless card; devoid uses actual
color rather than mana symbols. The existing exact paired turn spell/ability tax
remains separate from unconditional static clauses. Suppression, snapshot restore
and cleanup expiration are covered. Unsupported color-qualified cost clauses
warn instead of silently becoming unqualified/global modifiers.

Eleven complete raw Scryfall downloads retain source URLs, timestamps and SHA-256
provenance. They are constructed rules positions, not invented cards or decks.
Supporting a clause does not certify every other ability on that card.

## Evidence

- Initial fixture-loader errors were fixed by treating omitted noncreature stat
  fields as absent; downloaded Oracle data was not edited. Then ten real cost
  regressions failed before implementation.
- 268 focused backend checks pass, including existing activation modifiers,
  restricted mana and graveyard casting methods. An intermediate regression
  dropped supported turn taxes; its four failures are retained and fixed.
- 33 isolated HTTP/rules checks pass, including six new both-seat API payment,
  rejection and SQLite restart cases. These counts overlap, not additive totals.
- Six Chromium scenarios pass: both seats, own discount, unrelated color tax
  and prototype, actual UI choice/payment, reload and resolution.
- Final parser simplification passes 84 focused checks. This increment was
  subsequently included in the qualified `91b5dff` consolidated runtime; see
  [integration evidence](backend-consolidation.md). Release gates remain open.

## Known Limitations And Next Upgrades

Dynamic colored costs, mixed color/type qualifiers, floors, gained abilities and
arbitrary conditional clauses remain outside this increment. Whole announcement
ordering and arbitrary continuous color-layer fidelity remain separate work.
Use a full suite at the combined integration boundary, not another independent
qualification cycle for each small parser change. No AI strength or balance
claim follows from these deterministic rules fixtures.
