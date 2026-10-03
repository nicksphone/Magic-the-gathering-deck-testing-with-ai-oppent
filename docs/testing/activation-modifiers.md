# Activation Cost Modifiers

## Implemented Scope

Generic numeric activation increases and numeric/source-power reductions share one cost context across
availability, checked execution, actual payment and legal-action hints. Supported
Oracle clauses bind global, controller, recognized creature/permanent and attached
recipients. They apply only while the source is on the battlefield with its printed
ability available; source loss, attachment identity and controller changes matter.

Canonical fixtures retain Scryfall IDs and URIs for Suppression Field, Training
Grounds, Heartstone, Zirda, Power Artifact, Oppressive Rays, Azure Mage, Mind Stone,
Llanowar Elves and Auriok Steelshaper. Fixtures are not new competitive decks.

`dynamic_activation_modifiers.json` adds canonical Agatha of the Vile Cauldron
and Tithe Taker data, with Oracle IDs and source URIs. No rules dispatch on their
names: the supported grammar binds a self-name/prefix power reference or a complete
paired controller-turn opponent spell/ability tax. These are bounded cost clauses,
not certification of every effect on either card (including Afterlife).

- Source-power reductions use current effective power, including supported Auras,
  counters and temporary effects, with negative power contributing zero. The
  creature recipient scope, source suppression and one-mana floor remain intact.
- Paired `During your turn` spell/ability taxes apply only to opponents during the
  source controller's turn. Both halves use the same recognition function; mana
  exceptions affect only the ability half. Multiple sources stack, and source
  departure or printed-ability suppression disables both halves.
- Requirements are computed before automatic mana-source consumption by the
  existing shared planner. This does not establish arbitrary interrupted-cost
  continuations or an explicit human ordering interface.
- Ability-specific `This ability costs ...` clauses are reported as gaps, not
  applied to every ability on their card. Unsupported `During ...` activation
  modifiers are also reported instead of disappearing from static-clause filtering.

- Increases precede reductions. Recognized one-mana floors belong to each reduction,
  not a global minimum: independent equip reductions can still reach zero.
- Generic discounts never remove colored, colorless or snow requirements. An
  existing zero cost is not raised by a reduction's floor.
- Mana exceptions distinguish actual mana activations from nonmana abilities.
  Creature-permanent discounts do not apply to cards cycled or ninjutsu-activated
  from the hand; recognized global modifiers do.
- Tap/sacrifice sources and chosen crew creatures are reserved against double use
  by automatic mana payment. Legal crew moves carry a payable candidate group;
  AI materialization uses that group rather than an independently chosen one.
- Cycling, loyalty, equipment and ninjutsu use activation payment context. Printed
  zero-mana costs still receive increases. Announced activated X is checked against
  source-aware payment rather than a spell-only budget.
- Automatic payment only counts free mana activations. A payable taxed producer
  remains manually usable, including its actual fee; it is not assumed free.
- Unsupported modifier grammar and unrecognized minimum wording remain explicit
  coverage warnings. Recognizing a clause is not whole-card certification.

## Validation

`backend/tests/test_activation_modifiers.py` covers both seats, controller scope,
attachments, floors, mana exceptions, reservations, actual draw/cycling/crew/loyalty/
equip resolution, X announcements, source suppression, snapshot reload and atomic
HTTP/SQLite rejection and restore. The existing AI and variable-mana regressions
also cover lightweight fixtures and zero-cost pool preservation.

`backend/tests/test_dynamic_activation_modifiers.py` additionally checks both
seats, effective-power changes, source/controller/Aura changes, floor/color
preservation, draw resolution, turn/actor/mana exceptions, matching spell
affordability/payment, HTTP rejection and durable SQLite restore. The recorded
baseline runs these same canonical fixtures against the preceding committed
engine; it is an intentionally failing reproduction, not a passing gate.

Dynamic-cost milestone evidence is archived under RCHFiles
`diagnostics/dynamic-activation-costs/20261003T042248Z`. The full suite passed
3,311 tests; two final checked-instant tests were added afterward without changing
production code, and the expanded focused suite passed 158. The archive preserves
the 25-failure/12-pass committed baseline, 98-card grammar-only probe and 24 actual
AI decisions (22 draw activations, including all 16 Strong/Master cases). Twelve
logical four-deck replay samples were each repeated twice; a separate two-sample
run uses the final engine source. Neither is a statistical balance measurement.

Independent before/after probes record 18 actual AI decisions per revision with
full snapshots, hands, battlefield, legal moves, reasons and checked results. The
baseline is commit `280df82`; these are constructed canonical interaction states,
not tournament samples or a claim of optimal play. Final suite/replay evidence is
recorded in the milestone changelog and archived under RCHFiles
`diagnostics/activation-modifiers/`.

Rules reference: [Wizards Comprehensive Rules, September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
CR 118.7a, 601.2f and 602.2b. Reduction order is chosen automatically to minimize
the supported mana cost; this is not an explicit human ordering interface.
The [Wilds of Eldraine release notes](https://magic.wizards.com/en/news/feature/wilds-of-eldraine-release-notes)
also distinguish battlefield creature activations from cycling and triggered
abilities for the source-power reduction fixture.

## Known Limitations and Next Upgrades

- Extend bestow phasing/type-layer fidelity and broader permissions beyond the
  [implemented casting/resolution/unattachment scope](bestow.md).
- Extend ability-specific discounts, arbitrary conditions/dynamic expressions,
  copied-name references and other floors with canonical fixtures;
  do not silently interpret arbitrary Oracle clauses. Zirda's companion procedure
  and every unrelated clause on these fixture cards are not certified here.
- Add deliberate payment-source/reduction-order controls and paid-mana conversion
  planning. Current automatic payment conservatively excludes taxed producers.
- Finish interrupted cost/replacement continuations and broader nonmana costs.
- Expand adversarial multi-turn and wide-board crew/resource planning. A payable
  crew group is not necessarily the strategically best group; replay repeatability
  and these decisions do not certify expert AI, arbitrary-card fidelity or balance.
- The alpha UI still shows printed ability costs; modified cost metadata is available
  in legal hints, but complete dynamic-price presentation awaits the deferred UI work.
