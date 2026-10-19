# Development Browser CI Runtime

## Observed Failure

At exact `8d715442`, hosted browser job `116875769446` fails the original
held-response assertion in `browser-ui-v2-costs.mjs`. The bounded trace records
an aborted POST, a closed development WebSocket and script-initiated reloads.
The POST abort precedes the observed socket closure; the initial cause and
causal direction remain unknown. This change does not rewrite that diagnosis.

## Runtime Boundary

The ordinary and independent Officer launchers now build the real application
with explicit development `NODE_ENV` and Vite mode, then serve those assets
with Vite preview. Hot reload and Fast Refresh are absent; development React,
ReactDOM warnings, development JSX and the existing App StrictMode remain.
The ordinary production `npm run build` command is unchanged.

Both builds include a small test-only React entry. Before their existing browser
programs, a separate page must actually render under StrictMode and report two
renders, two effect mounts and one cleanup. It shares the application's bundled
React module; counters are incremented by real hooks, not supplied by the driver.
The driver requires development flags and successful page closure before emitting
the separate `DEVELOPMENT_RUNTIME_PROOF` record. Protocol tests of that driver
are explicitly not genuine browser replay evidence.

All 66 original scenario files remain byte-identical, preserving their 919
assertion-call sites, 45 ordered stage headers and 501-banner expectation.
Original per-program deadlines, source-copy isolation, browser flags, native
wiring, actions and assertions are unchanged. No application UI or backend
gameplay code changes. Build-time API origins remain the actual owned backends.

## Verification And Limits

The isolated component first reports four passes and seven meaningful failures,
then all 20 build/protocol cases pass. Its unchanged 116-case diagnostic neighbor
declaration also passes. Actual Vite output proves the two real configurations
contain development React and no HMR bootstrap, including a shared React chunk
for App and the probe. Independent static review finds no actionable issue.

On a private parent copy of `fe026def` plus this unchanged component, the complete
`npm test`, `npm run build` and `npm run lint` commands each return zero. The
normal build still reports a production build. The release Python runtime's
3,674 regular files, four links and 429 directories remain unchanged.

Two earlier parent attempts are retained as setup failures: the source-only copy
lacked the Git revision required by an unchanged launcher test; then an owned
home-directory TMPDIR conflicted with the passive observer's existing `/tmp`
restriction. A real Git inventory outside source and a fresh owned `/tmp` path
correct only the runner environment. All 38 affected original checks pass before
the final full rerun; no product, test assertion or privacy permission changes.

Both original shell-wrapper control commands also return zero. They use their
existing fake service/browser fixtures; this is not local native-browser proof.

## Actual Hosted Result At 5763

Run `38880857267`, attempt 1, completes its frontend job successfully. Its
browser job `116906982005` first passes the genuine development prerequisite:
React 18.3.1 reports the required development flags, two renders, two effect
mounts and one cleanup. The original suite then fails at
`browser-ui-v2-costs.mjs:61`: its expected held POST response is absent.

The bounded metadata records a continued OPTIONS request and an aborted POST
37.652 milliseconds after request initiation. A recovery GET aborts separately.
No WebSocket events or post-action navigations are observed. Thus removing HMR
does not remove this failure; the cancellation cause remains unproven. Only two
of the 45 stage headers and 18 of the 501 PASS banners are reached. The Officer
probe is not reached and is not declared passing.

This change establishes a stable development runtime and a genuine replay
prerequisite, not a fix for the held-response failure. Native Firefox, Phase 1,
the latest whole backend and complete release remain separate. No local browser,
native service or kernel capability probe was used in parent verification.

The subsequent [bounded transport diagnostic](browser-cors-transport-diagnostic.md)
compares four CDP modes without App code or altered original assertions. Its
protocol and shell-flow checks pass; the actual hosted comparison remains a
distinct future observation, not an assumed fix for this cancellation.

## Original Fixture Page Coverage

The later `5e8a8509` browser run exposes a separate defect in this development
build bridge: its original input map emits only the application and replay
probe. The original attack-all, human-actions, interactive-preflight and
simulation-preflight HTML pages are absent. Vite preview serves the normal SPA
fallback for the attack-all URL, so the unchanged browser test cannot find its
fixture declaration form. This is a harness packaging defect, not evidence that
the application's attack control is broken.

The corrected native Vite input map emits all six HTML entries. Only this
development-test build targets ES2022, preserving the simulation fixture's
pre-existing top-level await; the ordinary production command, Vite config and
production target are unchanged. No fixture TSX, App code, scenario assertion or
deadline changes. Four missing-page checks first fail while the original 20
checks pass. The complete corrected module passes all 26 build/protocol cases,
including emitted chunks, route-catalogue coverage, shared development React,
absence of HMR, unchanged await source and default production configuration.
Actual browser acceptance still requires the next hosted run.

The same `5e8a8509` diagnostic proves its single baseline action succeeds, but
fails its page-closure observation. The other three transport modes are not
reached; the initial request-cancellation cause remains unknown. Its saved
failure does not prevent the original suite from running, which independently
reaches the missing fixture page described above.

The exact follow-up `bf62c2b2` browser job `116944954950` gets past those fixture
pages. It reaches 465 original PASS console lines, including accepted-response
reconciliation, real backend restart, lost-start retry and reload recovery.
It then fails the unchanged manual recovery wait at
`browser-start-recovery.mjs:121`. The third recovery POST actually returns 200
and finishes before follow-up requests are canceled; the cause is still
unproven. This is concrete progress beyond the missing-page failure, not a
complete 45-stage/501-banner or browser-vendor acceptance claim.
