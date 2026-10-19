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

The separate `npm run test:browser:entry-mode` check now exercises the actual
React component in Chromium with all four captured paid views. Both seats and
modes expose enabled offered buttons, rendering submits nothing, clicks send
the exact declared callback, and unknown kinds retain the warning. Four real
screenshots and the local GET-only request ledger are preserved.

The final component, Chromium process and wrapper all exited zero. An earlier
wrapper exited one after the component passed because it incorrectly assumed
the retained application database was absent. The corrected wrapper pins that
existing database before and after instead; its bytes are unchanged. No
application API or SQLite test was run by this browser component.

Evidence: `parent-integration/entry-mode-chromium-20261008/` under the project
NFS artifact store. This is browser DOM/callback qualification, not complete
built-app, paid HTTP or final Suncleanser end-to-end acceptance.
