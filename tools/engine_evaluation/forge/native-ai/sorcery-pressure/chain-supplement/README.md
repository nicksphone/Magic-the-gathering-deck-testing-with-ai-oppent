# Three-Cast Chain Supplement: Tests Only

Separate from the frozen original eight-case family. The first declared run is
**2 RED / 0 PASS / 0 errors**, closed with exit1. No production change, rerun or
policy/cost diagnostic evaluator is included.

## Declared Gate

Two seats, two native games total, one game per seat. Each starts at own MAIN2,
own20/opponent20, hand three full canonical Lava Spikes and three untapped
Mountains, with no other battlefield cards or effects. Each successful native
decision must pay, enter the stack and resolve before the next fresh chooser
call. The intended end state is the three original source IDs in graveyard,
hand0, three tapped Mountains, pool0, opponent11, own20, native game nonterminal.

Seed `2026110617` is set once before model initialization. No reseed, hand
rewrite, counter mutation, phase reset, forced cast/outcome or saved-choice
reuse occurs. A native decline stops its case immediately; there is no
same-state retry or artificial attempt to continue to the third cast.

## Actual Closed Result

Both seats/native game IDs1 and2 behave identically:

1. Choose Spike18, pay Mountain17, resolve20 to17. Spike18 reaches graveyard.
2. Fresh native choice declines. Spikes20/22 remain in hand; Mountains19/21
   remain untapped; own20, opponent17, empty stack and pool0. Game nonterminal.

The declines took12.390740ms and6.299189ms against the unchanged native5-second
decision limit. Decision3 and the final desired assertion are not reached.
This is the expected behavioral RED, not a harness error or a claim that all
three casts succeeded.

## Source-Level Cause

Under this constrained empty-board position, the rejection is explained by
`DamageAiBase.shouldTgtP`: the low-life shortcut at line101 is false for either
single3 or paired6 damage against17. Hand2 is not over the native default
maximum7. The `hand.size() > 2` guard at line116 then skips the entire chance
block and falls through to false at line151. This is not merely an unlucky
`nextFloat` or the0.2 floor: the hand-size guard prevents that chance branch.

The current DamageDealAi source (SHA53e892f0...) still requires `shouldTgtP`
inside its MAIN2 timing branch, lines708-715. With no target it returns false
at745-746; `canPlay` returns `TargetingFailed` at260 or277 depending on whether
the existing pair estimator was attempted. The pair estimator does not rescue
hand2 against17. `AiController` clears next-spell source reservations at1686
on every fresh chooser call; reservation is not a promise to force the second
spell. Ordinary hand Lava Spikes do not satisfy `ComputerUtil.playImmediately`.

This is a source-constrained path explanation matched to actual hand/target/
phase/mana observations, not an instrumented branch-local trace. No evaluator,
cost query, random draw or counter was repeated to create a causal label. No
additional diagnostic override was prepended to the required seven-class
prefix. Production work, if desired, requires a separate grant and verification.

## Reproduction And Preservation

```bash
bash test.sh "$QUALIFIED_BASE_IDENTITY" "$CURRENT_SEVEN_CLASS_SHADOW" "$FRESH_LOCAL_OUTPUT"
```

One isolated native engine JVM,180-second wall bound,1500MB heap and one active
processor; the native decision clock is unchanged. Output must be local.
`PREFIX-PIN.json` pins the same parent d36d composition, including DamageDealAi50a0
and held-piece Mana4217. Base sources and complete canonical programs are
checked before/after. No original test is compiled or loaded. `FROZEN8-PIN.json`
preserves all twelve original source files, both original compiled test classes
and four original archive metadata files. The original eight remain8/8 PASS;
this supplement does not change or relabel that evidence.

Full private per-choice/payment/resolution records, class origins, pins and
source-cause evidence are archived separately. No app/UI run, SQL/database,
model/network/external service, commit/push or graph update is performed.
These are canonical constructed positions, not natural-game quality evidence.
