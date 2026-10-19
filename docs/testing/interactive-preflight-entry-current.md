# Interactive Preflight Entrypoint

## Root Cause And Correction

The completed public `38e43cd5` browser job passes its preceding recovery,
copied-spell and natural BO3 flows, then waits unsuccessfully for
`window.interactiveFixture`. Its driver navigates to
`/tests/interactive-preflight.html`, but that file was absent from Git.
Vite therefore serves the normal app instead of the complete tracked fixture.

The correction adds a three-line HTML wrapper that mounts exactly the existing
`interactive-preflight.tsx` module. The fixture, App, driver, all gameplay
assertions and original deadlines remain unchanged. No backend, workflow,
dependency or lockfile changes. Four packaging regressions use the already
installed TypeScript parser; their module is appended after the entire original
43-entrypoint test chain. Their source-closure check is static, not a browser
or dynamic-import certificate.

## Verification

The worker's missing-entry regression records one failure and three negative
controls passing before the fix, then all four passing after it. Independent
review verifies the three exact postimages and original ordered test prefix.

Parent execution on the complete public source finishes the full 44-entrypoint
chain in 44.264s, lint in 3.172s and build in 6.161s, each exit zero. All 2,915
declared source hashes remain equal. Node network and pre-import Python
SQLite/socket/process denial logs are empty; no default database is created.
These pure frontend checks use an explicit 2-GiB capacity floor; the native
browser and AI 3-GiB floors are unchanged. The parent source-hash preflight first
finds one omitted committed documentation file, before any tests. Restoring its
exact Git blob corrects that isolated-copy omission without changing tests.

Worker whole-chain attempts with incomplete isolated public source are retained
as setup failures, not gameplay failures. Its final full-source chain, lint and
build also exit zero. Production Vite's ordinary single-entry build does not
ship this development-server fixture; the new tracked HTML does.

Frozen patch SHA256:
`9bbe151212c1172be209d8c0c3ea1d7f1bac919fb6afe38c4d4cfcb0c2143c27`.
Verified worker evidence under RCHFiles:
`diagnostics/ci/browser-interactive-entry-38e-qualified-20261010-2wYYq0vW/`.

Actual native preflight and complete current browser acceptance remain required.
The previous cleanup defect and the separate local conditional-copy failure
remain their own historical ledgers. No protected trace or raw backend CI log
is published by this correction.
