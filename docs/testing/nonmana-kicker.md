# Fixed nonmana kicker and payment-aware decisions

## Acceptance checklist

- [x] Shared fixed life/discard/typed-sacrifice component parsing, not card-name rules.
- [x] Canonical sacrifice-creature, sacrifice-land and pay-life kicker fixtures.
- [x] Paid/unpaid targets/effects, normal/free cost admission and snapshots.
- [x] Explicit typed/count payment choices and atomic invalid-payment rejection.
- [x] Copies retain the choice without a second sacrifice/life payment.
- [x] Shared self-or-owned-other death matcher and real sacrifice payoff tests.
- [x] All AI difficulties compare optional payment loss against recognized gains.
- [x] Focused acceptance: 421 passed, including HTTP/SQLite restoration.
- [x] Frontend lint/contracts/build; complete browser suite including twelve
  new cases, restart recovery and natural BO3.
- [x] Both-seat payment-source probes tap lands for mana before sacrificing
  those chosen lands, with no remaining mana and the exact surviving land count.
- [x] Twelve seat-balanced BO1 samples repeated twice: zero reported anomalies,
  timeouts or determinism failures, 518.414 seconds. This is repeatability evidence,
  not an optimal-play or matchup-balance certificate.
- [x] Full isolated backend suite: 4,156 passed, 307 deprecation warnings,
  709.71 seconds, using installed dependencies and the isolated test database.
- [x] Twenty-four actual AI decisions across both seats and all difficulties
  choose the tested high-life counter payment, preserve low life, select a useful
  removal sacrifice and retain lands for unproductive additional discard.
  Checked casts, hands, choices and payment logs are retained with evidence.

## Shared contract

The kicker cost reader accepts one fixed mana cost or one recognized fixed
life/discard/typed-sacrifice component. It reuses the additional-cost reader rather
than inferring payment from later spell effects. Life amounts, sacrifice counts
and sacrifice types feed ordinary affordability, selected-card validation and
payment. The paid branch is still an additional cost when the mana cost is waived.
Unsupported tap/reveal/qualified/X/multiple costs remain visible as coverage gaps.

The spell surface compiler now handles recognized replacement discard counts in
addition to conditional damage/pump/draw. The permanent compiler retains the same
counter entry/replacement/prohibition path. A spell copy keeps the announced kicked
choice and conditional effects but does not pay resources or emit a second cast.
Mixed mandatory sacrifice types need independent groups and receive a diagnostic
rather than incorrectly summing the count using the last type encountered.

Sacrifice payments preserve ordinary deaths and their triggers. The shared death
matcher recognizes controller-scoped self-or-other-creature subjects, using departed
object/controller information. Canonical checks cover self, friendly and opponent
deaths, source departure and snapshot resolution; this is not arbitrary death grammar.

AI optional-cost decisions reuse hand-retention, sacrifice-loss and life-risk
estimates. Supported negative-toughness breakpoints can justify paying to remove a
larger opposing creature, while already-lethal removal does not buy that upgrade.
The indestructible distinction uses zero toughness versus damage lethality. Life
payments at low/lethal life totals are discouraged. Opposing discard gain uses
public hand count, never hidden card identities. These are bounded estimates, not
full adversarial planning or an expert-strength claim.

## Canonical evidence and boundaries

`backend/tests/fixtures/nonmana_kicker.json` records fresh Scryfall source URLs,
identities and unmodified Oracle text for Bog Down, Phyrexian Scuta and Vicious
Offering. Existing canonical Baloth Gorger and Zulaport Cutthroat fixtures supply
targets and payoff sources. No competitive deck or playable card was fabricated.

The creature free-cast case tests the shared authorized-cost admission directly;
it does not broaden the existing instant/sorcery-only graveyard permission to
creatures. Syntax-only malformed/mixed-cost diagnostics are not playable fixtures.
HTTP checks reject malformed payments with identical complete memory/database
snapshots, then invoke the app's actual startup restore function after a legal cast.

The initial focused failures included a missing Forest fixture, use of an unknown
damage effect key, an intentionally narrower graveyard-cast permission and stale
test-state references after rejected HTTP mutations. Corrected fixtures retain the
original resource/outcome assertions. The added sacrifice-payoff test exposed a
real missing controller-scoped death matcher, which was fixed in shared code.

`frontend/tests/browser-nonmana-kicker.mjs` passes twelve both-seat real
App/API cases: exact mana/life/sacrifices, payment button gating, refresh with a
pending spell and deliberate owned discard choices. An older hand-activation
browser assertion raced a pending request; the wait now requires authoritative
graveyard/stack state without changing the gameplay assertions. The full rerun passes.

The read-only local knowledge inventory has 38,690 records and 270 faces mentioning
kicker/kicked/multikicker. Recognized surfaces increase from 19 to 27 at the same
corpus revision. The eight newly classified names include the three primary
fixtures plus Stomped by the Foot, Hypnotic Cloud, Final Flourish, Vayne's Treachery
and Eject the Warp Core. These are classification counts, not full-card certification;
the five additional cards now have [canonical interacting goldens](kicker-goldens.md).
Their accepted paths remain bounded; classification does not certify whole cards.

## Known Limitations and Next Upgrades

Qualified or mixed mandatory payment groups, variable/nonmana compounds, X kicker,
dual kicker, multikicker, payment-order choices and interrupted continuations remain
unfinished. Cost parsing alone does not certify a whole card. Optional-resource
valuation is coarse, including conservative land retention; sacrifice synergies,
response-mana holding and racing require deeper planning. Arbitrary death triggers
and complete gained/suppressed ability provenance remain open. Fresh installation,
network deployment, broad matchup balance and the deferred UI redesign are not
acceptance claims of this backend batch.

Verified source, canonical responses, test logs, corpus classification and decision traces
are archived on RCHFiles at `diagnostics/nonmana-kicker/20261003T130221Z/`.
