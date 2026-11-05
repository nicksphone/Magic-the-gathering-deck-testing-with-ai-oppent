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
mkdir -p "$INPUT/classes" "$INPUT/home" "$INPUT/tmp"
javac --release 17 -cp "$CP" -d "$INPUT/classes" "$INPUT/NativeMatchProbe.java"
timeout -k 20s 600 java -Xmx2g -Djava.awt.headless=true \
  -Duser.home="$INPUT/home" -Djava.io.tmpdir="$INPUT/tmp" -Dsentry.dsn= \
  -cp "$INPUT/classes:$CP" forge.evaluation.NativeMatchProbe "$INPUT"
```

Our observed run additionally used the existing network-isolated sandbox and
separate home/temp directories. Keep `game-logs.private.jsonl` protected; do not
commit generated game traces. Require exit zero **and** the
`native_match_complete` JSON footer. The runner never assigns an outcome to
convert a timeout or error into a draw. This is not yet an app backend or a
browser-facing protocol.

## Actor Boundary Prototype

[`forge/actor-boundary`](forge/actor-boundary) contains our original
GPL-3.0-or-later actor projection, one-use choice broker and native tests. The
native engine, human-controller protocol and test helpers are upstream work by
the Forge Team/Card-Forge contributors. Each source header credits them; retain
[Forge's original license](forge/LICENSE) and upstream notices.

From the pinned checkout's `forge-gui-desktop` directory, using the native
classpath `CP` described above and an isolated copy at `BOUNDARY`:

```sh
mkdir -p "$BOUNDARY/classes" "$BOUNDARY/home" "$BOUNDARY/tmp"
javac --release 17 -cp "$CP" -d "$BOUNDARY/classes" "$BOUNDARY/"*.java
timeout -k 15s 360 java -Xmx2g -Djava.awt.headless=true \
  -Duser.home="$BOUNDARY/home" -Djava.io.tmpdir="$BOUNDARY/tmp" -Dsentry.dsn= \
  --add-opens java.base/java.lang=ALL-UNNAMED \
  -cp "$BOUNDARY/classes:$CP" org.testng.TestNG \
  -testclass forge.evaluation.ActorBoundaryTest,forge.evaluation.NativeHumanBoundaryTest,forge.net.embedded.ProtocolGuiGameInProcessTest,forge.ai.simulation.GameSimulationTest,forge.gamesimulationtests.ReplacementHandlerTest \
  -d "$BOUNDARY/results"
```

Our actual run used the existing network-isolated sandbox and separate home and
temp directories. Keep generated native logs/results protected. These tests do
not expose raw native objects to a browser, certify all native dialogs or switch
the running application. Read [the evidence and remaining integration work](../../docs/testing/forge-native-boundary.md).

## Public-Information Naming

[`forge/public-naming`](forge/public-naming) contains an original GPL-3.0-or-later
controller subclass and probes, credited to the Forge Team/Card-Forge native
engine/AI work. Retain [the upstream license](forge/LICENSE) and its notices.
No original upstream card program was edited. This is a scoped evaluation, not
an app migration or globally fair/expert AI claim.

Copy `PublicNameController.java` and `NativeNameInformationTest.java` into an
owned `NAMING` directory, along with `ActorBoundary.java` from the earlier
prototype. With the same pinned native classpath `CP` and working directory:

```sh
mkdir -p "$NAMING/classes" "$NAMING/home" "$NAMING/tmp"
javac --release 17 -cp "$CP" -d "$NAMING/classes" "$NAMING/"*.java
timeout -k 15s 360 java -Xmx2g -Djava.awt.headless=true \
  -Duser.home="$NAMING/home" -Djava.io.tmpdir="$NAMING/tmp" -Dsentry.dsn= \
  -cp "$NAMING/classes:$CP" org.testng.TestNG \
  -testclass forge.evaluation.NativeNameInformationTest -d "$NAMING/results"
```

The final seven-class regression cohort additionally included both earlier
boundary classes and upstream `ProtocolGuiGameInProcessTest`,
`GameSimulationTest`, `ReplacementHandlerTest`, `FlatMonteCarloNamedDiscardTest`.
It required `--add-opens java.base/java.lang=ALL-UNNAMED` for the upstream protocol
test. All 181 cases passed; this is not the entire native test suite.

`NativeNameMatchProbe.java` also requires the actor-boundary class. Its
`match-input` directory is the exact corrected seed-zero input. A separate copy
with `use_public_name_controller=false` selects the baseline; use seed
`873109261490271` for the second development pair. Run its class like the earlier
BO3 caller, with a fresh owned home/tmp per series, heap limit and 300-second
external bound. Require process exit zero and the actual terminal footer.
Keep both generated `.private.jsonl` files protected, not in Git.

See [full results, mixed outcomes and remaining work](../../docs/testing/forge-public-naming.md).

## Practical Native Search

The same credited `NativeNameMatchProbe` accepts an optional boolean
`flat_monte_carlo` in `SPEC.json` (omitted means off). It configures each real
game before play, leaves MAX/LITE off and records the existing upstream
`FlatMonteCarloStats` after each game. `NativeSearchConfigurationTest` checks
both settings. No native search implementation was copied or rewritten here.

[`forge/practical-search/match-input`](forge/practical-search/match-input) is the
exact first search-on input using unchanged app Burn/White Weenie main decks
and empty sideboards. For matched copies set the boolean false/true and use seeds
`2026110501` and `2026110502`. Use the native classpath, isolated homes/tmp and
300-second bounds described above, adding `-Dforge.flatmc.debug=true` and
`-Dflatmc.trace=true`. Require every process exit and real terminal footer;
an aggregate shell exit alone is not match acceptance. Keep generated traces
private. Read [actual results and limitations](../../docs/testing/forge-practical-search.md).

## Native Human Worker

[`forge/stdio`](forge/stdio) is an original, credited GPL-3.0-or-later process
adapter around the unchanged Forge human controller. It reuses the actor-scoped
projection and one-use choice broker, with JSON-lines stdin/stdout rather than
raw Java views. Diagnostics and game traces remain private. Read the
[contract, runnable commands and open adoption requirements](../../docs/testing/forge-native-human-worker.md).

## Native Save Compatibility

[`forge/save`](forge/save) contains an original credited GPL-3.0-or-later
fresh-JVM diagnostic, not a replacement persistence implementation. Real native
payment/resolution and strict observed-fact comparisons are retained, including
failed pending-stack recovery. Separate, explicitly narrower placement controls
do not waive full save/resume requirements. Keep native state text and facts
private. Read [the executed result and observer limitations](../../docs/testing/forge-native-save-compatibility.md).
