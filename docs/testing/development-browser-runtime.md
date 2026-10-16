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

Exact-source hosted acceptance remains separate. Neither the component counts
nor a successful production build prove that the original browser suite or
genuine StrictMode probe passed. No local browser, native service or kernel
capability probe is used for this preparation. Phase 1, native Firefox and the
complete release remain open.
