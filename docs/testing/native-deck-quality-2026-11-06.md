# Native Deck Coverage And Retained Stack Sources

These are bounded integration checks, not an AI-strength or release certificate.
They reuse Card-Forge's native rules, card programs and Default AI. Upstream
Forge Team/Card-Forge contributors retain credit and GPL notices; see
`tools/engine_evaluation/forge/LICENSE`.

## Natural Best-Of-Three Coverage

The unchanged `NativeNameMatchProbe` ran these five pairings in both seat orders:

- Burn / White Weenie
- Dimir Control / Tempo
- Midrange / Ramp
- Burn / Dimir Control
- Tribal / Midrange

All main decks were the unchanged application built-ins, with empty sideboards.
Deck import and combined inventory were checked. No sideboarding-quality claim
follows from empty sideboards. Games used native outcomes, ordinary Default AI,
the qualified public-name controller, disclosed deck lists, Monte Carlo off,
filtered hands off and cheat shuffle off. Each series had a 300-second bound.
Two JVMs ran concurrently; no application database or live service was used.

The initial ten-series run returned **nine completed series and one observer
failure**. There were 23 emitted game-completion receipts, including one from
the failed series. Its second game finished naturally, but observer errors
prevented its completion receipt and stopped the series before game three.
The initial run is retained as exit 1, not a green ten-series run.

## Identified Adapter Failure

The failed Midrange / Ramp run encountered a real retained source for Reflection
of Kiki-Jiki. An observer-only diagnostic reproduced four failures: the exact
native stack source was face-up battlefield last-known information (LKI), with
a null current zone. Our ordinary card projection correctly rejects unclassified
cards, but incorrectly applied that rule to this classified retained stack source.

The correction is stack-specific. Both stack snapshots and native stack choices
require the exact current native entry/view and its exact source/view association.
Only a native LKI object with no current zone, saved origin exactly Battlefield,
and both native/view faces face-up may use the retained scalar projection.
No source is recovered by card ID or live-card lookup. No zone is manufactured.
Source owner/controller are preserved, not replaced by the ability activator.
Answer dispatch rechecks the native association. Ordinary unclassified cards,
private/missing origins, face-down LKI, foreign/removed entries and aliases reject.

The first new eight native-object checks produced **4 PASS / 4 FAIL** before the
fix: two expected public-LKI projections rejected, and two mismatched source
views were incorrectly admitted. Final whole classes `ActorBoundaryTest`,
`NativeStackBoundaryTest` and `NativeLkiStackBoundaryTest` produced **48 PASS**,
zero failures/skips, in 11.907 seconds. These are labelled native-object unit
poses, not natural games. Earlier 44-check green and diagnostic runs remain
separate evidence.

With the correction and unchanged AI classes, a fresh affected series completed
**three natural games and 1,650 actor observations**, exit 0, in 25.570 seconds.
The first two native game logs match the original run entry-for-entry except
their two explicit elapsed-duration messages. The third game completed naturally.
This was one corrected series, not a rerun of the entire ten-series cohort.

## Limits And Evidence

The final AI source/class candidate for these series was `ff89fd32`; its compiled
runtime/profile and the live application were not changed by this boundary fix.
A separate follow-up has reproduced an additional-cost held-piece dependency on
concealed hand contents. That remains a separate correction/qualification task.
A possible Burn missed-lethal decision is under investigation, not yet a proven
tactical failure. No broad fairness, expert play, full-card support, new-profile
UI game or save/resume qualification is claimed here.

Generated hands, RNG information and game/actor traces are private evidence and
are not repository fixtures. Full diagnostics, exact launch/class origins,
native logs, original failures and XML results are preserved under the project's
NFS artifact storage. The original failure and its elapsed-duration-only
comparison are retained, not overwritten or silently normalized.
