# Native Browser Checkpoint: 014263

Exact source: `014263f876ad7540e7f543336b4d5d30e5fadb0f`.

## Chrome

[Native Chrome job 116250473986](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/actions/runs/38682667511/job/116250473986)
completed successfully on October 15, 2026 at 05:07:46 UTC. Official Chrome
155.0.8059.79 ran nonroot with its sandbox enabled. Identity, DOM nonce and
direct-child closure checks passed; the enclosing control group was empty.
The browser reports its expected renderer sandbox status, not a per-renderer
kernel attestation.

The unchanged zero-argument browser suite completed all 45 ordered stage
headers and 501 observed PASS banners. These banners are not pytest nodes or
unique assertion counts. The standard browser and frontend jobs also succeeded
on this source; the full backend job was still active at this checkpoint.

## Brave

[Native Brave job 116250474315](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/actions/runs/38682667511/job/116250474315)
completed with failure at 05:04:52 UTC. Its preflight **passed** with the real
Brave 1.97.57 package, Chromium 155.0.8059.80, SUID sandbox layer, PID/network
namespaces and seccomp. The shorter private temporary path therefore repairs
the earlier singleton socket startup failure in actual native execution.

The whole application suite did not pass. After 38 stage headers and 463 PASS
banners, match-creation recovery observed an OPTIONS 200 pause, then an OPTIONS
failure pause, then CDP `-32602 Invalid InterceptionId`. The retained output
lacks pause correlation and continuation acknowledgments; a deeper CORS or
ordering cause is not established. Cleanup still proved the enclosing control
group empty. The overall native workflow is **not green**.

Bounded follow-up diagnostics retain only local ID ordinals, fixed response/CORS
categories and command acknowledgment/error codes. They do not change request
handling, assertions, retries, deadlines or sandbox settings, and do not claim
to fix that runtime failure.

## Evidence Boundary

Both preflight and shared-driver hashes equal the exact source Git blobs.
Allowlisted metadata and browser-only synthetic logs are verified privately on
RCHFiles under `diagnostics/ci/native-014263-terminal-20261015-I1MMstc0/`.
The terminal archive SHA256 is
`6574bac6f9471d6c35fd42bf2f59aee42351119eb76b8a38fcbfbf42e002eb40`.
No protected backend trace or raw backend log was accessed or published.

This does not qualify Firefox, later bridge code, trusted remote LAN access,
clean-OS deployment, measured AI strength or the remaining release requirements.
