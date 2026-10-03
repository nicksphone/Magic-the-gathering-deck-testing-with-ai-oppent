# Subtype/color costs and recipient-preserving resolutions

## Acceptance checklist

- [x] Fresh canonical fixtures with Oracle IDs and source URLs for four spells.
- [x] Goblin Grenade/Fodder Launch share validated creature-subtype sacrifice costs.
- [x] Natural Order/Abjure share color-qualified creature/permanent sacrifice costs.
- [x] Both-seat ownership/control/zone/type eligibility, exact payments, free casting
  without waived additional costs, atomic rejection and snapshot restoration.
- [x] Canonical changeling and Kindred permanent candidates; multicolor is accepted,
  while colorless/devoid permanents and Islands are not blue payment resources.
- [x] Natural Order's actual green-creature search uses qualified color/type filters,
  owned resolution-time selection, fail-to-find rules, shuffle and durable choices.
- [x] Fodder Launch's damage goes to the referenced creature's resolution-time
  controller through shared damage/prevention machinery. It is not creature damage
  or life loss. Its only target becoming illegal prevents both instructions.
- [x] Abjure counters the actual spell after its blue permanent is paid.
- [x] All three AI tiers materialize checked casts using eligible resources for both
  seats. These are supplied-legal-move tests, not autonomous tactical-strength claims.
- [x] Expanded 84-test file passes, including eight HTTP/SQLite cases and fourteen
  late borrowed-resource/token cases (5.64 seconds). The latter were added after
  the full suite started and are validated in the separate expanded run.
- [x] Initial existing-cost/kicker regression batch: 374 passed (21.97 seconds).
- [x] Full isolated backend suite: 4,430 passed, 335 deprecation warnings,
  794.04 seconds. Production source matches the working tree; the fourteen late
  resource-edge cases pass separately in the expanded file, not in this full run.
- [x] Frontend lint/contracts/build and full browser, including eight new both-seat
  qualified-payment cases, search-choice refresh, restart, sideboarding and natural BO3.
- [x] Twelve seat-balanced BO1 samples, each run twice, with no reported timeout,
  anomaly or determinism failure (483.324 seconds). Existing Aggro/Tempo/Tokens
  templates are a smoke check; they do not demonstrate these four spells appearing
  in autonomous games or establish expert AI/matchup balance.

## Shared boundary

The clause reader recognizes fixed counts and validated creature subtypes from the
shipped rules-backed subtype list, or one of the five colors followed by a supported
permanent type. The same descriptor drives affordability, exact candidate lists,
checked payment and existing AI resource selection. Candidate filtering rejects stale
battlefield-list entries, nonpermanents and cards controlled by another player. A
controlled permanent owned by another player remains a valid sacrifice resource;
ownership still determines its graveyard destination in the existing zone handler.

Subtype matching includes printed Creature/Kindred subtypes and canonical changeling.
Color matching uses the existing selected-face/canonical color helper, not mana
production or Commander color identity. Costs do not borrow filters from later effects.

Color-qualified library searches retain their printed color and type instead of
widening to every creature. Referenced-controller damage has a reusable handler,
retaining source context and resolving the current controller immediately before
using ordinary damage handling. No card-name gameplay exception was added.

## Evidence and scope

A read-only inventory of 38,690 local knowledge records found four matching printed
qualified/subtype spell clauses. Fresh canonical responses reproduced all four cost
clauses rejected, Natural Order widened to every creature, and Fodder Launch damaging
the creature instead of its controller. The first new test run had 47 failures and
three passes; some Abjure failures were a missing stack label in the fixture, not an
application bug. That label was corrected without relaxing gameplay assertions.
The old unsupported-Goblin-Grenade regression now checks that no eligible Goblin
still means no playable cast, rather than requiring the newly supported clause to
remain unsupported. Unknown cost grammar retains explicit fail-closed tests.
The token-payment probe initially expected a token to remain in a graveyard;
the engine correctly moved it to its ceased state after state-based actions.
The corrected test requires that state and absence from every battlefield,
graveyard and exile list, without changing production code.

Rule references: [official rules/keyword glossary](https://magic.wizards.com/en/keyword-glossary)
and [official changeling explanation](https://magic.wizards.com/en/news/feature/lorwyn-eclipsed-mechanics).

These are semantic scenarios, not invented competitive decklists or modified Oracle
cards. Passing these paths does not certify whole cards or arbitrary-card accuracy.

Verified source, fresh canonical responses, initial probes/failures, corrected
fixture runs, browser evidence and replay results are preserved on RCHFiles under
`diagnostics/qualified-spell-costs/20261003T140748Z/`. Installed dependencies were
reused; fresh installation, network release and long-session UI are not tested here.

## Known Limitations and Next Upgrades

General type/color-changing layers, gained/lost subtype dependencies and suppression
provenance remain incomplete. Qualified intersections/unions, nontoken/nonland/tapped
filters, independent mandatory sacrifice groups, exile/reveal/return/tap costs,
variable counts, payment ordering and interrupted continuations remain unfinished.
Arbitrary search constraints, compound referenced-object instructions and deeper
sacrifice-payoff/response/resource planning are not certified by these tests.
