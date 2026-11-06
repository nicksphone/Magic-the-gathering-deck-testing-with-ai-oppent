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
- The source-only build compiles all 17 distributed inputs in one explicit
  Java batch. All 28 qualified payload classes reproduce byte-for-byte with
  the pinned compiler and cached dependency classpath. This establishes source
  reproducibility, not application integration.

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

The observed gap is in the bridge: the necessary native `Selection` API already
exists. The correction is to expose actor-visible selection metadata at the
current-input boundary and consume it structurally, while preserving one-click
responses, native validation, input generations and one-use tokens. No card-name
exception, invented selection or enlarged game budget is an adequate fix.

## Still Required

- Complete complex-deck human/native-AI games with the corrected choice bridge.
- Review ordinary native-AI hidden-information boundaries and strategic play;
  a protected human view alone does not establish that native AI never peeks.
- Integrate game state, choices, payments and rendering with the application.
- Qualify durable saves and resume through pending choices, not just replay.
- Establish broader strategy quality, practical performance and release gates.

This prototype removes implementation work we would otherwise duplicate. It
does not yet close those requirements or the application's RC checklist.
