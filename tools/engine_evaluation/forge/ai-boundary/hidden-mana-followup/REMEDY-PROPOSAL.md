# Proposal: Per-Call Known-Resource Affordability

## Approval Boundary

**Proposal only. No production patch, compilation, tests, profile changes or new
qualification are performed by this document.** The existing visibility patch,
twenty controls, six follow-up checks, and parent-owned `runtime_profile.py` /
`test_runtime_profile.py` remain untouched. The parent-reported completed UI game
is operational evidence, not evidence closing this cost-information channel.

Recommended implementation scope, if separately approved: **three native Java
files**, with a generic per-call card-knowledge predicate threaded through the
existing affordability search. This cannot responsibly be confined to the
`hasAFogEffect` body using existing public overloads. No fourth production file
is proposed. Anything requiring one needs another proposal before editing.

This is a new increment on top of the frozen identity correction, not an edit to
its patch/profile or a reuse of its qualified identity. No deployment or app/save
compatibility claim follows from this proposal or from the earlier 20 passes.

## Read-Only Findings

The pinned API has only these `ComputerUtilCost` entry points:

```java
boolean canPayCost(SpellAbility sa, Player payer, boolean effect)
boolean canPayCost(Cost cost, SpellAbility sa, Player payer, boolean effect)
```

Relevant `ComputerUtilMana` entry points are:

```java
boolean canPayManaCost(ManaCostBeingPaid cost, SpellAbility sa,
                      Player ai, boolean effect)
boolean canPayManaCost(SpellAbility sa, Player ai, int extraMana, boolean effect)
boolean canPayManaCost(Cost cost, SpellAbility sa,
                      Player ai, int extraMana, boolean effect)
CardCollection getAvailableManaSources(Player ai, boolean checkPlayable)
CardCollection getManaSourcesToPayCost(ManaCostBeingPaid cost, SpellAbility sa,
                                     Player ai, boolean effect)
SpellAbility chooseManaAbility(ManaCostBeingPaid cost, SpellAbility sa,
                              Player ai, ManaCostShard toPay,
                              Collection<SpellAbility> maList, boolean checkCosts)
```

None accepts observer knowledge or an allowed-source predicate. The last chooser
accepts an already-built ability list, but the full affordability routine builds
its own list internally. `getManaSourcesToPayCost` returns chosen hosts after
that search; it does not accept candidates. `test=true` avoids actual payment but
does not restrict information. `effect` and `checkPlayable` express rules/cost
semantics, not knowledge permissions, and must not be repurposed.

The demonstrated path is:

```text
hasAFogEffect(... defender ..., checkingOther=true)
  -> canPayCost(sa, defender, false)
  -> canPayManaCost(cost, sa, defender, extraManaNeeded, effect)
  -> payManaCost(... test=true ...)
  -> getSourcesForShards
  -> groupSourcesByManaColor
  -> getAvailableManaSources(defender, checkPlayable)
  -> actual defender battlefield + hand
```

Consequently, a local extra check after the old `canPayCost` call is too late:
the private source has already affected search/bookkeeping. Rejecting a chosen
unknown source afterward also loses valid known alternatives. A hand-size test,
card-name exception, mana estimate, blanket opponent-Fog veto, temporary zone
removal, copied/replaced player, or RNG restoration is not an acceptable remedy.

## Exact Files And Preimages

Paths below are relative to the local pinned Forge root `K`:
`U/external-mtg-card-knowledge-20261105-1Uz704n2/forge/forge-61e9442c433711a82258daca3236f936a1d6f70e`,
where `U=/home/nick/.hermes/cache/scratch/mtg-jev-ui-clarity-20261025-krVbf5Hv`.

| Native Source | Complete Source SHA-256 |
| --- | --- |
| `forge-ai/src/main/java/forge/ai/ComputerUtil.java`, raw pinned upstream | `10aa934b5efca931d34d39cbcf5dcd9a703ff0145edfad3466ffbd9dc3a4937d` |
| Same file after the frozen identity patch: **delta preimage for this proposal** | `7a9341bc13900a1ad8a47a96ad29a5cba3110340ecb38895bef98669760f18d8` |
| `forge-ai/src/main/java/forge/ai/ComputerUtilCost.java` | `5fe219c35f0f7067d7c6943b85c8f7f91272b5ef88707b5b863d24fbaf16f833` |
| `forge-ai/src/main/java/forge/ai/ComputerUtilMana.java` | `46d8b049cb68379f1968fd5eac95fdd7f0544fa37551a1f21c2f9944f071d436` |

The existing patch SHA-256 stays
`221ac0ec7c0cedd3e72392bdae7692f052ac2fe6a51c7b445852e762fc030cf3`;
its `ComputerUtil.class` stays
`60ec0579438008e0c5a1eba4ef0ffde6b77f3eaf7ab9865c8fa3a2a1b97a1bfc`.
Neither frozen artifact is a target for overwriting.

Current native `ComputerUtilCost.class` is
`ecc2dfef346c7ca36993ca3d8c192313817ab7e031a611c72f2e98475dd76ccd`;
`ComputerUtilMana.class` is
`be85674769897c78dc008eca3a5949ae331dff9724e98318ffc6c76a02a8d398`.
Future outputs must have their own recorded identities. The current cost source
also emits `ComputerUtilCost$1.class`; a later explicit build must account for
all compiler-emitted nested payloads, not silently mix a new outer class with
unreviewed old inner payloads.

## Recommended API Change

Use `java.util.function.Predicate<Card> knownCard`, a plain per-call argument.
No new policy class, mutable global, thread-local, game/player/SpellAbility field,
or simulation state is needed. `null` means **legacy unrestricted payer-side
evaluation**, not a fallback for an unknown observer. Existing signatures retain
their behavior by delegating to the new implementation with `null`.

### 1. Observer Policy At The Existing Consumer

Keep the signature:

```java
boolean hasAFogEffect(Player defender, Player ai, boolean checkingOther)
```

In its body, use the existing registered `ai` as observer and existing revealed
memory as provenance. When `checkingOther` is true, pass a non-null predicate
whose policy is:

```text
currently visible identity to ai
    = canBeShownTo(ai.getView()) AND canFaceDownBeShownTo(ai.getView())
OR
existing legitimately remembered card in defender's current hand
    = REVEALED_CARDS contains card AND card owner == defender AND zone == Hand
```

The predicate may examine native visibility, identity membership, owner and zone
to decide admission. It must not first inspect the concealed card's name, mana
abilities, colors, cost, or mana potential. An immutable per-query known-card
membership snapshot is also acceptable if it implements exactly this policy.
Do not expand remembered cards into arbitrary hidden library positions.

With `checkingOther=false`, preserve the existing payer-side path with no
knowledge restriction. With `checkingOther=true`, do not drop the predicate
because the known set is empty. Public floating mana remains usable through the
existing pool logic; no speculative hidden source is invented.

Replace only this caller's affordability invocation in the new increment:

```java
ComputerUtilCost.canPayCost(sa, defender, false, knownCard)
```

This is effect-family-independent resource policy, not an ESG/Fog card-name
branch. Other callers keep the legacy API until independently authorized.

### 2. Preserve Cost Logic With Overloads

At `ComputerUtilCost.java:544` and `:547`, add:

```java
public static boolean canPayCost(SpellAbility sa, Player payer, boolean effect,
                                 Predicate<Card> knownCard)
public static boolean canPayCost(Cost cost, SpellAbility sa, Player payer,
                                 boolean effect, Predicate<Card> knownCard)
```

The existing signatures remain compatible. The original full cost body becomes
the shared implementation with the extra parameter. Preserve its activating
player handling, taxes, Ward, loyalty/Casualty checks, `extraManaNeeded`, and
additional-cost call. At the existing mana call, `:649`, forward `knownCard` to
the corresponding new `ComputerUtilMana` overload. Do not duplicate cost
arithmetic or run an unrestricted mana query before the restricted one.

### 3. Thread Scope To The First Source-Admission Gate

Add these public overloads in `ComputerUtilMana.java`, keeping their old public
signatures as unrestricted compatibility delegates:

```java
public static boolean canPayManaCost(Cost cost, SpellAbility sa, Player ai,
                                     int extraMana, boolean effect,
                                     Predicate<Card> knownCard)
public static CardCollection getAvailableManaSources(Player ai,
                                     boolean checkPlayable,
                                     Predicate<Card> knownCard)
public static SpellAbility chooseManaAbility(ManaCostBeingPaid cost,
                                     SpellAbility sa, Player ai,
                                     ManaCostShard toPay,
                                     Collection<SpellAbility> maList,
                                     boolean checkCosts,
                                     Predicate<Card> knownCard)
```

The new affordability entry still forces `test=true`. Propagate the parameter
through the following private implementations; keep legacy delegates where
needed rather than changing unrelated callers:

```java
private static boolean payManaCost(Cost cost, SpellAbility sa, Player ai,
        boolean test, int extraMana, boolean checkPlayable, boolean effect,
        Predicate<Card> knownCard)
private static List<SpellAbility> payManaCost(ManaCostBeingPaid cost,
        SpellAbility sa, Player ai, boolean test, boolean checkPlayable,
        boolean effect, Predicate<Card> knownCard)
private static Multimap<ManaCostShard, SpellAbility> getSourcesForShards(
        ManaCostBeingPaid cost, SpellAbility sa, Player ai, boolean test,
        boolean checkPlayable, boolean hasConverge, Predicate<Card> knownCard)
private static ListMultimap<Integer, SpellAbility> groupSourcesByManaColor(
        Player ai, boolean checkPlayable, Predicate<Card> knownCard)
```

Relevant current definitions/calls are at `:64`, `:74`, `:630`, `:675`, `:1107`,
`:1111`, `:1646`, `:1802` and `:1806`. At the start of each candidate's filter in
`getAvailableManaSources`, before current line `:1649`, do:

```java
if (knownCard != null && !knownCard.test(c)) {
    return false;
}
```

Only then call `getAIPlayableMana`, `canPlay`, and restrictions. Preserve the
existing battlefield/hand universe, native source ordering, mana amounts/colors,
costs, reuse limits, conversion and payment algorithm. No zone is temporarily
changed and no new mana source is fabricated.

### 4. Do Not Reintroduce Hidden Hand Data In This Search

The same file contains three direct hand-based preference reads on this payment
path. A source-only filter that left these raw hand reads would be too weak to
advertise as a known-card affordability route. Append the same argument to:

```java
private static void sortManaAbilities(
        Multimap<ManaCostShard, SpellAbility> sourcesForShards,
        ListMultimap<Integer, SpellAbility> manaAbilityMap,
        SpellAbility sa, ManaCostBeingPaid cost, Predicate<Card> knownCard)
private static Collection<SpellAbility> sparingSourcesFirst(
        Collection<SpellAbility> candidates,
        Multimap<ManaCostShard, SpellAbility> sourcesForShards,
        SpellAbility sa, Player ai, Predicate<Card> knownCard)
private static boolean canPayShardWithSpellAbility(ManaCostShard toPay,
        Player ai, SpellAbility ma, SpellAbility sa, ManaCostBeingPaid cost,
        boolean checkCosts, Map<String, Integer> xManaCostPaidByColor,
        Predicate<Card> knownCard)
private static void setComboManaChoice(Player ai, SpellAbility manaAb,
        ManaCostBeingPaid cost, Predicate<Card> knownCard)
```

Filter hand cards before computing statistics/colors at `:163`, `:981` and
`:1184`. Carry scope through the existing calls at `:735`, `:741`, `:420`,
`:1138` and `:1264`. This is the same payment dataflow, not a new card family.
When scope is null, the original full hand and behavior are retained.

The real-payment filter-prepayment helper's old call at `:1075` can retain the
old private `canPayShardWithSpellAbility` compatibility delegate. Restricted
affordability always has `test=true`, so it never enters the `!test`
prepayment/actual-payment branch. It must not switch to that unscoped route.

## Why This Actually Removes Unknown Mana Candidates

1. The admission gate is applied to every card in the native candidate universe,
   not only hand cards, named cards, or the first chosen payment.
2. For an unrevealed, unremembered hand card, the observer predicate is false
   before its mana abilities or eligibility are evaluated.
3. Color grouping and shard maps are built only from the admitted hosts. Sorting,
   alternative choices, test-mode reuse and filter activation costs operate on
   those maps; they do not obtain a second unrestricted source inventory.
4. The three direct hand-statistic readers use the same knowledge predicate,
   rather than using a concealed non-source card to steer the restricted search.
5. Genuine known sources are still evaluated by native rules and costs. Public
   Forest, public/remembered hand mana, and public floating mana can establish a
   payment; an empty known source set does not blanket-disable the heuristic.

For the demonstrated strict pair, the unrevealed enabler cannot enter either
observer's source map. That removes the private input itself. Matching attack
choices/RNG would then be an observed consequence, not the mechanism of the fix.

This is specifically a known-mana-source correction, **not a proof that arbitrary
native costs are observer-complete**. Existing additional-cost, ability-script,
replacement/reflection and conditional-source hooks still execute native code.
For example, `canPayShardWithSpellAbility` at `:1222` can consult a held-piece
heuristic for a discard-hand mana cost. That branch is not the demonstrated
enabler and is not independently explored here. Do not infer it is safe from
26 passes. If the scoped route needs another production file or broader semantic
changes to handle such dependencies, stop and propose that separately; do not
add a blanket true/false fallback or silently drop observer scope.

## Acceptance Before A New Increment Is Qualified

The following are requirements for a later authorized implementation, not results
claimed by this document:

1. Keep all six follow-up checks byte-identical: current 2 RED / 4 PASS becomes
   **6 ordinary PASS**, actual attack choices and actor views included. Do not
   suppress/assert-away the two strict nodes or only normalize RNG.
2. Keep the original twenty controls unchanged and all twenty passing. Preserve
   known Fog, currently visible/remembered cards, public external/permanent Fog,
   public mana and tapped/unpayable behavior, both seats.
3. The follow-up's separate unrestricted owner-side source-list diagnostic is
   allowed to differ between concealed variants. It measures the payer's lawful
   knowledge, not the observer's. Do not make the owner API ignorant to force
   that diagnostic equal.
4. Add a narrowly matched, same-enabler positive control in both seats where the
   mana source is legitimately revealed/remembered. It must still fund known Fog
   under native costs. This prevents a false solution that bans all hand mana.
   No independent family or randomized cohort is proposed.
5. Compare legacy owner-side truth/payability with the unmodified route. Keep
   actual payment on legacy APIs, with no private-zone edits, source consumption,
   invented mana, forced outcomes, shared simulation writes, or RNG resets used
   to conceal an information dependency.
6. Audit the source gate and scoped call graph as well as running tests: no
   rejected source's mana abilities are inspected; no nested fallback regains
   unrestricted source enumeration. Record before/end origins and hashes for
   every explicit new payload and unchanged supporting native resources.
7. Build only the three authorized sources and their actual emitted nested
   payloads in a fresh owned shadow, with original notices/preimages. Preserve
   K/Q, all frozen source/tests, the existing candidate, and parent profile
   builder. Archive private state/RNG/traces to mounted writable NFS and verify
   readback before cleanup.

The parent must separately compose that new shadow with its profile builder
(parent-reported `27e9` increment), assign a new content/build identity and
requalify the application/native lifecycle and save compatibility as applicable.
The parent-reported completed application run does not substitute for those
checks. SaveCore and the full fairness goal are not declared complete here.

## Alternatives Rejected

- Only change `hasAFogEffect`: no existing cost API accepts a knowledge boundary;
  implementing another mana solver or mutating a payer is larger/less faithful.
- Validate the returned selected-source list: private choices have already run,
  and rejecting one selected source can discard a legal known alternative.
- Only filter `getAvailableManaSources` globally: breaks owner-side mana and
  affects unrelated callers; the correct boundary is an explicit per-call scope.
- Disable opponent Fog or unknown-hand positions: loses required public/known
  positives instead of evaluating native cost using authorized information.
- Thread-local/global filters, temporary cards/zones/controllers, or RNG repair:
  implicit/shared state and observation laundering, not a knowledge correction.

Approval requested is limited to this three-file API/dataflow increment and its
same-enabler qualification. Until approved, the only authored file is this
proposal; all executable artifacts remain frozen.
