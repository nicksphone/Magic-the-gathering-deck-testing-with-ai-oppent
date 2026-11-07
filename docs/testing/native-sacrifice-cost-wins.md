# Native Sacrifice-Cost Wins

## Reproduced Defects

The native Default AI passed funded winning sacrifice activations. Unchanged
Drain8 passed 6/8, with both Oven/Blood Artist wins missed. The separate Timing6
passed 2/6: both Village Rites choices worked, both Oven and both Viscera Seer
choices failed. Actual manual native payment/trigger controls won after those
declines. These overlap: they are not six unrelated defects or natural games.

Two gates mattered. API-specific timing deferred profitable sacrifice costs.
Separately, `AiController` removed Viscera Seer's `AI:RemoveDeck:All` ability
before the now-willing API evaluator could be asked. A shared forecast, not
named-card policy branches, now informs both gates.

## Final Source And Results

The [portable family](../../tools/engine_evaluation/forge/native-ai/sacrifice-timing/README.md)
contains the unchanged three Java audit sources, complete native programs,
preimages, patch, attribution, GPL license and exact pins.

- Candidate content: `7998ea519b319759b22abe1db526229be053914ffce643aa7d6f802e366a77d9`.
- `SpellAbilityAi.java`: `e3ae29b8137219293c28a7597579fd75c3c6088d637b6415b96cb0c73312a5c2`.
- `AiController.java`: `e8a7ae4d39b73a9f95c70dbae2b5c54e75b3c1a7cdfb14c6fa2e013026b563e7`.
- Final portable 8+6+8: 22 PASS, exit 0, 47.36 seconds, three fresh native JVMs.
- Final separate internal-protocol 8 and 4: all PASS, exit 0; no ordinary AI
  callback or strategic-game claim. The checks include hidden-body rejection,
  effective override precedence, unknown body refusal, combined zone selectors,
  runtime API agreement and unchanged RNG/ability allocator/trigger cache.
- Synthetic profile compatibility: all 32 tests PASS. Both new acceptance tests
  first failed on the unchanged schema-8 validator, then passed with schema 9.

Schema 9 requires exactly twelve sources and twenty classes. All preceding ten
sources and seventeen classes are unchanged. The code only adds the shared
forecast and candidate-filter exception; it does not change native rules,
cost execution, card programs, profile difficulty or turn handling.

## Boundaries And Retained Failures

The forecast only handles ordinary one-creature sacrifice costs and complete,
literal public death-drain/gain chains. All eligible payment victims must satisfy
its estimate. Visibility is checked before body reads. Known replacement,
protection, suppression or unmodelled public-trigger uncertainty withholds the
preference override. Normal rule and payment gates remain. It is not a complete
replacement predictor, general winning-line solver or full fairness certificate.

Initial review exposed reading an ability before its visibility check and
crediting the printed SVar instead of an effective native override. The new
internal eight-case baseline gave 2 PASS / 6 RED; the correction gave 8 PASS.
A later API-consistency four-case baseline gave four strict protocol REDs,
then four PASS. Its initial draft incorrectly required the changed child API's
manual outcome to be nonwinning; those two test-harness failures remain archived,
not classified as gameplay defects. API tags and a cached native effect are not
an unrestricted adversarial-object validation contract.

All previous candidate source, compile results and gates remain separate.
The preservation worker's native eight assertions passed, but its wrapper
rejected blocked socket attempts. Those log entries say `canary=no`; their
callsite was not attributed, and they are not relabelled as deliberate canaries.
A separately declared final parent suite and portable suite both completed.
The portable suite makes no native-SQL-denial claim.

Four source-pinned natural games on preceding candidate3 (Drain/Dimir and
Drain/Tribal, both deck orders, seeds 2026110611/12) completed without native
errors. Drain lost all four, as in the old-prefix sample. These are not a
strategic strength gain or final-candidate4 natural-game qualification.

## Still Open

- Both-seat native Oven -> Food -> Familiar wins without Blood Artist remain
  ordinary-choice RED; actual manual two-action controls win. The new immediate
  death-cost preference does not close that longer planning problem.
- Public delayed-trigger registry interactions, self-sacrificing creature outlet
  preferences, broad strategic play and general hidden-information safety need
  further qualification. No observer-safe full-game copier was found: the native
  copier reads actual private hand/library identities before copying.
- Application adoption, durable BO3, useful learned policy and release acceptance
  remain open. No live profile was switched by this work.
