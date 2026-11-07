# Linked Damage Lethal Audit

Tests only. The initial strict declaration is twelve Default AI cases: both
seats for genuine-land-entry and nonlandfall damage versus Topiary Stomper,
killable Bear landfall, no opposing creature, opposing player hexproof and
unfunded mana. All opponents begin at one life. Positive cases require native
choice, native RR payment, complete linked targeting, resolution/SBA and native
victory. Negative cases require an unchanged physical pose and no choice.
One chooser invocation per AI game precedes diagnostic queries; no retry or
RNG reset is used. Physical snapshots are plain getters, not evaluators.

Six additional SEPARATE games are manual trusted-legal-action controls, not AI
successes. They explicitly declare the three positive scenes' player/creature
targets and pass through native target validation, payment, stack and resolution.
They occur after all twelve AI cases. No manual control can rescue an AI RED.

Libraries contain eight canonical Runeclaw Bears per player. Existing battlefield
cards use AITest poses; Topiary's ETB search is not fabricated. Landfall is
created only by legally playing a Mountain from hand with native Player.playLand.
No body/SVar/history/counter repair, free cast, forced outcome, evaluator retry,
native clock change, production patch or replay ABI work is included.

The runtime is exactly the separately qualified eight-class prefix
`3f595b71da5b339b2c9f5f6bced98fb25291db7d55c6427835d52b6d532e38ee`
before qualified592 base. Profile414 is provenance only, not launched here.
Parent owns every prior source, graph, profile, publication and application gate.

Run once in a fresh LOCAL output directory:

```bash
python3 run.py BASE_BUILD_IDENTITY EXACT_EIGHT_CLASS_SHADOW FRESH_OUTPUT
```

The runner pins canonical programs, the prefix, existing source/tests, base
identity, native source inputs and runtime classpath before/after. It compiles
only this new test class, then uses one network-isolated engine JVM with the
unchanged native clocks, 180-second outer bound,1500MB heap and one processor.
Initial behavioral RED expectations remain strict; results are not yet known.
