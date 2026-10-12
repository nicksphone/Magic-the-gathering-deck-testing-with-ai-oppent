# Capacity Policy Fixture Portability

The pure default-path tests preserve the prior file's device, inode, size,
mtime and content digest instead of assuming earlier tests left it absent.
The rejected unacquired backup still requires its original owner error and
zero backup calls. The network-filesystem test now declares a fake local/NFS
mount table instead of requiring the runner to have our actual NFS mount.
All eight other original function ASTs are unchanged. Production capacity,
retention, locking, backup, timeouts and permissions are unchanged.

Three new pure environment controls cover prior file presence and a host with
no NFS mount. Metadata comes from a real owned ordinary file stat result;
these controls are not native SQLite, bootstrap or lock evidence.

## Actual Evidence

On isolated `788e219a`, original22 with arbitrary owned non-SQLite default bytes
produced 20 passes and 2 failures (0.82s). Adding new3 before correction gave
21 passes and 4 failures (1.10s). The corrected25 passed in 1.08s. Two earlier
24-pass/one-error runs retain incomplete new stat-fixture errors explicitly.

Five whole modules passed all 93 cases with the arbitrary file present (2.68s)
and, separately, absent (2.71s). These are the same93 cases, not 186 unique tests.
The exact public postimages also pass the same93 cases independently (2.60s).
The first wider run's four asyncio self-pipe harness denials remain archived.
The corrected harness admits only stdlib AF_UNIX stream socketpair construction;
SQLite, network connect/bind/DNS and subprocesses remain denied. Its current
export lookup is cooperative enforcement, not immutable CodeRef/tamper-proof
or kernel isolation. Source bytes and file set match during the present-file run.

Verified private evidence is under `diagnostics/ci/capacity-policy-parent93`
and its independent review dated 2026-10-12. The arbitrary existing-file input
was byte-verified on NFS before removing only that disposable local input.
No source default or live database was deleted. No hosted shared532 startup
failure closure, whole backend CI, measured expert-AI or release claim follows.
