# Canonical Sorcery Pressure: Tests Only

The first and only declared run passed all eight positions. No behavioral RED
was obtained and no product change is granted or supplied here. Do not relabel
this as a RED/GREEN fix, a native policy defect, or general Burn competence.

## Declaration

`DECLARATION.json` fixes seed `2026110617` and exactly four scenes in both seats.
The RNG provider is initialized once before model initialization and any game;
there is no late reset, seed search or policy retry. All positions have three
native Lava Spikes in hand, three native Mountains in play, own life20, empty
creature boards, and no other battlefield cards, taxes, prevention, Eidolon,
counters or lifegain. Eight canonical Runeclaw Bears per library avoid incidental
empty-library losses; these are explicitly constructed scenes, not full games.

| Scene | Phase | Opponent Life | Red Sources | Expected Behavior |
| --- | --- | --- | --- | --- |
| pressure | Own MAIN2 | 20 | Three untapped | At least one recognized, paid, resolved Lava Spike |
| lethal | Own MAIN2 | 3 | Three untapped | Paid Lava Spike, native damage and native winner |
| unfunded-lethal | Own MAIN2 | 3 | All three tapped | Decline without paying/moving cards |
| upkeep-lethal | Own UPKEEP | 3 | Three untapped | Decline the illegal sorcery timing |

The style expectation was declared before execution: use at least one red mana
for recognized nonlethal pressure, not a universal spend-all-mana rule. There
is one real Default chooser call per case, before any profile/snapshot
diagnostics. No `canPlay`, cost forecast or damage forecast is called by the
harness to prime the choice. If chosen, the exact native ability is passed to
`playWithRollback`, then the native stack resolves and native state-based
actions determine life and outcomes. No target, winner, card body, hand or RNG
state is rewritten after the first choice. The harness never forces a cast.

## Actual Baseline

Both pressure cases select one canonical enemy-targeting Lava Spike, pay one
Mountain, and resolve opponent20 to17 while own life stays20. Both lethal
controls pay one Mountain and end in a native win. All four cost/timing
negatives decline without mutations. Result: **8 PASS / 0 failures / 0 errors**.
The scratch output folder was initially named `red`; its actual result is
passing, not a reproduced RED. No expectation or seed was changed afterward.

This does not test another chooser invocation after resolution, use of the
remaining two Mountains, every RNG outcome, a natural game or broad competence.
The earlier isolated `3/20 < 0.2` source observation is not a sufficient
prediction of the whole native chooser. Existing `DamageDealAi.canPlay` first
asks `getDamagingSAToChain`, can test damage with the paired amount, and can
reserve mana for the next spell. Default's actual loaded
`CHANCE_TO_CHAIN_TWO_DAMAGE_SPELLS` value is90. That is an existing ABI, not a new
knob or profile; no passive branch trace was captured to prove which path
admitted these particular casts. No evaluator was rerun to obtain one.

## Pins And Reproduction

The prefix is the current **seven-class** coupled tactical shadow, content ID
`d36d96612e9b770575dd7de4a40b17fce8bccc23ec8dac66002e557d9e7b3d29`,
not the old ff89 layer. `PREFIX-PIN.json` retains its five-source/seven-payload
manifest, including known-held-piece mana, ActorBoundary and DamageDealAi50a0.
All seven payload hashes are checked before and after the run; observed loaded
origins are checked without forcing unused classes to load. ActorBoundary's
`Pending` nested class is pinned but was not observed loaded in this family.
Reviewed base Java/profile sources and all three full canonical bodies are
also pinned and checked. The old26 source is unchanged and is not rerun here.

```bash
bash test.sh "$QUALIFIED_BASE_IDENTITY" "$CURRENT_COUPLED_TACTICAL/shadow" "$FRESH_LOCAL_OUTPUT"
```

The runner compiles only this test and uses a network-isolated sandbox with
one native engine JVM, 1500MB heap, one active processor and the existing native
decision clock. Output must be a fresh local directory, not NFS. No dependency,
SQL/database operation, application run, model access, production compilation,
profile publication, old-test edit, commit or graph update is involved.

Full private choices/snapshots, actual payment/outcome records, class-load logs,
pre/post source/payload checks and the fixed declaration are retained as test
evidence. Native initialization warnings remain in stderr; they are not hidden
or counted as behavioral failures. See [NOTICE.md](NOTICE.md) for provenance.
