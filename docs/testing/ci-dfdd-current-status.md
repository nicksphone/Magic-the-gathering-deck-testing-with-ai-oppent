# Current CI And Runner Capacity

Observed 2026-10-10 UTC. Public source:
`dfdd121e73cbb43589a36f7c089d49e872b285d1`.

## Current Results

GitHub run `38092293252` completes the frontend job `114331027467` and
browser job `114331027570` successfully. This is the original whole workflow,
including the zero-argument browser action/recovery command, not a selected
subset. The backend job `114331027651` is still running at this observation.
No backend pass, terminal count or private-trace outcome is inferred.

These are current job-level results. The earlier 497 checkpoint / 45 stage /
67 invocation accounting belongs to the separately inspected `58ab2881`
browser log; it is not newly counted from this current job's metadata. Its
fixture, Vite-versus-built, deck and topology limitations remain applicable.
See [earlier browser scope](browser-58ab-current-acceptance.md).

## Previous Backend Stop

Run `38082052366`, source `58ab2881`, has a terminal failed backend check
`114300810842`, completed `2026-10-10T22:49:52Z`. One of two platform
annotations reports disk exhaustion. There is no sanitized backend result
artifact, so no completed test count or gameplay failure count is available.

The finding comes from platform metadata, not inspection or publication of
the protected test logs or synthetic trace. The current live job was not
canceled or restarted. Runner-capacity remediation is separate from this
failed result; it is not yet an executed fix or a full-backend certificate.

## Runner Capacity Change

The backend workflow now prepares its disposable GitHub-hosted Ubuntu 24.04
runner before private inputs or pytest. It validates the job, repository,
workspace, runtime paths and fixed unused SDK roots, then removes only
`/usr/share/dotnet` and `/usr/local/lib/android`. Their installation roots are
documented by the upstream [.NET installer](https://github.com/actions/runner-images/blob/main/images/ubuntu/scripts/build/install-dotnetcore-sdk.sh)
and [Android installer](https://github.com/actions/runner-images/blob/main/images/ubuntu/scripts/build/install-android-sdk.sh).
Python, action toolcache, source, test outputs and protected inputs are excluded.
Local/self-hosted/wrong-context invocation rejects before cleanup. This is a
trusted workflow-context check, not cryptographic host attestation.
Root ownership remains required. Only the fixed .NET root may use the exact
0777 mode set by GitHub's [post-deployment configuration](https://github.com/actions/runner-images/blob/main/images/ubuntu/scripts/build/configure-system.sh);
other writable modes, writable Android roots and symlink roots remain rejected.

Both workspace and runner-temp filesystems must have at least 20 GiB available
after reclamation. This is an explicit operational floor, not a measured
whole-suite peak or a storage quota. Reclamation still runs when the initial
floor passes: an instantaneous free-space observation cannot prove later
scratch demand. Rejection stops before the protected-input decoder or tests.
No pytest selection, wrapper, test environment, assertion, clock, private
trace handling or metadata-reporting logic changes.

Capacity tests mock privileged commands and use only disposable filesystem
fixtures; no SDK cleanup runs on the developer host. Full original public
reporter/privacy controls are retained. Actual hosted capacity and full backend
completion still require the next candidate's original whole CI execution.

## Remaining Acceptance

Full protected backend completion, current combined built/HTTPS browser
acceptance, complete AI objective horizons and measured AI quality remain
open. A source-byte comparison for the corrected private AI harness covers
23 selected files at both revisions; it is not native execution or admission
of all setup/runtime dependencies or the 52 decision roots. No original
release requirement, assertion, test denominator or quota is reduced.

Private sanitized metadata and the source comparison are preserved under
`diagnostics/ci/current-dfdd-release-reconciliation-20261010-2tBSKlAO` in the
project's verified RCHFiles archive. The protected trace remains private.
