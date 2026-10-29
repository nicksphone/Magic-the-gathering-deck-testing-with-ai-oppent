# Command Layout Plan

1. Add failing component tests for a dedicated turn-command region and exact
   callback/disabled/form behavior; implement the strip using existing controls.
2. Integrate automatic-play controls in the same strip, compact optional help,
   and apply the researched table-first visual hierarchy.
3. Verify browser placement after scrolling, keyboard focus and target clearance
   at desktop/mobile/short-height/zoom; retain existing target/combat/preflight
   regressions. Run whole frontend tests, lint and build plus independent review.
4. Update the AST graph, archive/verify private evidence, atomically deploy only
   the frontend with a verified previous-build backup, commit and push.

Design: `docs/superpowers/specs/2026-10-25-turn-command-redesign.md`.

## Verified Outcome

- Primary commands now share a viewport-anchored strip. Pass and automatic-play
  controls were moved, not duplicated; combat confirmation uses the existing
  native forms and payment checks. Required human choices link to their real
  panel, while AI-owned choices retain AI/pause guidance.
- The table uses an offline-font, felt/copper visual hierarchy and a single
  page scroll. Optional help is compact during play. The measured dock reserves
  CSS layout units rather than applying zoom twice; board rows wrap by available
  width rather than relying solely on viewport breakpoints.
- Whole `npm test`, lint and production build passed. Native pointer/keyboard
  checks passed at 1440x900, 390x844, 720x400 and 200% CSS zoom, including focus
  clearance, exact submissions, missing payments, both seats, busy fieldsets,
  AI ownership, required choices and tab exit. This is synthetic UI coverage,
  not a rules, sandbox or all-browser certification.
- Existing target/combat, beginner-setup and whole interactive-preflight browser
  regressions passed. A separate stubbed App-shell check verified compact help,
  one automatic-play button and no live API calls.
- The user-reported haste badge was reproduced in a public battlefield view.
  Effective haste now suppresses the restriction badge without clearing the raw
  condition. Pure, rendered-choice and browser regressions cover the fix and
  effective keyword loss. No backend/rules/AI/timer/schema/dependency change.
- Independent review found and corrected an AI-owned choice instruction; a new
  regression passed. Historical setup/zoom/hit-test failures are preserved in
  private evidence rather than excluded from the final cohort.
- The verified frontend was atomically deployed after readback of the previous
  build backup. Served JS/CSS matched the build. Backend/frontend PIDs and the
  match state were unchanged during deployment; user play between checks is not
  treated as a deployment mutation.

Private evidence and AST graph outputs are archived separately. Remote CI is a
separate pending check, not inferred from local results. Earlier UI/AI traces and
all prior frozen evidence remain private and unchanged.
