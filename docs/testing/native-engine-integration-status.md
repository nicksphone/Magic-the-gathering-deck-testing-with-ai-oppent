# Native Engine Integration Status

The Forge Team/Card-Forge implementation is a reuse path for card rules and
baseline AI, not merely an Oracle-text database. The intended shortcut is to
connect our application to that existing implementation instead of rebuilding
each card interaction. It is not a completed engine migration or a claim that
Forge's AI is an expert opponent. The live application still uses our Python
backend. Upstream authorship and GPL notices remain in the
[evaluation sources](../../tools/engine_evaluation/README.md) and
[third-party notices](../../THIRD-PARTY-NOTICES.md).

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
  byte-for-byte. The current build adds a native boundary unit and lists 18
  explicit Java inputs, without implicitly compiling another upstream copy.
  Source reproducibility is not application integration.

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

- **219 passed, zero failed/skipped, 41.53 seconds:** the unchanged original
  nine whole classes and ten new native units. All 209 inherited invocation
  identities/parameters and all 28 loaded before/end payload pins are checked.
- Separate public test-client checks pass **20 selection** and **nine stack**
  labelled synthetic protocol cases, plus the original batched-frame/EOF check.
  These are not natural games or a summed full suite.
- New native units use trusted object/queue poses and negative inputs, not paid
  game wins. They cover distinct same-source stack entries, real dispatch,
  redaction, stale references, highlight separation and fail-fast behavior.

The first inherited run had 207 passes/two failures: an early no-action context
dereference and a missing launcher module-opening flag. Neither inherited test
was edited. The next 219-case run had 217 passes/two failures: the missing partial
stack completion receipt and a new fixture lacking native retained marks. The
final correction changes that callback body and only the new fixture setup,
retaining every assertion. Earlier failures remain archived, not relabelled green.
Corrected complex games, mixed card/stack dialogs and full callback coverage
remain separate acceptance work.

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

## Still Required

- Complete complex-deck human/native-AI games with the corrected choice bridge.
- Review ordinary native-AI hidden-information boundaries and strategic play;
  a protected human view alone does not establish that native AI never peeks.
- Integrate game state, choices, payments and rendering with the application.
- Qualify durable saves and resume through pending choices, not just replay.
- Establish broader strategy quality, practical performance and release gates.

This prototype removes implementation work we would otherwise duplicate. It
does not yet close those requirements or the application's RC checklist.
