# Native Final Actor View

## Correction

A real rendered human/native game reported the correct loss at zero life while
its board still displayed the preceding three-life priority snapshot. The native
final journal confirmed zero; the outcome text was not the source of the defect.

`NativeHumanWorker.finishTerminal` now publishes a final actor-filtered `view`
before `game_complete`. It uses `ActorBoundary.snapshot(game.getView())`, not raw
native journals or life values inferred from English outcome strings. Existing
completion fences, outcome checks, privacy projection and event schemas remain.

The extended completion fixture supplies the actor/boundary context already
present in the real host. It retains every original outcome/unfinished-game
assertion and adds final-view ordering and both-seat life checks. The canonical
native Bolt is actually paid and resolved; no winner is injected.

## Observed Qualification

- The isolated final-view regression went from two passes/two failures on the
  original producer to four passes on the corrected producer. Historical raw
  traces remain unchanged; the old captured mismatch is still historical RED.
- Eight whole native lifecycle/privacy/input/stack/checkpoint/journal/completion
  classes passed 101 checks in 26.37 seconds. These include controlled poses and
  negative protocol diagnostics, not 101 natural games or strategic wins.
- Seven whole backend modules passed 258 checks and six frontend modules passed
  51 checks. These use synthetic child/transport and UI contracts, not native
  games. All 65 declared production/test source pins stayed unchanged; the
  Python child guard starts at `sitecustomize`, not before site initialization.
- The existing 42 profile tests pass. A fresh schema11 prefix contains 14 sources
  and 23 classes. All AI sources/classes are byte-identical to C14; only the
  worker source changes. Its outer class and two generated anonymous classes
  have different hashes; every AI class remains unchanged.
- A fresh rendered production `ForgeGame` plus actual Forge router/manager game
  completed naturally in eight native turns: 103 DOM submissions, 94 Jev human
  decisions, four native zero-card acknowledgements, Save/page-reload/Resume and
  an acknowledged Close. Its final DOM/native lives both equal -1 and 18.
  The backend stayed running across the page reload. Native guard canaries and
  observed override origins passed in both worker lifetimes.

The public regression is reproducible with the native completion test; raw game
and model traces remain private. Forge rules, card programs and the underlying
AI are the **Forge Team/Card-Forge contributors' work**; existing GPL notices and
upstream attribution are retained.

## Identity And Limits

Corrected content:
`16517907e0dc07f6f136d4a6b7199bb0e62a8c629a549ef25797644bfe7bb1e7`.
Fresh native profile:
`efdf57c55ce935f667112a32b7818fe56565cdc8eb7781aa16aaac04d93cb395`.
Worker source:
`28e6e30bcb4d0dd5b5bd37b6525a0e04561f6592bde3bdbbc0a91f5808fab782`.

This is not a live/default runtime switch, full-App acceptance, human best-of-
three/sideboarding, backend-process restart proof, expert-opponent result,
paid-human-spell certificate, trained-model result or completed AI release.
The native matchups and broader strategy/fairness review are separate evidence.
