# Native Precombat Buff Timing

## Cause And Correction

Recorded Tribal games held a lord until after combat despite ready Elf
beneficiaries and untapped lands. The shared permanent timing gate recognized
haste and legacy card-data hints, but not an incoming continuous stat bonus.
This failed before the normal permanent evaluation could consider the spell.

The additive fallback recognizes unconditional friendly, positive-power static
bonuses using closed native creature-type/YouCtrl/Other selectors. Native
battlefield defaults include null active-zone values. Affected cards must be
attack-ready through native combat restrictions; raw sickness flags alone are
not used. Unknown conditions, layer changes, replacement contexts, attack costs
and unsupported combat constraints fall through without a new timing reason.

Funding reuses Forge's existing basic-land/unrestricted-pool witness without
calling its stateful test payment planner. Creature mana does not count in this
witness. The existing helper body, ordinary spell evaluation and actual payment
are unchanged. The helper's visibility becomes package-private for reuse.
This is not a payment reservation, arbitrary layer forecast or general combat
planner, and it does not promise optimal timing in unsupported contexts.

## Verified Component Evidence

- The unchanged six-case registered fixture on the matched parent has two
  funded Main 1 policy failures, two unfunded declines and two observations.
  The corrected prefix selects and natively pays for both funded casts; the
  declines and observations remain. Manual native controls are not AI successes.
- The separate twelve-case cohort retains both ordinary Main 2 casts. Its ten
  other native controls are observations, not independent strategic wins; actual
  choices remain declines under Humility, tapped/sick beneficiaries, opposing
  Elves or own non-Elves. Both seats are covered.
- Existing pressure70, knowledge38 and boundary48 pass. Unchanged gain-response6
  and preservation10 also pass. The three serial cohorts finish in 255.58 seconds;
  this is a measured execution duration, not a speed or playing-strength claim.
- A separate unchanged eight-case source tests Clancaller and Leaf-Crowned
  Visionary in both seats. Four land-funded refusals on the parent become four
  ordinary AI casts. Actual payment uses two distinct Forests, both ready
  Llanowar/Archdruid beneficiaries remain untapped, and their full native stats
  change from 2/2 to 3/3. All four one-Forest alternatives still decline; separate
  manual native payments demonstrate that creature mana could otherwise pay.
- Four fresh parent and four fresh corrected Tribal/Ramp games, using the same
  two seeds and both seat orders, all complete without native errors. These are
  separate paired cohorts, not a win-rate or expert-strategy certificate.
  In three matched pairs the first selected-public-action divergence is a real
  Main 1 Clancaller cast instead of proceeding to attackers. Two Forests pay,
  existing creatures receive their native buffs while untapped, then actually
  attack. The original case18 now attacks with its two Elves at 3/3 rather than
  casting the lord after their 2/2 combat. This compares recorded public actions,
  not an unavailable initial-chooser trace or complete legal opportunity set.

Fixtures use declared established-ready poses, not invented paid-cast history
or a forced game winner. Natural traces remain separate from those controls.

Candidate: `a721ca75042823349ad3a37bbbfb18d4311b92914ca81ddb213df6e8e9f655d9`.
Profile: `cf86c19b614046891d00655d5190f3337084183c270df42e866199dd123688f3`.
The full prefix remains thirteen sources/twenty-one classes; two sources and two
classes change relative to the qualified expiring-land parent. Earlier draft
results and review corrections are preserved separately.

## Delivery And Limits

[Source patch, unchanged fixtures, full canonical programs and attribution](../../tools/engine_evaluation/forge/native-ai/precombat-buffs/README.md)
retain Forge Team/Card-Forge authorship and GPL notices. Rebuild only over the
exact parent pins; no live profile is installed. Complete strategy quality,
learning generalization, BO3 acceptance and application adoption remain open.
