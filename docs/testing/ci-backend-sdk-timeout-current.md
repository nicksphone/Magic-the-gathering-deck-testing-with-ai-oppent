# Hosted Backend SDK Cleanup Timeout

Published `ed3bf11fdf7ce7150a4234d152c9370696b8cc54`, run38127352989,
backend job114434373306 fails runner-capacity admission before metadata-reporter
tests or backend tests execute. Both test steps are skipped. The uploaded
allowlisted metadata records `EVIDENCE_MISSING`, no collected identities and no
pytest exit code. This is not a gameplay-failure or full-backend result.

The fixed public admission records show dotnet reclamation at
2026-10-11T09:09:32.3035233Z, Android reclamation at
2026-10-11T09:09:49.9570950Z and `sdk-cleanup` rejection at
2026-10-11T09:11:49.9586155Z. The Android operation stops after120.0015s,
consistent with the existing120-second command timeout. The old generic reason
does not independently distinguish timeout from another command failure.
Only fixed admission enums/timestamps are retained from this pre-private-input
job; no private preparation or protected test step executes.

The follow-up changes the same fixed SDK-removal command to a finite300-second
budget per root, at most600 seconds across both roots. Timeout remains a
fail-closed rejection with the distinct fixed reason `sdk-cleanup-timeout`.
No automatic retry, arbitrary deletion root or successful-admission fallback is
introduced. Context, image, ownership/mode, symlink, overlap, inode, remaining
root and both20-GiB floor checks remain unchanged. Gameplay, browser and native
benchmark clocks/counters are not changed.

Two new pure mocked-command regressions fail against the previous code, then
the complete126-check CI script suite passes in13.065s. They verify slower fixed
cleanup can proceed within the bounded policy, and a timeout still stops after
one command without leaking exception output. The original command-timeout
assertion now checks the intentional300-second policy instead of120; all other
original checks remain. No privileged removal is executed locally.

An independent static review verifies the exact two-file diff and unchanged
safety checks. These tests prove policy behavior, not actual hosted cleanup or
full backend success. Published `1f08a6ca`, run38128147774, now actually passes
hosted runner-capacity admission and metadata-reporter checks. Frontend CI
passes; full backend and browser jobs are still running at this checkpoint.
This closes the observed SDK admission failure, not whole-suite qualification.
The separate `b0880389` run38125893436 passes frontend
and its whole browser job, with its backend still active at this checkpoint.
All original release requirements and measured AI quality remain open where
unproved. No protected trace or raw private backend logs are published.
