# Conditional-Mana Source Qualification

## Result: Source Excluded, No Fairness Verdict

The single inspected candidate is pinned **Charmed Pendant**. It is not a
qualified reproducer for the ordinary opponent-Fog affordability route on native
candidate `75d4ac3971e7f970d2e3c62ba12f25aba639eba5fd36d0ed2f930a4ea17511b7`.
Its canonical program has `InstantSpeed$ True`; native `getAIPlayableMana(Card)`
unconditionally excludes an ability with that restriction. This happens before
produced-color inspection or the mana source's additional-cost checks.

**Executed decision checks: 0. RED: 0. PASS: 0. Native controller callbacks: 0.**
There is no same-public-view attack/payability result, paired RNG result or
known/public-positive result to report. No artificial library-top regression,
changed restriction, guessed source behavior or assumption-based PASS test was
authored. No alternate source/family was hunted after this exclusion. This
source negative is not a broader fairness, forecast-correctness or strength claim.

## Exact Knowledge/Call DAG

Locations below refer to the immutable retained 75d4 `candidate/source/` and
pinned Forge `61e9442c433711a82258daca3236f936a1d6f70e`.

| Stage | Exact Native Function / Gate |
| --- | --- |
| Fog identity admission | `ComputerUtil.java:1576`, `hasAFogEffect(defender, observer, checkingOther)`: actual observer visibility, including face-down identity visibility; legitimate native remembered defender-hand reveals are added separately. |
| Knowledge policy | Same file `:1602`: `knownCard` is null for own/unrestricted calls; otherwise actual visibility OR remembered card still in the defender's hand and owned by defender. No open-decklist inference grants present private-zone identity. |
| Cost forwarding | Same file `:1625` calls `ComputerUtilCost.canPayCost(sa, defender, false, knownCard)`. Cost source `:549` forwards the predicate and `:659` calls scoped mana affordability before the Fog's own additional-cost check. |
| Mana graph | `ComputerUtilMana.java:70` -> scoped cost `payManaCost` overload -> `:657` mana-cost overload -> `:703 getSourcesForShards` -> `:1140 groupSourcesByManaColor(..., knownCard)`. |
| Public source admission | Same file `:1868` calls `getAvailableManaSources`; `:1707` applies `knownCard` to each actual battlefield/hand source **before** inspecting that source's abilities. A genuinely public Pendant may pass this knowledge gate; publicness alone does not make its ability usable. |
| Decisive exclusion | Same file `:2040`, `getAIPlayableMana(Card)`: after the Mana/ManaReflected API and mana-cost gates, a non-null restriction with `isInstantSpeed()` causes `continue`, before adding the ability to the result. No observer knowledge, library identity, seat or RNG condition can bypass this branch. |
| Downstream paths not reached for Pendant | Color grouping `:1872` / `:1898` / `AbilityManaPart.canProduce`, and `canPayShardWithSpellAbility(..., knownCard)` / `CostPayment.canPayAdditionalCosts` for this source. |

Pinned `SpellAbilityRestriction.java:107` maps presence of `InstantSpeed` to
`setInstantSpeed(true)`. The complete canonical Pendant script is preserved in
`canonical/charmed_pendant.txt`, not a modified Oracle or ability.

The **actual candidate class file** was independently disassembled with Q's
pinned `javap`. In `getAIPlayableMana`, bytecode offsets 84-101 check the
restriction and jump back to the iterator on true; ability insertion starts at
104. This agrees with the source gate. This is class-byte inspection, **not** a
native runtime load-origin or actual-decision observation.

As separate context, native `CostMill.canPay` checks the public library count,
not top-card identity. `ManaEffect.java:237` resolves `EachColoredManaSymbol`
from `AbilityUtils.getDefinedCards(..., "Milled", ...)` after milling; such
already-milled/public information is not itself an illicit concealed-top read.
Neither fact qualifies Pendant for this forecast route or establishes safety
of other costs, colors, replacement effects or global conditions.

## Pins, Scope And Evidence

[SOURCE-PINS.json](SOURCE-PINS.json) records the exact candidate manifest,
three source hashes, all four class hashes, canonical script and primary native
source hashes, Q identity and disassembler hash. Before/end input comparisons
and the disassembly are retained privately. No old tests are rerun or relabelled.

Only new files in `conditional-mana-followup/` and fresh owned local scratch are
written. Existing 75d4, E, Q, upstream, source ca81, tests/patches, profiles and
parent's composed candidate are unchanged. No game JVM, simulation, app, SQL,
network/dependency install, protected model body, secret or external AI is used.
The only JVM tool is a bounded local `javap` process with 256 MiB heap and one
active processor. No graph update, commit, push or publication is performed.

Evidence directory:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/native-conditional-mana-20261106-lNZfmFXF/`.
It contains complete inspected source copies, GPL attribution, canonical script,
exact input pins, bytecode and before/end verification. [EVIDENCE.json](EVIDENCE.json)
records mounted-writable NFS and full archive readback before owned scratch cleanup.

Missing coverage remains a reachable public mana source whose constrained
additional cost or generated colors depend on an observer-unknown card, with
actual native attacks/payability, both seats, matched actor views and incoming
RNG, plus independent known/public positives. This task does not supply that
coverage, authorize a production change, or qualify the parent's composed app.
