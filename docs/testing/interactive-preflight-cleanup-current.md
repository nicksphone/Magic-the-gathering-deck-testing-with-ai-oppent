# Interactive Preflight Cleanup

## Correction And Evidence

The published `eb8d8805` browser job passes copied Helix/Drain and three natural
BO3 flows, then fails removing the independent interactive-preflight Chromium
profile. No checkpoint inside that program passes before the cleanup failure;
its primary error was unknown in that attempt. The separate local conditional-
copy failure is preserved, not treated as proof of the same defect.

The subsequent published `38e43cd5` run reaches the same program and preserves
the actual primary error: it times out waiting for `window.interactiveFixture`.
The rendered page is the normal app. Its complete fixture module is tracked,
but the navigated HTML entrypoint is absent. This confirms a separate packaging
gap; it is not a passing native preflight or full browser result. No cleanup
error is reported in that attempt, which alone is not proof of detached native
descendant closure.

The correction latches Chromium's `close` event immediately after spawning,
waits for both output streams and the log's actual completion before removing
the owned profile, and preserves the original error alongside cleanup failures.
Browser or server cleanup failures no longer prevent child cleanup. Removal
errors still fail: there is no retry, forced deletion or ignored error.

All original gameplay assertions, waits, fixture bodies and deadlines remain
byte-identical. The original outer interactive-preflight bound remains 180s.
The patch changes only its driver, adds one regression module, and appends that
module to the existing frontend test chain; dependencies and lockfile do not
change.

Eleven actual-driver VM regressions first fail against the old driver, then pass
after the correction. They mock external CDP, Vite, filesystem and child-event
boundaries, with real Node streams; they do not launch Chromium or certify game
play. Independent parent execution also passes all eleven checks.

The parent executes the complete configured frontend chain: all 42 original
ordered entrypoints plus the new 43rd entrypoint pass. Lint and build pass.
Source and backend hashes remain unchanged during execution, and the parent
Node-network/Python-SQL-socket-process denial logs are empty. The first parent
attempt stops on a missing backend Python import path; the corrected attempt
adds that environment path only, without changing source or tests.

The worker's earlier full chain records two denied connection attempts with
uncaptured callers; that history is not relabeled as zero attempts. Its setup
failure, behavioral RED runs and cleanup-utility timeout remain archived.

## Integration And Limits

Independent static review finds no actionable issue in the exact frozen patch.
Patch SHA256:
`706d4234d17b2776f31943ed794c4dff0c3b80dd7f9b940944244c78b39be71c`.
Immutable worker evidence:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ci/browser-interactive-cleanup-eb8d-qualified-20261010-1dy4hion/`.
Its complete `SHA256SUMS` readback and all three integrated postimages are
independently checked by the parent.

A `close` wait can still consume the unchanged outer bound. Detached Chromium
grandchildren and actual native shutdown are not proved by the VM regressions.
Complete current browser execution and protected backend CI remain required.
No protected trace, raw backend log, live-user state or dependency is published
by this correction.
