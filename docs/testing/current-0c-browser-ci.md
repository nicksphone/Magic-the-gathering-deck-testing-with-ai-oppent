# Published 0c Browser CI

GitHub run `38863018317`, attempt 1, exact source
`0c4129f58f314ef8813a187ca0be8ea0682bf2e9`, completes browser job
`116849410289` successfully at 2026-10-16 07:03:21 UTC. Frontend job
`116849410376` also succeeds. Backend acceptance is a separate job and was
still running at the independent browser reconciliation.

The terminal browser log matches all 45 ordered stage headers and all 501
PASS banners against the immutable launcher. Static comparison retains all
919 original assertion-call AST sites across 66 distinct scenario files.
These are different measures: banners are not 501 independent programs, and
static assertion sites are not runtime assertion-execution counts.

This source contains the bounded navigation/Runtime observation changes and
the reviewed setup-order correction. The actual whole browser result is
successful; historical failed runs remain preserved, and their earlier abort
cause is not retroactively declared known.

The configured generic CI explicitly uses its existing `--no-sandbox` mode.
This does not qualify sandbox-intact Chrome/Brave/Firefox, native Firefox
input flows, a clean install, LAN trust, Phase 1 or the complete release.
Only the terminal browser log and public source were reconciled; neither the
protected synthetic trace nor raw backend job logs were downloaded.

## Subsequent b720 Checkpoint

Run `38866253264`, attempt 1, exact
`b7201869f52b4de4fa36f5959718986c02dbf93a`, also completes browser job
`116859658108` successfully at 2026-10-16 07:40:29 UTC. Independent terminal
reconciliation again matches all 45 ordered headers, 501 PASS banners, 66
scenario files and 919 original assertion-call sites. Frontend succeeds too.
Its backend job and the earlier `0c` backend remain running at the 07:58 UTC
observation; no backend artifact or log was downloaded by that watch. The
same no-sandbox/native-browser and whole-release limitations apply. This
source-specific pass does not qualify a later selector change automatically.

## Subsequent 8d Held-Response Failure

Exact `8d715442`, run `38871299367`, browser job `116875769446`, fails the
unchanged `assert.ok(held)` in `browser-ui-v2-costs.mjs`. The bounded native
history records a canceled POST, development WebSocket closure and subsequent
script-initiated reloads. It does not establish why the first socket closed or
which event caused the initial abort; no CORS or server-restart cause is assumed.

The subsequent [development-asset runtime preparation](development-browser-runtime.md)
removes live HMR from the two browser fixtures while preserving development
React, actual StrictMode verification and every original scenario. Its full
frontend package commands pass locally. Genuine replay and whole browser
acceptance still require the next exact-source hosted run; older successful
browser ledgers are not substituted for it.
