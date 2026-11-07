# Fallback-Only Sorcery Pressure

Separate two-source/two-class increment over the qualified592 base and frozen
d36d seven-class parent. Parent owns eight-class composition, profile approval,
application qualification and publication. No such qualification is claimed here.

## Product Delta

`DamageAiBase.shouldTgtP` retains its four-argument entry with pressure disabled.
Its five-argument body preserves the existing target, lifegain, avoidTargetP,
life-loss, prevention/NoPrevention forecast and low-life checks. Only afterward
may the opt-in approve positive forecast damage for a direct noncompound
targeted DealDamage sorcery spell at the actor's own MAIN2. Every current
selector root must be Player/Opponent/Planeswalker, with a player alternative.
Any, Card, creature-capable and mixed categories do not qualify.

Only DamageDealAi's final player-target fallback opts in. Earlier PW choices
and every other four-argument caller keep their existing policy. Ordinary
hand-size/chance rules remain intact outside this semantic exception. There is
no card/deck/seed/hand2 condition, global playImmediately change, forced cast,
duplicated safety implementation or added native damage forecast. The existing
restDamage is reused; downstream cost, tax and own-cast safety remain native.
Native helpers/conditions may consume authored randomness: this is not a
universal RNG-purity claim. No direct RNG call/reset is added by the product.

## Actual RED / GREEN

The same corrected harness and declaration ran against baseline and candidate:

| Cohort | Corrected Baseline | Candidate |
| --- | --- | --- |
| New canonical controls | 34 PASS / 8 pressure RED | 42 PASS |
| Unchanged chain2 check methods | 0 PASS / 2 RED | 2 PASS |
| Unchanged original26 check methods | 26 PASS | 26 PASS |
| Total | 60 PASS / 10 RED / 0 errors | 70 PASS / 0 failures / 0 errors |

Both-seat hand1/2/3 Lava Spike chains pay and resolve every original card;
independent Lava Axe pressure also pays and resolves. PW kill is preserved
using genuinely native-chosen/paid Nissa entry with printed loyalty5, not
manually assigned counters. Volcanic Hammer still kills the canonical creature
and is held on an empty board. Instant, sorcery-speed activated, MAIN1, upkeep,
opponent-turn, prevention, hexproof, unfunded, Chill-tax, own-Eidolon,
self-damage, fixed-life and opponent-lifegain preservation controls pass.
Flames of the Blood Hand bypasses Glacial Chasm using its complete native
NoPrevention program and pays/resolves a native lethal outcome.

The original check methods/assertions and source bytes are unchanged. They are
invoked reflectively by this new driver, not by editing their frozen verifiers.
One seed is set before model initialization and all cohorts; no later reset.
These are exact new-runtime check-method cohorts, not claims of rerunning the
old standalone main programs with their historical random histories.

The first fixture-development run is retained separately: two PW setup
assertions used a stale pre-entry Nissa reference. Native zone changes clone
card incarnations. Only the new harness was corrected to read game.getCardState
and native loyalty, then the corrected RED ran before any product patch.
No expectation, native body or counter was changed to hide that issue.

`VERIFIED-CLOSED.json` counts live under `cohorts`; its other fields include
`unexpected_controls`, `errors`, preserved pins and loaded origins. Aggregate
`passed`/`failures` are in `summary.private.json`. All gates are terminal.
The 38 knowledge controls were not run by this worker; parent owns that gate.
No natural game, UI, save compatibility or broad all-cost fairness claim follows.

## Build And Test

```bash
python3 build.py "$BASE_IDENTITY" "$CURRENT_SEVEN_CLASS_SHADOW" "$FRESH_BUILD"
python3 test.py "$BASE_IDENTITY" "$CURRENT_SEVEN_CLASS_SHADOW" "$FRESH_BASELINE_RUN"
python3 test.py "$BASE_IDENTITY" "$CURRENT_SEVEN_CLASS_SHADOW" "$FRESH_CANDIDATE_RUN" "$FRESH_BUILD/shadow"
```

The builder pins both preimages, applies the zero-fuzz patch, compares the two
published copied source bodies, and permits exactly two emitted classes. Its
content identity binds source/class/patch/builder/JDK/base/parent pins without
including output-directory names. Test runtime is new-layer:unchanged-parent:
qualified-base, with a separate test-class directory. Nothing modifies the
parent prefix or profile. Engines are sequential, one active at a time, with
180-second outer bounds,1500MB heap, one processor and unchanged native clocks.

Layer ID: `6f472ce54673908d08908673432f9097c7005038f3e799060be9a964a017677b`.

| File | SHA256 |
| --- | --- |
| DamageAiBase.java | 70312adb62cbf3ab8a0f06d0405c2be9c0858715bcb6c2d86818b1ec03cde8bd |
| DamageDealAi.java | bac01d37456a32978a406fc5875ab5f5ab0305461bcdb1f157916589ca73a129 |
| DamageAiBase.class | 45a6feaea78d0a7321cf29879a67a2ede0d658b50c189d38c9d002c0ac6cfa7e |
| DamageDealAi.class | 546e795cd1ea20e0de5912127f9b5e3a93a6214693df87882066a8e705c2567f |

No SQL/database, network service, protected model, dependency, workflow,
profile-builder, existing source, graph update, commit or push is involved.
Private evidence retains all intermediate/RED/GREEN logs and predecessor pins.
See [NOTICE.md](NOTICE.md) for upstream attribution and canonical provenance.
