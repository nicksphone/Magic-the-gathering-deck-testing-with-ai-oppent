# Targeted Draw Decisions

This is a two-line modification of the Forge Team/Card-Forge `DrawAi`, not a
replacement rules engine or an AI authored from scratch. Full upstream source,
copyright headers and GPL-3.0-or-later terms are retained in `preimage/`,
`source/` and `LICENSE`. Canonical card scripts are unchanged copies of revision
`61e9442c433711a82258daca3236f936a1d6f70e`.

## Correction

Native `targetAI` can deliberately select an opponent for a winning draw spell.
`checkApiLogic` then contradicted that decision with a zero-rated rejection.
The new return accepts that already-selected opponent with rating 100. Ordinary
native legality, costs, target selection and linked drawback checks still apply.
The later self-draw timing/loot/sacrifice heuristics are not used for this early
opponent-target path. Arbitrary curse/linked/trigger interactions are not claimed
as separately qualified.

The decking predicate now requires drawing **more** than the library size.
Drawing exactly two cards from a two-card library, or four from four, does not
cause an immediate empty-library draw loss. Existing other target-selection
branches remain unchanged.

## Executed Evidence

The same 22 AI cases produced 12 passes/10 strict failures before the product,
then 22 passes/zero failures or errors afterward. These include the unchanged
original 12 checks and ten added both-seat equality, empty-library, funding and
Platinum Angel controls. Four separate explicit-target paid executions establish
the equality boundary; they are trusted execution controls, **not AI passes**.

All positive AI cases use a fresh Default chooser, genuine land payments and
native stack/resolution/outcomes. There is one declared seed before model
initialization, no late RNG restore or repeated chooser to repair a decision.
Controlled poses are not full games or a strategic-strength benchmark.

The parent independently rebuilt `DrawAi.class` byte-identically and composed
exactly seven sources/nine classes. That single prefix passed the 22 AI checks
and four separate boundary executions, existing 70 pressure/safety checks,
38 knowledge checks, 48 boundary checks and four synthetic empty-source checks.
The profile's 24 labelled synthetic tests include the old 22 unchanged and
require an explicit complete schema-5 bundle before artifact reads.

## Reproduction

Given the qualified base identity and exact eight-class parent prefix, create
one fresh local directory named `native-targeted-draw-policy-*`, then run:

```sh
python3 test.py baseline "$BASE_IDENTITY" "$EIGHT_CLASS_PREFIX" "$FRESH_ROOT"
python3 test.py build "$BASE_IDENTITY" "$EIGHT_CLASS_PREFIX" "$FRESH_ROOT"
python3 test.py candidate "$BASE_IDENTITY" "$EIGHT_CLASS_PREFIX" "$FRESH_ROOT"
```

The builder requires the recorded strict baseline, applies `DrawAi.patch` with
zero fuzz/offset, compares the complete postimage and emits exactly one class.
The new runner permits descendants of the recorded baseline commit and records
actual HEAD; it does not require a future checkout to retain the old HEAD.
Do not edit the frozen predecessor audit or run a database from NFS.

This component does not switch the live opponent or model weights. App adoption,
durable saves/BO3, broader fairness and strategy coverage remain separate.
Private game/RNG/hand evidence is archived privately, not published as fixtures.
