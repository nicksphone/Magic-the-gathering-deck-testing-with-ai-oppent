# Rules, Choices And Color Composition

## Implemented Scope

- Collect a cycled card's own anchored trigger outside the battlefield, using
  the existing effect compiler and chosen cycling X. Canonical Shark Typhoon and
  Renewed Faith include both-seat HTTP restoration and deliberate optional choices.
- Bind self-death source LKI when the trigger is created. Counter/power-based
  token quantities use that frozen receipt rather than a later incarnation.
  Unsupported dynamic quantities are diagnosed, not replaced with one token.
- Use effective live colors for damage, colored exile and conditional static
  abilities, and retained source characteristics for an older stack object's
  protection/target checks. Targets still use their own live characteristics.
- Reject unrecognized and wrongly placed requested parameters for loyalty,
  equipment, crew and cycling before intent normalization. Producer display
  metadata never selects targets or resources for the actor.
- Warn and prevent unsupported mechanic confirmation in the UI. Preserve known
  controls, both seats and private choices; keep the backend authoritative.
- Refresh existing latest built-in archetype labels only after complete local
  card hydration and positive, full-coverage analysis. User/history rows stay
  intact. This does not improve AI policy or fix first cold-import labels.

## Coupled Qualification

The 66-module rules/color composition passed **1,402 checks**, 246 warnings,
349.94 seconds, with no skips, expected failures or deselection. Its source
manifests are identical before/after execution, excluding generated image cache.
The later metadata increment passed **60 checks** on this composition. Two older
counter-dependent death requirements now pass ordinarily; their obsolete expected
failure markers were removed without changing their assertions.

Fresh warning UI qualification on the published baseline passes **16 actual-App
checks**, 16.240 seconds, with canonical supported actions, both seats, private
views, malformed-wire rejection and no unsupported action POST. Lint/build and
component gates pass. The standard `npm test` now includes focused manual-mana,
mechanic-warning and Suspend checks. Historical comparison is explicitly opt-in;
ordinary component checks work without Git history.

Counts overlap across gates and must not be added together as independent games.

## Replay-Found AI Contract Defect

Seat-balanced Tempo/Dimir Control smoke resolved both samples with zero
determinism failures. Tokens/Ramp failed at seed `2225858263`, tick 274, turn 10:
the AI added `target_card_name` inside a strict target object. The malformed
decision was rejected, not silently executed or converted to a pass.

The shared materializer now omits that display-only field in all five affected
targeting branches, preserving target IDs, ranking and strict API validation.
Four canonical Nissa/Naturalize before-fail controls cover both seats and actual
checked actions. Legacy policy doubles receive current model bookkeeping defaults
without changing their printed data or weakening production validation. The
initial harness errors and the failed replay remain separate archived evidence.
The AI wire/policy gate passed 270 checks. Its post-fix Tokens/Ramp replay
resolved the first paired arrangement identically, but the second exceeded the
360-second bound at tick 902, inside a blocking decision. That exit 124 is not a
completed paired replay. Later full-snapshot reconstruction/profile is separate
evidence, not a snapshot captured by the original timed-out trace.

## Subsequent Composition

The six-patch 83-module gate passed 2,024 checks in 654.71 seconds, with no
skips, expected failures or deselection and identical source manifests. Its
initial invocation passed 2,018 and failed six cold subprocess imports because
the documented PYTHONPATH was missing; that failed evidence remains archived.
The unchanged gate passed from a fresh checkout with the corrected environment.

Later token/cold-import and trigger-context compositions passed 153 and 123
checks. Artifact/enchantment token types, first built-in canonical admission,
cohort identities and matched trigger instructions are covered by their scoped
documents. Human-flow16 passes 212 actual-App assertions; modal/Adventure flows
separately pass 144 browser assertions. These counts overlap and are not games.

A separate default suite exceeded 1,800 seconds at 64%, exit 124. It has no
terminal full-suite counts and is not a release pass. All evidence and finished
synthetic databases are archived on mounted storage; no test SQLite is deployed.

## Remaining Limits

General layer cycles, compound mechanics, paid optional continuations,
post-mana Escape witnesses, Delver private reveal/timing, multiple matched cast
abilities and broader face/selection composition remain separate work.
Generic-import admission and full release acceptance remain unfinished.
Existing saved games may contain effects
compiled under older rules; starting a fresh game is appropriate for comparing
new decision behavior. No broad win-rate, expert-AI, arbitrary-Oracle or network
release certificate is asserted.
