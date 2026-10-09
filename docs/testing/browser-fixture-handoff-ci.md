# Browser Fixture Handoff And Scry Completion

The `c0528c8e` workflow passes its configured frontend job. Its browser job
stops in the table-v2 flow: after submitting the initial scry selection, the
rendered page still shows the legitimate second, private ordering choice while
the next scenario waits for Llanowar Elves.

The old predicate could succeed when legal controls disappeared during an
in-flight mutation. The fixture helper then bypassed the application's mutation
gate and could replace saved-match storage while the old operation was still
finishing. The log does not record exact storage-write ordering, so that
specific race is source-supported rather than directly observed.

The test now completes both genuine scry choices, waits for a committed revision
and idle mutation state, and verifies the API continuation is cleared and the
deliberately ordered Twiddle is drawn. Before another fixture is published,
setup waits for the prior operation to settle. Reload readiness requires the
requested rendered match ID, saved ID and revision. Battlefield exposes its
already-public match ID as a data attribute; gameplay and action handling are
unchanged. No write retries or swallowed errors are introduced.

The new helper-ordering regression fails on the old helper and passes after
correction. It executes the actual helper body with controlled transport; it
does not certify browser DOM behavior. The existing navigation/deadline unit
passes unchanged. A separate native check of the actual backend fixture proves
scry -> ordering -> selected top card drawn, with no SQL, socket or child I/O.
Current TypeScript no-emit checking and the complete configured source lint pass.

The SSR deadline harness also explicitly disables Vite's unused websocket
transport with `ws:false`; all deadline assertions remain unchanged. Its separate
qualified original-source full frontend run covers 35 modules and 17 guarded
Python fixture children, not the later combined browser correction.

Evidence and unchanged remote failure logs are archived under mounted RCHFiles
`mtg-deck-testing-lab/parent-integration/browser-fixture-handoff-20261009/`
and `diagnostics/ci/c0528c8e-37922748592-20261009/`.
The complete corrected remote workflow remains required. These checks do not
close all release gates, arbitrary-card semantics, expert AI or deployment.
