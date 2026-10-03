# Activation Cost Modifiers

## Implemented Scope

Generic numeric activation increases and reductions share one cost context across
availability, checked execution, actual payment and legal-action hints. Supported
Oracle clauses bind global, controller, recognized creature/permanent and attached
recipients. They apply only while the source is on the battlefield with its printed
ability available; source loss, attachment identity and controller changes matter.

Canonical fixtures retain Scryfall IDs and URIs for Suppression Field, Training
Grounds, Heartstone, Zirda, Power Artifact, Oppressive Rays, Azure Mage, Mind Stone,
Llanowar Elves and Auriok Steelshaper. Fixtures are not new competitive decks.

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

Independent before/after probes record 18 actual AI decisions per revision with
full snapshots, hands, battlefield, legal moves, reasons and checked results. The
baseline is commit `280df82`; these are constructed canonical interaction states,
not tournament samples or a claim of optimal play. Final suite/replay evidence is
recorded in the milestone changelog and archived under RCHFiles
`diagnostics/activation-modifiers/`.

Rules reference: [Wizards Comprehensive Rules, September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
CR 118.7a, 601.2f and 602.2b. Reduction order is chosen automatically to minimize
the supported mana cost; this is not an explicit human ordering interface.

## Known Limitations and Next Upgrades

- Finish bestow casting, Aura characteristics, resolution and unattachment. Noble
  Quarry's alternative characteristic fixture does not demonstrate bestow support.
- Extend conditional/dynamic modifiers and other floors with canonical fixtures;
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
