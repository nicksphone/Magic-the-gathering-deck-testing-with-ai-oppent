# Explicit Entry-Mode Controls

The frontend now recognizes the generic public `entry_mode` mechanic and renders
each offered symbolic option as a labeled button. Clicking sends only
`{type: "choose_mechanic", choice_id: offered_id}` to the declared player.
Rendering does not choose a default, including when only one mode is offered.
Unknown mechanic kinds retain the unsupported-choice warning.

Both pending-choice and legal-move TypeScript unions include the mechanic.
The new regression checks both seats, two/one offered options, exact callbacks,
offered-only buttons, input purity, and the unknown-kind boundary. It is part
of `npm test`; full configured tests, `npm run build` and `npm run lint` pass.

The regression now reads four captured actor-visible views from real paid
Suncleanser casts and actual selected-mode resolution, both seats and modes.
It additionally checks an offered-single-mode protocol boundary. The original
captured fixtures and generator provenance are in `tests/fixtures/entry-mode-public/`.
An initial paid-helper zero-snow/missing-total mismatch was corrected in fixture
setup, not by weakening the frontend contract.

These checks exercise the real React component and handlers. They are not
browser DOM, SQLite/HTTP, or final Suncleanser end-to-end qualification.
