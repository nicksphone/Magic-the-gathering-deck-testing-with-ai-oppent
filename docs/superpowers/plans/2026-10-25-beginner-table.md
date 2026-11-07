# Beginner Table Implementation

- Add a tested public-state-only next-action guide.
- Integrate it above the table with plain-language definitions and navigation.
- Simplify setup labels and progressively disclose technical turn controls.
- Verify whole frontend suite, lint/build, browser keyboard/mobile behavior and
  existing target/combat controls; obtain independent review and Jev feedback.
- Archive verified private evidence, commit/push scoped changes, and deploy only
  the verified frontend build, preserving backend and user game state.

Design: `docs/superpowers/specs/2026-10-25-beginner-table-design.md`.

## Results

- Whole `npm test`, lint and production build passed. The development-build
  contract now verifies all original routes plus the explicitly added synthetic
  UI clarity fixture, rather than hiding or skipping the new route.
- 79 public-state-only guidance cases passed, including both seats, AI ownership,
  pregame subchoices, stale/unknown states and navigation to the actual controls.
- Browser checks passed for real App setup, keyboard disclosures, human-seat
  labels, automatic opening of required support review, focused action links,
  mobile390 ordering/wrapping, and the existing target/combat fixture.
- The whole original interactive-preflight browser regression passed, including
  acknowledgement, response loss, recovery, stale configuration and persistence
  cases. All API behavior in those UI fixtures is explicitly stubbed.
- Jev advised contextual guidance and correctly followed the new blocker-guide
  link. Actual focus moved to the block form without sending a game action.
- Independent review found no remaining actionable issue. The isolated browser
  used the previously documented sandbox-disabled loopback-only test setup.
- The preview frontend was atomically replaced after verifying the previous
  build backup. Backend/frontend PIDs and the saved game revision were unchanged.
- A separate baseline CI exact-count bug was corrected from twelve to the actual
  sixteen unchanged schedule methods; all sixteen passed locally. Remote CI is
  separate and is not presumed green.

Initial keyboard-protocol and fixture-entry/count failures are retained in
private evidence. These UI checks do not certify rules, AI quality, all browsers,
full human accessibility, or RC completion. No gameplay callbacks, AI defaults,
timers, schema, backend code or dependencies were changed.
