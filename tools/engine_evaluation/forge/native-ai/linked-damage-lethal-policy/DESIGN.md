# Approved Minimum Design And Recorded Limits

The frozen audit proves a controlled failure: four Stomper AI REDs despite
separate legal paid native wins. Natural T15 is still not a certified mistake.
After the strict32 baseline closed, the minimum DGAI-only product was approved.
Only a copied native source/class under this family changes; shared native
sources/classes, profile builders and every predecessor test remain untouched.

## Approved Minimum Candidate

Prefer a DamageDealAi-only linked-child drawback fallback, with unchanged native
ABI: only an actual spell's pure player-damage -> required linked opposing-
creature damage -> DamageResolve chain, exactly one already selected opposing
player, and matching root/child amount and prevention semantics. Reuse the
child's already-calculated damage only where its root equivalence is established;
do not call calculateDamageAmount(root) a second time. Invoke the existing
isLethalDamageToPlayer once, then allow an otherwise legal opposing creature
target even if the child cannot kill it. Keep targetability, MustTarget and
ordinary root admission/cost/payment/own-cast safety; never set global mandatory
or infer that every immediately=true child is mandatory.

This is an approved extra native forecast, not a no-extra-evaluation claim.
No mutable ability field, stale cache, ThreadLocal, evaluator/cost-policy retry,
raw damage == lethal shortcut, named-card branch or shared source/profile edit is made.
Root/child X-dependent or unequal amount semantics, alternate branches, optional
targets, unknown conditions, triggers, activated roots and extra effect nodes
must fail closed unless separately reviewed. Source-only proof that all public
direct-child entry points imply prior root admission is not established; the
standard Default canPlayWithSubs path does root admission first. This remains
a documented limit, not a claim that direct callers prove root admission.

## Forecast Inspection And Exact Limit

Current pinned DamageDealAi473-481 checks life-loss availability, disabled
zero-life loss and infect, then calls staticReplaceDamage (NoPrevention) or
ComputerUtilCombat.predictDamageTo. ComputerUtilCombat2227-2255 dispatches
noncombat prediction through Player.staticReplaceDamage724-809 (numeric local
operations over current state) and GameEntity.staticDamagePrevention89-146.

The latter does replacement requirementsCheck115, matching122-125, and
AbilityUtils.calculateAmount for a prevention Amount138. AbilityUtils2766-2771
can execute Count$Random and advance MyRandom; CardTraitBase470-485 can also
evaluate authored SVar requirements. Therefore the wrapper's nonmutation comment
does NOT prove universal RNG or state purity. The canonical fixtures' fixed
numbers/Count$Landfall, unconditional prevention and ordinary life conditions
are a bounded deterministic domain, not a certificate for arbitrary authored
replacement programs. The existing raw damage amount helper974-982 can also
evaluate authored randomness; reusing the existing child's result avoids adding
that second amount evaluation, but not the extra forecast limitation above.

If design approval requires unchanged RNG/evaluation history on every legal
board, this one-source option is insufficient without an explicit safe-domain
guard. Do not silently add an interpreter-wide purity framework or accept an
unqualified guarantee. An alternative is method-local per-canPlayWithSubs
forecast/payoff context threaded through reviewed overloads in SpellAbilityAi,
DamageAiBase and DamageDealAi; legacy/direct-child entries receive none. That
avoids another forecast but expands source/class scope and still needs approval;
it is not implemented here and no cache is proposed.

## Why Not Any Admitted Nonlethal Root

Admitted player damage plus required creature damage can be beneficial even
without a creature kill, but the bonus is not automatically free. Retaliation
(for example Boros Reckoner), lifelink or damage replacements, enrage token/draw/
counter triggers, redirected damage and forced follow-on effect nodes may make
nonlethal creature damage harmful. The nonlethal-retaliation and side-effect
controls make this distinction explicit; no global burn/removal preference is
authorized. Lethal root payoff also must not be claimed for infect, prevented
damage or a player protected from losing, and cast backlash happens before
payoff. These controls are scoped safeguards, not all-cost/all-effect fairness.

## Pre-Product Controls

Twenty new both-seat cases plus the old12 unmodified check methods, total32,
one declared seed2026110627 before model initialization. Old12 expectations
stay strict. The infected activated control is honestly nonlinked: canonical
Phyresis cannot legally enchant an instant. Full native canonical programs and
native land entry are used; no spell body, history, land counter or winner is
rewritten. Actual chosen positives must pay, resolve all native pending triggers,
and reach the declared removal/native outcome. No manual action rescues an AI
failure. Any unexpected control is reported without retuning its expectation.
