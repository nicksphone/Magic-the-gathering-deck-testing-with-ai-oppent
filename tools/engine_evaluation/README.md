# External Magic Engine Evaluation

These original test adapters exercise the Forge and XMage contributors' card
implementations. They are not replacements for either upstream engine and do
not bundle their code or card programs. See [the third-party notices](../../THIRD-PARTY-NOTICES.md).

## Pinned Sources

| Project | Revision | License |
| --- | --- | --- |
| [Forge](https://github.com/Card-Forge/forge) | `61e9442c433711a82258daca3236f936a1d6f70e` | GPL-3.0-or-later source headers; accompanying GPL v3 text |
| [XMage](https://github.com/magefree/mage) | `987fd4e9c73e9f113e235f8d8f98628f2d391667` | MIT |

Original upstream notices were retained. Our Forge adapter's GPL marking is
specific to that file; the app's root Apache license does not override it.

## What Was Executed

Both adapters run native paid spell paths on constructed boards, for both seats:
Cloudblazer's gain-two/draw-two ETB, Growth Spiral's draw and optional land,
Inspiration's selected player draw, and Ray of Command's initial control,
untap and haste. Forge checks tapped mana sources; XMage additionally attacks
with the borrowed creature. Inspiration targets self in the Forge fixture and
the explicitly selected opponent in XMage. These are common mechanics, not
identical performance inputs or automatic target-quality tests.

Neither adapter certifies Ray's later loss-of-control trigger, copied-source
lifecycles, BO3 or expert AI strength. The upstream card programs/Oracle text
were not replaced or shortened.

## Running The Adapters

Use disposable checkouts of the pinned revisions and their documented build
prerequisites. Copy the Forge adapter into
`forge-gui-desktop/src/test/java/forge/ai/simulation/` and the XMage adapter into
`Mage.Tests/src/test/java/org/mage/test/cards/compatibility/`. Retain the license
and source notices when copying. Then run the specific classes with Maven:

```sh
# From the Forge checkout; upstream reactor dependencies are compiled as needed.
mvn -pl forge-gui-desktop -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=forge.ai.simulation.ExternalCardKnowledgeTest test

# From XMage after installing its required reactor dependencies.
mvn -pl Mage.Tests \
  -Dtest=org.mage.test.cards.compatibility.LocalCardKnowledgeSmokeTest test
```

Our observed runs used Maven 3.9.11, a complete Temurin JDK 21.0.13+9, separate
local caches/homes and network-isolated native test processes. Dependencies were
prepared separately. They did not use the app's live database or private traces.

Detailed coverage JSON and full canonical references are preserved with the
archived evaluation evidence, not bundled into the app. They record definition
matches for the shipped 155-card reference plus 32 harder cards. XMage basic
lands live in its core module, not `Mage.Sets`. Presence is not a gameplay pass.

See [the results and limits](../../docs/testing/external-engine-card-knowledge.md).

## Native Forge BO3 Probe

[`forge/native-match/NativeMatchProbe.java`](forge/native-match/NativeMatchProbe.java)
is our original GPL-3.0-or-later caller of the Forge Team's native match engine,
not our own card/rules implementation. Its source header credits the upstream
authors and exact revision. The [original Forge license](forge/LICENSE) applies
to this separately marked probe; retain it and the upstream notices.

The accompanying `SPEC.json` and `.dck` files use the app's unchanged Ramp and
Dimir Control main decks. The sideboards are constructed diagnostic lists, not
tournament-provenance lists. Deck lists are explicitly public for this check.

After building the pinned Forge checkout, set `CP` to its complete native test
classpath, including compiled classes and dependency jars. From that checkout's
`forge-gui-desktop` directory, with `INPUT` an isolated writable copy of
`forge/native-match`, compile and run:

```sh
javac --release 17 -cp "$CP" -d "$INPUT/classes" "$INPUT/NativeMatchProbe.java"
timeout -k 20s 600 java -Xmx2g -Djava.awt.headless=true \
  -cp "$INPUT/classes:$CP" forge.evaluation.NativeMatchProbe "$INPUT"
```

Our observed run additionally used the existing network-isolated sandbox and
separate home/temp directories. Keep `game-logs.private.jsonl` protected; do not
commit generated game traces. Require exit zero **and** the
`native_match_complete` JSON footer. The runner never assigns an outcome to
convert a timeout or error into a draw. This is not yet an app backend or a
browser-facing protocol.
