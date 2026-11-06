# Native Human Process Bridge

The original GPL-3.0-or-later adapter in
[`tools/engine_evaluation/forge/stdio`](../../tools/engine_evaluation/forge/stdio)
calls the Forge Team/Card-Forge native match, human controller and GUI protocol,
revision `61e9442c433711a82258daca3236f936a1d6f70e`. Those engines, card programs
and controllers are upstream work, not ours. Retain the source credits, original
copyright notices and [Forge GPL license](../../tools/engine_evaluation/forge/LICENSE).

## Contract

One local, host-owned JVM runs one human-versus-AI game. The host chooses the
actor and decks; the client cannot select a seat. Native diagnostics go to
protected stderr, not the JSON output stream. This is a local process prototype,
not an authenticated HTTP service or a live engine replacement.

- `choice` frames contain an actor-scoped snapshot, detached question/context,
  and opaque one-use choice tokens. Native callbacks retain their real objects
  privately. Reply with exactly `request_id` and an ordered `tokens` array.
- `view` frames project native public updates and authorized reveals through
  the same actor boundary. Raw native deltas/events/logs are never wire objects.
- Invalid, duplicate, oversized, actor-selecting and stale replies are rejected.
  A native input replaced before EDT dispatch is not acted upon.
- Total-order dialogs require every offered token, in the client's chosen order.
  The prototype does not silently remember that order as a future preference.
- Reveal-only `(-1,-1)` dialogs require acknowledgment without card selection.
  A source with zero eligible abilities returns the native no-action result.
- EOF emits an abort, not a manufactured game result. A late completion callback
  cannot overwrite that abort. Native terminal results come from actual outcomes.
- `game_complete` retains the native outcomes, turn and win condition. Its nested
  `coverage` reports observed reverse-order and paid-human scenarios as diagnostics,
  not prerequisites for a real game result. Balanced callbacks, causal completion
  and complete reference consumption remain required.

The current worker supports the exercised scalar/list dialogs and native
card/player/stack-instance clicks. Selection metadata describes the actual current
native selection, not GUI highlights. Unsupported callbacks fail rather than
choosing defaults. Combat-damage allocations, mixed card/stack targeting,
partial/sideboard ordering, arbitrary text input, all delayed-reveal contexts
and the complete native dialog surface remain unqualified. Browser rendering
and reconnect/auth are not supplied. See the
[current 223-case component and game limits](native-engine-integration-status.md#current-choice-checkpoint).

## Earlier Checkpoint Qualification

This section records the earlier published worker, before the causal replay and
native input patch checkpoint. It is not a rerun of that cohort on every later
worker revision. See [current integration evidence and limits](native-engine-integration-status.md).

Nine whole native classes passed **209 tests, zero failures/skips** in 16.686
seconds: the earlier 183-case regression set plus 26 worker/transport checks.
These include deliberately labeled internal protocol tests, not 209 full games.
The reply parser first ran 2 passing / 13 failing cases before strict parsing.
Reveal acknowledgment, empty-ability handling, prompt text, dispatch failure,
mandatory order and late-completion handling each retained their failing checks
before correction. Independent review found the missing question text and
uncaught EDT dispatch; both were corrected and covered.

On the final published worker/client bytes, separate offline JVMs ran the
unchanged 60-card app Burn and White Weenie mains, empty sideboards and public
deck lists. Human seats were reversed. The scripted human-controller client
uses native clicks, abilities, targets and payment controls; it does not inject
cards, game events, paid spells or winners.

- Human Burn / native AI White Weenie completed naturally in 12 turns.
- Native AI Burn / human White Weenie completed naturally in 13 turns.
- Both sides put real spells on the native stack. Captured examples include the
  human's Lightning Bolt and the AI's Monastery Swiftspear and Brutal Cathar.
- Two additional fresh processes closed stdin at the first question: each
  exited 2 with one explicit abort and no game-complete result. These are not
  scored games, draws or wins.
- All four cases checked 1,265 actor-view frames, including native public
  updates during the AI's turn. Ordinary opposing hands stayed hidden; this
  matchup's legitimate Goblin Guide top-card reveals remained visible.

The native AI was configured with Default and Flat-MC enabled, MAX/LITE disabled;
these process cases did not capture rollout statistics. The earlier matched
search comparison provides separate actual rollout evidence. Neither this
scripted client nor these outcomes establishes playing strength or full-policy
fairness. The current Python app and live saved matches were not changed.

Earlier integration attempts are preserved: reveal-sentinel failure at turn 3,
empty-ability failure after repeated canceled payment attempts at turn 8, and
unsupported simultaneous-trigger ordering in the first reversed-seat run. The
test driver was corrected to avoid repeating unaffordable attempts. A later
pure driver check exposed a batched-EOF loss; the corrected published client
passed that check and all four final fresh-process cases. Those failed stages
are not relabeled as successful games.

## Reproduce

Use the previously built pinned Forge classpath. From the application checkout,
compile the explicit 19-source list; this includes all current helpers and the
four modified native input classes, rather than relying on an older cached
adapter. The output directory must not exist and must be outside this repository:

```sh
FORGE_CP="$CP" JAVAC=/path/to/jdk/bin/javac \
  bash tools/engine_evaluation/forge/stdio/build.sh "$OWNED/classes"
```

Run from the pinned Forge checkout's `forge-gui-desktop` working directory.
Keep the owned classes first on the runtime classpath. Copy the existing
practical-search `SPEC.json` and two deck files into a fresh
owned input directory. Add `human_seat` as integer 0 or 1. Retain the explicit
deck inventories, `open_decklists`, `seed` and `flat_monte_carlo` settings.

```sh
java -Xmx2g -XX:ActiveProcessorCount=2 -Djava.awt.headless=true \
  -Duser.home="$INPUT/home" -Djava.io.tmpdir="$INPUT/tmp" -Dsentry.dsn= \
  -cp "$OWNED/classes:$CP" forge.evaluation.NativeHumanWorker "$INPUT"
```

Create the home/tmp directories first. Keep stderr and all generated game traces
private. Our execution used the existing offline filesystem/network sandbox.
Operator-owned `COMMAND.json` can hold the exact bounded Java/sandbox argv for
`exercise_worker.py COMMAND.json EVIDENCE_DIRECTORY [disconnect]`. Never expose
its executable/path configuration to a browser client. The exercise client is
an intentionally simple integration driver, **not an expert AI or training label**.
Its privacy assertions are specific to the declared Burn/White Weenie matchup,
not universal rules forbidding legitimate larger reveals.

The supplied controlled-unit launcher additionally expects its original native
test layout; compiling it does not make that layout or its scene files part of
this distribution. The compiler flags target Java 17 and disable implicit source
discovery. Byte-identical reproduction additionally requires the qualified JDK
21.0.13+9 and the same pinned dependency classpath, not arbitrary newer builds.

## Save/Resume Boundary

This bridge does not claim durable engine restart. Native `GameState` is a
position format; source inspection found no drop-in serialization of suspended
human choices, RNG and BO3 history. In-memory undo/copies are not durable resume.
An actual fresh-process compatibility audit is separate. Do not replace saved
app matches or claim full adoption from successful process games.
