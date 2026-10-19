# Observer, Flash And Simulator Composition

Date: 2026-10-06 UTC. Base: eec69bebab5b4084f4598063e272831d279712ed.
This is scoped backend acceptance, not a deployment or full-release certificate.

## Changes

- Generic supported nontoken creature-entry matching; preserve existing cast
  observer paths, token exclusion, controller predicates and ability suppression.
- Pure unconditional global flash permission from an active controlled source.
  Preserve real priority, mana, source lifetime, explicit casting restrictions
  and prohibitions; no extra land plays or off-turn loyalty permission.
- Attribute batch opening-hand quality to deck identity after seat alternation.
  The statistics change does not modify game winners or AI decisions.
- Replace the obsolete unsupported-Leyline recast characterization with actual
  paid creature recast, restored snapshots and old-trigger incarnation rejection.
- Isolated flash HTTP fixtures preserve the default database bytes even when a
  preceding standalone test legitimately created that disposable database.
  Memory repository overrides remain isolated; live/main database access is fenced.

## Authoritative Gate

Ten complete modules: **293 passed, 1023 warnings, 60.41s, exit 0**.
JUnit and before/after captured source hashes are retained with the evidence.
No skips, expected failures or deselections.

Fresh configured frontend `npm test`, `npm run lint` and `npm run build` all
exit 0, using the declared qualified Python environment for backend-rendered
contracts. The initial invocation omitted `MTG_TEST_PYTHON` and stopped at its
explicit setup assertion; that log is retained separately. No frontend source
change was necessary.

| Module | Cases |
| --- | ---: |
| Creature observer audit | 56 |
| Creature observer fix | 26 |
| Batch deck-identity quality | 3 |
| Analytics batch | 47 |
| Canonical global flash audit | 72 |
| Global flash product | 40 |
| Restrictions | 7 |
| Mulligan and timing | 4 |
| Activated ability timing | 14 |
| Canonical magecraft self-pump | 24 |

Earlier scoped gates overlap and are not summed. Historical whole magecraft
22-pass/2-fail results reflected the former unsupported recast assertion. The
first final composition had 269 passes and 24 API-fixture setup errors because
the fixture assumed no disposable root database existed. Both ledgers and test
preimages remain archived; the final gate above uses the documented adaptations.
All other magecraft test functions and all 40 flash test functions are preserved.

## Inputs And Evidence

Frozen observer integration: 3f1cfc3ed01829a32786e7c14823444625e5628d5cc4c4859ee2560f3cad97e3.
Frozen flash inputs: dependency 386424eb9225fdb2dfea3d1e6ddbb7f6cc547c67bba2a1dda131050c94543eb8;
production 8e957fe8fd9ac32d973334ccb0189ffc5ade29ed49ca8d64e97d369ac921fc22;
tests/docs 4419cf8bd5454527f9336594a0947a3fd9816530062d9951d511ea070091c6a9.

Completed evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/observer-global-flash-simulator-20261006/`.
The unchanged Scout/Atlas historical audits remain separately archived with
their original failures; their eight-case supplement passed on the newer
published candidate before this composition. These histories are not relabeled.

## Known Limitations and Next Upgrades

Conditional/scoped/quoted/activated timing grants are not admitted by this new
unconditional grammar. Direct layer/control fixtures are not causal spell
episodes. Memory HTTP and snapshot checks are not full browser/LAN games.
No frontend source changed; configured tests/lint/build are not a full browser
acceptance. Broader rules, counter/search/catalog composition, expert
AI measurement and release/deployment gates remain unfinished.
