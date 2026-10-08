# Human Response Controller Role

The response countdown prerequisite now checks the current priority player's
public controller role instead of assuming that the human occupies seat 1.
An AI priority holder or a missing controller mapping does not open a human
response window. Existing timing, mutation, restore and legal-pass checks remain
unchanged.

## Evidence

The candidate was prepared from commit
`78a720d3c2023d9a7cc6fd28cbd3f575457e02ce` in an isolated source checkout.
The regression extracts and evaluates the actual App variable initializer using
the existing TypeScript dependency; it does not duplicate the policy.

- The complete 36-check baseline failed with six mismatches.
- The same 36 checks passed after the one-line production correction.
- The configured full frontend test command, lint and build each exited 0.
- Package test integration appends the regression without removing existing tests.
- Parent App, package and regression postimages match the tested candidate;
  package-lock is unchanged.

Completed logs, baseline failures, candidate postimages and built assets are
archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/human-response-role-qualified-20261008/`.
The candidate archive SHA256 is
`5f2d94c4c86c30641fb2a9f6fa79596b8414f18bbff85d6ebcde150880ba7181`.

## Limits

These are public-view prerequisite and frontend build checks, not live DOM,
timer, HTTP or browser qualification. Both-seat live response countdown, pause
and priority-pass behavior still require an affected browser cohort. No backend
product, timer semantics, dependencies or retained user database were changed.
The successful full frontend test used the then-existing qualified Python
runtime; its later disappearance does not establish qualification on a different
runtime. Fresh-runtime backend and browser evidence remain separate.

## Seat-Neutral Setup Labels

The setup labels now say Deck A and Deck B, rather than assuming that seat 1
is the human and seat 2 the opponent. The actual Controls rendering regression
checks both labels for both seat selections across all three match modes.
The old labels failed the first new assertion; the corrected candidate passed
the rendering regression, all configured frontend unit checks, lint and build.
The existing 36 App response-guard checks also passed unchanged.

Evidence is archived at
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/seat-neutral-labels-qualified-20261008/`.
These checks do not establish live browser countdown or priority behavior.
No backend, role logic, callbacks, dependency pins or user database changed.
