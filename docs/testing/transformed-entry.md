# Projected Transformed Entry

## Implemented Scope

The registered `exile_return_transformed` operation now prepares counter/chapter
choices against a serialized back-face projection. The real card remains exiled
on its front face until choices complete; resumption rechecks the source's exile
incarnation and never exiles it a second time. The existing transforming-Saga
chapter parser uses this operation. Supported land-entry choices also inspect
the projected face before commitment.

Initial loyalty uses the incoming face's printed number, existing applicable
counter replacements and the return controller. A planeswalker face without a
printed loyalty number gets zero counters and is subject to the zero-loyalty
state-based action. These are non-cast entries: source X, escape and life-paid
Phyrexian choices do not become entry costs or counter amounts.

In-place transformation is different: it preserves physical loyalty counters,
including across planeswalker/nonplaneswalker faces, rather than resetting them
to the new printed number. Front-face printed characteristics are retained for
ordinary later zone restoration. Supported counters, face indices and prepared
amounts survive the existing snapshot format.

These distinctions follow [Wizards Comprehensive Rules 306.5b, 712.14a and
712.18](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).

## Evidence Boundaries

The canonical Jace, Arlinn and Garruk fixtures were retrieved from Scryfall with
card/oracle IDs, source links and retrieval provenance. Their tests exercise
explicit engine operations, not invented card text. They do **not** establish
complete interpretation of those cards' own Oracle abilities; the pre-existing
Fable chapter and HTTP regressions exercise the actual supported Saga route.

Focused tests cover both controller seats and replacement orders, snapshot
resume, source-choice isolation, counter-ban recipient type, later front-face
restoration, loyalty-preserving transformations and a back face without printed
loyalty. The browser scenario uses the real human control and HTTP action path
to check that the exile-to-battlefield mutation happens only after the choice.

Completed validation evidence is retained on RCHFiles under project diagnostics
`transformed-entry/`. This is bounded route validation, not professional-player
AI or arbitrary-card rules certification.

Final checks: **2,435 backend tests passed**, with 292 deprecation warnings, in
a fresh tracked-source checkout with its own initial empty database/cache.
The focused set passed 68 tests; frontend lint, boundary unit tests and
TypeScript/Vite build passed. Full Chromium coverage passed the new projected
entry and existing actions, recovery/restart, simulator preflight, sideboarding
and natural AI/human BO3 flows. Mono Red/Midrange, Tempo/Dimir Control,
Tokens/Ramp and Tribal/Drain Deck completed eight seat-paired games across
sixteen repeat executions with identical full results/logs and no timeout.
This is smoke repeatability, not a statistically adequate matchup evaluation.
The tested backend files and fixtures matched the local source byte-for-byte.

## Known Limitations and Next Upgrades

Special opening entries, generalized copy/continuous-effect pre-entry projection,
cross-family replacement ordering, conditional entry replacements, noncast Aura
attachment choices and arbitrary self-exile/return Oracle clauses remain open.
This operation currently handles supported transforming-card returns, not all
modal, meld, converting or token-copy face semantics. Broader AI decision quality,
long-run matrix validation and release hardening remain in the main plan.
