# Native Engine Integration Status

The Forge Team/Card-Forge implementation is a reuse path for card rules and
baseline AI, not merely an Oracle-text database. The intended shortcut is to
connect our application to that existing implementation instead of rebuilding
each card interaction. It is not a completed engine migration or a claim that
Forge's AI is an expert opponent. The live application still uses our Python
backend. Upstream authorship and GPL notices remain in the
[evaluation sources](../../tools/engine_evaluation/README.md) and
[third-party notices](../../THIRD-PARTY-NOTICES.md).

Later checkpoints are documented separately: the [opt-in app session](forge-app-session.md),
[native AI knowledge corrections](native-ai-knowledge-boundary.md), and
[broader deck coverage/retained stack-source fix](native-deck-quality-2026-11-06.md).
The stage-specific findings below retain their original sources and results;
they are not the latest app or AI qualification by implication.

## Verified Prototype

The isolated prototype uses Forge revision
`61e9442c433711a82258daca3236f936a1d6f70e`, with the owned adapter and native input
patches. A human-controller test client supplies actual offered choices while
the opposing player uses the native AI. That client is not an expert policy.

- A native game completed naturally with 236 starts and returns over 15 turns.
  A separate fresh run consumed the retained reference and verified the whole
  choice, native-state and RNG evidence streams. Completion order differs only
  at the two explicitly checked, causally independent producer pairs; this is
  not a claim of globally identical callback completion order.
- On the coupled build, a genuine two-source mana payment rejected a stale
  queued callback without a GUI callback or native-state mutation. A current
  replacement selection remained usable and the original payment completed.
  This is a controlled native payment check, not another natural game.
- The earlier 17-source checkpoint reproduces all 28 qualified payload classes
  byte-for-byte. The current build adds native boundary/checkpoint units and lists 22
  explicit Java inputs, without implicitly compiling another upstream copy.
  Source reproducibility is not application integration. The later checkpoint-prefix
  build below lists 23 sources; the earlier 22-source results remain historical.

An earlier run labelled replay did not actually load a reference; a later
explicitly interrupted run was incomplete. Those results remain unqualified.
Only the separate genuine reference-consuming run supports the replay claim.
Generated hands, native/RNG traces and receipts remain protected test evidence,
not public fixtures.

## Current Complex-Deck Finding

The first Control/Ramp game reached a real Memory Deluge multi-card choice.
Forge required two of four cards. The adapter exposed one-click responses but
omitted the native selection minimum, maximum and already-chosen objects.
The generic test picker repeatedly selected and deselected the first card,
eventually hitting the existing 1,000-input limit. This was a failed game,
not a natural outcome, and the reverse game was not run under that cohort.

The correction completed that actual native two-of-four choice: two distinct
clicks succeeded and both cards subsequently appeared in the actor's hand.
The follow-up game still did not finish: at 216 starts and returns, an unsupported
stack-target type left the adapter waiting until its wall limit. Neither
incomplete game is a scored result.

## Current Choice Checkpoint

The bridge now projects distinct current stack IDs with actor-filtered source
views and dispatches through native `selectStackItem`, not a source-card alias.
Foreign, removed and same-ID alias views reject. Native stack-only clicks publish
their completed interaction through the existing generation fence; other ability
paths are unchanged. Publication/snapshot errors fail promptly instead of hanging.

Multi-card metadata uses the current native input's actual `getSelected()`.
GUI highlights can retain earlier spell targets during payment and must not be
mistaken for selections. The picker uses offered identities and honors genuinely
enabled native OK, even where native rules permit an early finish. One-click
responses, native validation and one-use tokens remain; no card-name policy,
invented choice or enlarged game budget is used.

- **223 passed, zero failed/skipped, 41.60 seconds:** the unchanged original
  nine whole classes, ten stack-boundary units and four completion cases in
  eleven whole classes. All 209 inherited invocation
  identities/parameters and all 28 loaded before/end payload pins are checked.
- Separate public test-client checks pass **20 selection** and **nine stack**
  labelled synthetic protocol cases, plus the original batched-frame/EOF check.
  These are not natural games or a summed full suite.
- Stack-boundary units use trusted object/queue poses and negative inputs, not
  natural games. They cover distinct same-source stack entries, real dispatch,
  redaction, stale references, highlight separation and fail-fast behavior.

The first inherited run had 207 passes/two failures: an early no-action context
dereference and a missing launcher module-opening flag. Neither inherited test
was edited. The next 219-case run had 217 passes/two failures: the missing partial
stack completion receipt and a new fixture lacking native retained marks. The
stack correction changes that callback body and only the new fixture setup,
retaining every assertion. Earlier failures remain archived, not relabelled green.

## Completion Reporting

Two later complex games reached actual native outcomes: Ramp won at turn 16
and Control won at turn 18. The old worker nevertheless exited with
`coverage_missing`: its diagnostic reverse-order scenario had not occurred.
Those old executions remain failed bridge qualifications, not successful exits.

The correction removes only that test-coverage veto from `finishTerminal`.
`completed` still requires a genuine native game-over/outcome, callbacks must
balance, and the causal verifier and every replay-reference stream must finish.
The completion frame reports observed coverage separately without forcing a
reorder, paid spell or winner. No native AI policy, card rule or game limit changed.

The four new cases first produced two failures on real Default-AI paid Bolt wins
and two passing unfinished-game controls in both seats. The same four cases now
pass within the full 223-case cohort above. Only the Worker class changes among
the 28 loaded payload classes; all other payload bytes and inherited test inputs
are unchanged. The natural-game cohort below is separate evidence, not implied
by these controlled positions. Mixed card/stack dialogs and the full callback
surface remain unqualified.

## Complex-Deck Qualification

Three fresh, bounded processes ran on completion source `2a814bdd`, before the
checkpoint additions below, with the
same 60-card Control/Ramp mains, empty sideboards, seed and Default native AI.
The human-controller client uses offered native choices; it is not an expert
opponent or training label. No game budget, card rule or AI policy was changed.

| Process | Human Seat/Deck | Actual Native Outcome | Starts/Returns | Wall Time |
| --- | --- | --- | --- | --- |
| A | 0 / Dimir Control | Ramp won, turn 16 | 236 / 236 | 42.81 s |
| B | 1 / Ramp | Dimir Control won, turn 18 | 233 / 233 | 43.07 s |
| Fresh Replay Of A | 0 / Dimir Control | Same outcome, turn 16 | 236 / 236 | 44.82 s |

All three exited zero with genuine `game_complete` frames and no outstanding
callbacks. Starts/returns count protocol invocations, not casts or paid actions.
Both original games include actual human paid-spell evidence. Neither needed a
reverse-order dialog; `coverage.reverse_order` correctly remains false.

The replay actually loaded A's retained reference. Parsed starts, completions
including arrival order, native/RNG states, paid-pending, final and observation
streams match. Its completion contract records reference comparison, no displaced
pairs and strict global completion order. This is this replay's result, not a
universal callback-order guarantee. All registered 120 card IDs/owners, loaded
class origins and before/end input pins were checked; all game processes ended.
The genuine two-of-four selection and distinct stack-instance selection also
completed through native callbacks in A and its replay.

Protected hand/RNG/game evidence is archived privately, not published as fixtures.
These are completed native integration games, not a strategy-strength benchmark,
durable save/resume check, browser test or live engine migration.

## Pending-Choice Checkpoint Component

The worker can now capture a current unresolved question without consuming its
tokens or advancing play. Snapshot data contains private state and remains in
host-owned files; only the request ID and digest are acknowledged on the wire.
The host store checks snapshot bytes, schema and a trusted build ID, restores
only the original spec/deck inputs, and requires full captured-frontier equality
before further play. This is replay reconstruction, not complete Java heap
serialization, and it is not yet an application save/resume endpoint.

- Final **243 native cases passed**, zero failures/skips, in 42.71 seconds across
  thirteen whole classes. All original 209 identities/parameters and all inherited
  243 test bytes are retained on the final wire-label build. All 28 actual loaded
  payload resources are pinned before/end. The build lists 22 explicit sources.
- **92 Python client/store tests passed**: the unchanged 29 client checks and 63
  new labelled synthetic persistence/schema checks, not 92 game episodes. Four
  separate labelled Java protocol assertions cover busy-versus-legacy rejection.
- The first 17 native checks failed on the absent API, then passed in a 240-case
  cohort. Review found producing-dispatch and input-replacement races plus a fatal
  save-I/O path. Three deterministic native/API tests reproduced all three; they
  now pass. Original 17-test source and all previous native test inputs are unchanged.
- Capture now waits for nonblocking dispatch returns and retains the actual queue
  monitor through snapshot/publication. Recoverable I/O reports pre/postcommit
  status without invalidating the human question. A distinct busy reason remains
  available to the host; ordinary answer rejection is unchanged.

Those component checks do not establish that every native choice can be resumed.
The actual cold pending-choice experiment below is separate evidence. Existing full
reference/causal verification, AI policy, game budgets, costs and card rules are
unchanged. All earlier failing stages are preserved rather than relabelled green.

### Earlier Cold Reconstruction: Held

The original native process genuinely reached a Memory Deluge two-of-four choice
after its first selected card. It saved with 186 balanced starts/returns, then
closed stdin and exited 2 with an abort, not a game outcome. The real host store
saved/loaded the protected bytes and restored spec/deck inputs for a fresh JVM.

The new process replayed all 186 accepted invocations with fresh native tokens.
Its pending offer, actor view, existing native-state projection, spec, decks,
starts, native/RNG journal and paid-pending data match the saved checkpoint.
Whole completion rows also match by start ID, but their arrival order does not.
The strict frontier comparison rejected this difference before any new answer.
The resumed process was stopped without a completed game; the declared third
uninterrupted run was not started. These are **two processes and a failed resume
qualification**, not completed games or an accepted save/resume feature.

Matching current board state or sorting IDs alone is insufficient. The correction
below retains this failed experiment separately; it does not turn either earlier
process into a completed resumed game.

### Causal Prefix Verification

The host remains exact-by-default. An operator may configure the pinned local
Java verifier for an arrival-order-only difference at a balanced checkpoint.
Every other frontier field, journal stream and typed completion row must still
match. The Java prefix mode reuses the existing producer/parent inversion rule,
retains actual arrival order and consumes every stream. It requires zero final
rows and cannot certify a complete game. Full-game verification remains separate.

- Current native regression: **243 passed**, zero failures/skips, in 46.88 seconds
  across the same thirteen whole classes. All inherited test bytes and original
  209 invocation identities/parameters remain unchanged. Actual loaded origins
  and all 28 payload resources are checked before/end.
- **150 Python tests passed**: the unchanged 92 client/store checks plus 58 new
  labelled synthetic verifier-transport checks. These are not game episodes.
  Invalid proof fields, state/row changes and non-Java command wrappers reject.
- Separate pure Java checks passed: **31 prefix**, **60 unchanged full causal
  protocol** and **four unchanged checkpoint reply** assertions. The prefix/full
  distinction also rejects conversion by mutating a reference's final vector.
- The actual new verifier accepts the archived real `(53,51)` inversion. A matched
  pair of altered producer records rejects through the Java rule, while an RNG
  change rejects in the host before launching Java. No native Game was initialized
  by these verifier-only processes. This is executed policy evidence on archived
  data, not a new game or successful save/resume run.

The verifier command comes only from trusted host configuration, never checkpoint
or browser data. It launches Java directly with a timeout and minimal environment;
the returned proof binds the exact input bytes and records every displaced pair.
All private checkpoints, hands and RNG receipts remain protected evidence.
Fresh reconstructed continuation and uninterrupted reference qualification are
separate from these component results.

### Actual Cold Reconstruction And Continuation

Three fresh, serial processes used the fixed 23-source build, unchanged
60-card Control/Ramp mains, empty sideboards, human seat 0, the same seed and
Default native AI with Monte Carlo off. The original game genuinely reached
Memory Deluge's two-of-four choice with one card already selected.

| Process | Observed Result | Starts/Returns | Wall Time |
| --- | --- | --- | --- |
| Save And Disconnect | Saved pending choice; EOF abort, exit 2 | 186 / 186 | 43.19 s |
| Fresh Cold Reconstruction | Continued to Ramp's native win, turn 16, exit 0 | 236 / 236 | 50.69 s |
| Uninterrupted Reference | Same native outcome, turn 16, exit 0 | 236 / 236 | 51.27 s |

The real host store saved/loaded the checkpoint and restored spec/deck inputs
under the current build identity. The second process replayed the saved semantic
choices using fresh native tokens, with no `REPLAY.path`. Before any new answer,
all nine captured fields and every journal row matched exactly. This run did not
need the optional causal-order exception; the separately executed archived
inversion above keeps that path nonvacuously tested without forcing a reorder.

The remaining selection was a different offered card. Both selected registered
cards later appeared in the actor's native hand, and the resumed game reached a
genuine game-over. Only then did the uninterrupted reference run. All 236 starts,
236 completion rows including arrival order, 407 native/RNG records, paid-pending
data, final outcome, observations and registered native identity matched. A
separate pure runner fed the actual wire's start/completion order through the
existing full constructor, `accept` and `finish`; it consumed one real final row
and reported no displaced pairs. It did not substitute prefix verification for
full-game verification or construct a native Game.

The source/build/resource pins remained unchanged; all three game processes and
the pure verifier ended. Earlier failed checkpoints remain separate and failed.
This verifies one real pending-choice cold continuation, not arbitrary internal
heap equivalence, every native callback, either-seat coverage, durable BO3,
browser reconnect, strong strategy or live application adoption. The next app
slice must own native sessions/choices separately from Python actions and saves.

## Bounded Native AI Checks

Six controlled Default-AI burn checks passed in both seats: one Bolt at three
opposing life, two genuinely chosen/paid Bolts taking six life to three then zero,
and an unpayable case without a cast or fabricated win. The harness schedules
priority after each resolution; this is not a full natural priority loop.

Twelve controlled draw/counter pairs observed matching decisions and ending RNG
under the tested concealed variants, including paid draw/counter controls.
Neither experiment proves broad fairness or strength. Their strict zero-denial
environment checks failed separately: each recorded two blocked hostname/connect
checks. Burn traced its port-minus-one checks to TestNG reporting after the tests;
the earlier draw/counter run lacked attribution data. Functional observations are
not a claim of clean zero-attempted-IO qualification.

## Opt-In Application Slice

The separate process owner, strict HTTP routes and native React table now have
[bounded built-app qualification](forge-app-session.md): one real Control/Ramp
game completed naturally through 433 rendered-control answers, same-session
reload, negative protocol checks and a genuine rendered result. The first
runtime failures and their corrections remain separate evidence. No native
rule or AI policy changed. This does not enable the runtime by default, switch
the live service or establish broad AI strength.

## Still Required

The [native AI knowledge audit](native-ai-knowledge-boundary.md) now documents a
corrected private-card identity leak, its twenty controlled checks, and one
completed built-UI game on a distinct identity-only candidate. A second hidden
mana affordability leak is reproduced on that historical candidate and corrected
in a separate three-source increment with thirty native checks and an independent
byte-identical rebuild. Broader native-AI fairness remains open; the live backend
has not changed.

- Broaden completed native games beyond the qualified Control/Ramp pair and
  cover the remaining native choice surface.
- Review ordinary native-AI hidden-information boundaries and strategic play;
  a protected human view alone does not establish that native AI never peeks.
- Broaden the first app integration across both seats, remaining choices,
  card art, beginner interaction polish and practical runtime packaging.
- Qualify application saves across other pending choices, both seats and BO3;
  the one observed cold reconstruction is not full persistence coverage.
- Establish broader strategy quality, practical performance and release gates.

This prototype removes implementation work we would otherwise duplicate. It
does not yet close those requirements or the application's RC checklist.
