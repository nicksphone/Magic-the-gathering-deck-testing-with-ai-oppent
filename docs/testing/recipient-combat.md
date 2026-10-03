# Recipient-specific combat clauses

## Implemented Scope

Fixed mana attack/block costs now bind to a supported recipient rather than
automatically taxing every attacking/blocking creature. The same recipient
reader handles self, enchanted/equipped/fortified recipients and recognized
global subject/scope forms. A clause can constrain attack, block, or both;
the current declaration kind locks its own cost exactly once per chosen
creature. Source/controller condition support reuses the existing predicate
reader rather than accepting arbitrary English conditions.

Brainwash's attack clause and Oppressive Rays's attack/block clause have real
canonical regressions. Retargeting an attachment, losing its printed abilities,
departure and snapshot restore affect subsequent declarations, not paid costs.
Unrelated creatures remain untaxed. All AI difficulties use the existing
shared payment/requirement/finalization paths; no named-card AI override exists.

Static all-block requirements can name alternative self/attachment recipients.
Noble Quarry's actual Oracle clause exercises the self case in checked combat
and all four AI difficulties. Its defined bestowed characteristics exercise
only the static reader and snapshot contract, not casting/resolution acceptance.

## Checklist

- [x] Canonical Oracle fixtures, both-seat attack/block costs, atomic rejection,
  once-per-distinct-blocker pricing and SQLite restoration through HTTP.
- [x] Actual both-seat App controls for recipient-only attack/block payments,
  with an unrelated attacker remaining free and one blocker blocking twice.
- [x] Both-seat real AI block decisions across all four difficulties obey the
  all-block requirement without being forced to pay an optional recipient cost.
- [x] Unsupported nonmana payments/qualified all-block clauses stay visible.
- [x] Complete isolated backend suite: 3,125 passed (332 deprecation warnings).
  Frontend lint/unit/build and full Chromium harness passed, including natural
  human/AI BO3 and both-seat specific-recipient cost controls.
- [x] Four template decks, six pairings and twelve logical games in both seat
  orders, each repeated twice: zero timeouts, determinism failures, drift labels
  or reported anomalies. Actual before/after decision traces are archived.

Thirty-two actual agent decisions per revision cover both seats, all four
difficulties, attack/block declarations and zero/three available mana. The
baseline selected the taxed recipient eight times without sufficient mana and
never charged its declared tax. Current decisions selected no unaffordable taxed
recipient and paid the correct amount in all eight paid selections, with no
checked-action errors. These are legality/spending observations on controlled
public boards, not a balance or optimal-play measurement.

Verified source/evidence, raw Scryfall responses and failed/superseded copies
are on RCHFiles under `diagnostics/recipient-combat/20261003T014022Z/`.
`VALIDATION.md` distinguishes real checked actions from static bestow-characteristic
reads and explains the earlier invalid attached-fixture failures.

## Whole-Card Boundaries

This is combat-clause support, not certification that these entire cards work.
Oppressive Rays's numeric activation-cost modifier is now implemented in the
[shared activation payment increment](activation-modifiers.md). Noble Quarry's
bestow alternative casting, Aura transition, illegal-target fallback and
unattachment now have [bounded execution support](bestow.md). Unsupported forms have explicit
coverage/preflight warnings; previously these missing mechanics could go unseen.
No fabricated enchant instruction, card definition or competitive deck was used
to make the integration tests pass. Scryfall omits power/toughness for
noncreatures; the fixture preserves raw provenance and normalizes absent stats
to null only for the reusable test adapter.

Rules reference: [Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf),
CR 508.1/509.1 for declared costs and CR 702.103 for bestow semantics.

## Known Limitations and Next Upgrades

- Extend bestow phasing/type layers and arbitrary permissions beyond the bounded
  casting/resolution/unattachment implementation. Extend activation-cost forms
  beyond supported numeric/source-power and paired controller-turn modifiers.
- Finish qualified blocker subsets, temporary/granted targeted requirements,
  nonmana declaration costs, mana-source choices and interrupted payments.
- Continue wide-board/resource/hidden-choice planning; small scenario or replay
  checks do not establish expert play, arbitrary-card correctness or balance.
