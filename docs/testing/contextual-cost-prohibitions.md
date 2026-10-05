# Contextual Life and Sacrifice Costs

Status: unpublished backend candidate. Full latest-source, browser and natural
game qualification remain required before publication.

## Shared Rules

Recognized unconditional printed prohibitions on paying life or sacrificing
creatures apply to spell casting and ability activation, not arbitrary life loss
or land-entry payments. The source's effective abilities and controller determine
whether its printed prohibition applies. Zero-life payments remain legal under
Comprehensive Rules 119.4b. Phyrexian symbols can still be paid with actual colored
mana when life payment is prohibited.

Shared mana planning/payment and additional/activated cost checks use the same
context-aware predicate. Mixed artifact/creature sacrifice costs retain eligible
noncreature artifacts. Exhaustive costs cannot silently omit forbidden creatures.
Abilities with supported symbol-free life/sacrifice/discard costs now enter the
existing cost/effect admission path; unknown effects are not thereby supported.

An HTTP regression exposed a separate existing payment defect: generic sacrifice
availability counted the ability source, but actual payment always excluded it.
Payment now excludes a source only if it has already been included by an explicit
source-sacrifice cost. Both-seat tests verify the actual graveyard departure and
stack object, not merely that the activation appears in legal moves.

## Canonical Data and Evidence

Seven unchanged public Scryfall records and retrieval hashes/URLs are stored in
`backend/tests/fixtures/contextual_cost_prohibitions/`. Angel of Jubilation,
Viscera Seer, Dismember, Sacred Foundry, Kaervek's Spite, Makeshift Munitions and
Bone Splinters exercise the shared families. No card balance or Oracle text was
changed to fit the implementation. These fixtures do not certify every clause
on those cards.

- Initial selected regressions: 10 failures and 12 passes before the repair.
- Broader selection exposed two exhaustive-sacrifice omissions; shared legality
  and actual payment were corrected rather than weakening the assertions.
- Before the subsequent query prefilter, 490 checks pass across 15 files. These
  include 52 direct cases and six HTTP/SQLite cases, both seats, suppression and
  snapshot recovery, unchanged rejected memory/database snapshots, genuine paid
  actions and paid-stack recovery. Eight AI cases materialize payable Phyrexian
  branches for four archetype labels; this is legality, not strategic mastery.
- The first HTTP run had four failures: two genuine source-sacrifice payment
  defects and two incomplete test requests. An intermediate fixture used an
  incorrect cost-option ID. The corrected request uses the existing `base`
  option required by the API; failed evidence is retained, not labeled green.
- Relevant clause filtering now precedes expensive effective-ability queries.
  The latest source passes 495 checks across 16 files, including five structural
  query regressions. Full latest-source qualification remains open; earlier
  complete gates cannot certify this later runtime.

## Remaining Acceptance

## Full-Gate Selection Follow-up

The first full gate exposed an existing default-choice contract: when another
eligible creature is available, generic sacrifice payment should not immediately
consume its own ability source. The original repair made self-sacrifice legal
but changed that default. The corrected shared payment stably orders the source
after other candidates, without forbidding self-sacrifice when necessary.
Both-seat canonical Seer fixtures verify both choices. The unchanged existing
legal-move regression and six paid HTTP/recovery cases also pass; the latest
selection passes 292 checks across ten files. This newer source requires a fresh
full gate; the prior 495 checks and failing full run do not certify it. Explicit
strategic/human sacrifice selection remains outside this automatic-choice repair.

## Remaining Acceptance

Run the complete latest-source backend gate and browser/action integration;
retain deterministic game/decision evidence where these families are exercised.
Conditional prohibitions, broader costs, granted/rewritten printed semantics and
optimal sacrifice/life-resource strategy remain open. Land-entry, ward and combat
payment contexts must not be accidentally treated as spell/activation costs.
