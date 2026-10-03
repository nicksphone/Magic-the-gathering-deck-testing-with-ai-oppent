# Effect-authorized graveyard casting choices

## Supported contract

The recognized cast-from-your-graveyard effect can pause for either human seat.
The authoritative permission identifies one card and survives snapshots. Legal
moves expose that card through existing off-zone cast controls plus a decline
choice. A normal `cast_spell` announcement supplies the player's actual targets
and cost choice; clients cannot grant themselves a mana-cost waiver.

The shared admission helper checks the selected graveyard card, normal targets,
mandatory costs, taxes, timing overrides and printed X=0. It forecasts admission
on a copy before committing. Rejected checked actions preserve the entire state
and pending permission. Declining pays nothing and leaves the card in its zone.
Finishing either choice resumes the saved enclosing resolution once. Recognized
exile-on-departure metadata belongs to the spell, not a cast-trigger stack item.

Supported targeted graveyard casting triggers announce their graveyard target
when put on the stack, before the later optional cast decision. A Counterspell
can be a legal ability target even when it could not subsequently be cast.

## AI behavior

The shared trigger-target policy projects supported casts, excludes invalid or
unpayable announcements, then applies the existing cast-bias heuristic. A free
mana-spent draw that would inspect zero cards is not preferred without a
recognized cast-surveil payoff. If no useful cast is found, the triggered ability
still receives a legal target; ordinary effect admission can subsequently decline
an impossible announcement. This is bounded opportunity ranking, not optimal
search, general permission planning or expert-level evaluation.

## Validation

`backend/tests/test_effect_cast_choices.py` uses canonical fixture cards in both
seats: deliberate targets, cast/decline, trigger and resolution-stage snapshots,
taxes, printed X, departed cards, rejected announcements, HTTP atomic rejection
and duplicate prevention. Existing effect-admission, trigger-target and surveil
tests exercise the same shared handlers. The browser scenario
`frontend/tests/browser-effect-casts.mjs` casts a real Gearhulk, chooses its
graveyard target, refreshes both stages, then casts/targets or declines through
the actual App/API in both seats. Fixture decks are test scaffolding, not invented
competitive decks or tournament evidence.

Final acceptance: 3,665 isolated backend cases pass (358 deprecation warnings,
610.32 seconds), with frontend lint/unit/build and the complete Chromium harness.
The twelve-sample repeated Master matrix reports no timeout, anomaly or replay
drift; eight real-deck traces in both seat orders finish without invalid-cast
lines. Some Tokens/Ramp blocking-quality metrics lack evidence and remain null.
Installed dependencies are reused; clean installation is not established here.
Failed and superseded runs are retained separately in the verified RCHFiles
archive `diagnostics/effect-cast-choices/20261003T083528Z/`.

## Known Limitations and Next Upgrades

- General effects that authorize a card from other zones or multiple cards need
  their own permission contract and acceptance tests.
- [Recognized discard/sacrifice selections](cast-payment-selections.md) now use
  explicit ordinary cost-card controls in either seat. Optional kicker under a
  mana-cost waiver, broader grammar and interrupted payment continuations remain
  open.
- Modes and targets reuse existing supported cast controls; this does not prove
  arbitrary modal, multi-face or unusual cost composition works.
- AI uses the existing Strong materialization heuristic for this shared effect
  path, not a separate exhaustive or difficulty-specific permission search.
- Canonical fixtures and small replay matrices do not certify complete card
  semantics, matchup balance, tournament training or seasoned-player strength.
