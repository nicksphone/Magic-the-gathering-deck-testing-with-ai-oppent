# Initial Strict Baseline

One engine JVM completed in18.313seconds, exit1 for four declared behavioral
REDs, zero errors. The exact eight-class prefix and3710 pinned input files
matched before/after. Six AI classes were observed loaded from that prefix;
the two ActorBoundary classes were not observed loaded in this controlled
harness. Their artifact hashes were checked, not falsely claimed as executed.

| Scene | Both-Seat AI Result | Separate Manual Paid Control |
| --- | --- | --- |
| Landfall vs Topiary Stomper4/4, opponent1 | 0 PASS / 2 RED: PASS chosen | 2 native wins, paid RR |
| Nonlandfall vs Topiary Stomper4/4, opponent1 | 0 PASS / 2 RED: PASS chosen | 2 native wins, paid RR |
| Landfall vs Runeclaw Bear2/2, opponent1 | 2 native paid wins | 2 native wins, paid RR |
| No opposing creature | 2 PASS: declined | Not a legal positive control |
| Opposing player hexproof | 2 PASS: declined | Not a legal positive control |
| Unfunded | 2 PASS: declined | Not a legal positive control |

AI total8PASS/4RED; separate manual total6PASS/0FAIL. Do not aggregate the
manual wins into AI competence. All12 AI cases used exactly one fresh Default
chooser invocation before diagnostic queries. There was one declared seed
before model initialization and no reset. All physical choice snapshots matched;
this is not a claim that evaluating native AI is universally RNG-pure.

Actual retained source/target flags in all four REDs: root targets opposing
player, linked DealDamage child targets empty, child isMandatory=false. In both
Bear AI positives the root targets the opposing player and the child targets
the Bear. Native RR payment consumed exactly two red mana from two Mountains;
resolved opponent life was-2 for landfall and0 for nonlandfall manual controls,
actor20, native actor won/enemy lost. No free cast, manually assigned winner,
re-evaluation, native class change, body rewrite or altered expectation occurred.

## Exact Source Path

Source references are to prefix3f595b71's copied native DamageDealAi.java,
SHA256`bac01d37456a32978a406fc5875ab5f5ab0305461bcdb1f157916589ca73a129`.

- DamageDealAi.chkDrawback44-94 computes the child's damage and at91 calls
  damageTargetAI with immediately=true; failure returns TargetingFailed94.
- damageTargetAI459-470 passes the actual sa.isMandatory flag onward.
- damageChoosingTargets659-668 asks dealDamageChooseTgtC for the creature;
  when none is selected, the minimum-target failure resets targets745-746.
- dealDamageChooseTgtC324-362 starts with targetable cards, enforces MustTarget,
  filters killable targets344-354, and returns null361-362 for an empty killable
  set when mandatory=false. Immediate timing does not mean mandatory targeting.
- Native SpellAbility.isMandatory1383-1384 is isTrigger&&!isOptionalTrigger;
  this child is an AbilitySub of a spell, not a mandatory trigger.
- Native SpellAbilityAi.canPlayWithSubs56-66 calls the child chain only after
  the root is willing. chkDrawbackWithSubs269-281 dispatches to the actual
  DamageDealAi override and propagates child failure. It does NOT use the base
  class's default targeted-drawback rejection for this child.

The actual one-choice outcomes, retained root/child flags, controlled Bear
contrast and independent paid legal wins establish a controlled policy failure.
They support the killable-child source explanation. Exact internal local values
and return-site branch events were not instrumented; do not call this a passive
branch-local trace or exact reproduction of the earlier natural T15 decision.
The natural-game review remains a candidate, not retrospectively certified.

## Minimal Generic Proposal (Not Implemented Or Authorized)

Consider a narrow nonkillable-target fallback in the linked damage child's
drawback/creature-target path, not a global mandatory/immediately change:
require a root already admitted by the ordinary native policy, an opposing
player already selected, a proven-safe lethal native root prediction, and an
explicitly supported pure linked damage chain. Choose an otherwise legal
required opposing creature target even if that child damage cannot kill it.
Keep all targetability/MustTarget restrictions and the native payment/stack/SBA
path. Do not relax root timing, prevention/protection/cannot-lose, own-cast-cost
safety or funding gates. Use semantic ability structure, not card/deck names.

The lifecycle of any already-computed lethal forecast/context still needs
design review: no repeated canPlay/cost/forecast/RNG call and no stale cross-
decision mutable cache should be added. These tests alone do not authorize
class/profile changes. Before a future product grant, add independent controls
for nonlethal roots, pure creature removal, prevention/cannot-lose/infect,
own-cast backlash, target protection/MustTarget and compound side effects.

Local evidence root is native-linked-damage-lethal-audit-zIiBfN3d/baseline:
summary.private.json contains all actual rows; VERIFIED-CLOSED.json separates
the cohorts and loaded origins; BEFORE.json contains original/current pins;
LAUNCH.json, PROCESS-CLOSED.json and class-load.log retain exact runtime proof.
The initial12-file source snapshot remains byte-identical to its pre-run pins.
No production change, rerun, replay ABI work or new UI game was performed.
