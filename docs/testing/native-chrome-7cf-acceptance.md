# Native Chrome Acceptance

Exact source: `7cf693bb9f425d7fcce48d0666c83fbdd6e00457`.
The [hosted Chrome job](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/actions/runs/38678680378/job/116238008173)
completed successfully on 2026-10-15 at 04:25:53 UTC.

The official packaged Chrome 155.0.8059.79 runs as non-root without
`--no-sandbox`. Preflight verifies executable/package identity, a real DOM nonce
and the browser-reported Namespace, PID/network namespace and seccomp status.
Chromium labels this expected renderer status, not per-renderer kernel
attestation; the report explicitly retains that distinction.

The complete zero-argument browser suite succeeds with all 45 ordered stage
headers and 501 observed PASS-banner lines. Those lines are not a count of
unique assertions or pytest cases. The lifecycle report records exit 0 and an
empty owned service cgroup. No scenario timeout or assertion was weakened.

This is a pinned Linux/Chrome component result, not Brave or Firefox acceptance,
whole-source release sign-off, clean-OS/LAN qualification or measured AI strength.
The sibling Brave job failed, so the overall native workflow is not green.
Later diagnostic-only source revisions still require their own qualification.

Allowlisted reports, independently checked metadata and the private synthetic
browser log are preserved under the project's NFS `diagnostics/ci/` directory.
No protected backend trace was fetched or published.
