# Autoplay Request Deadline

## Defect And Repair

The frontend applied its ordinary thirty-second timeout to autoplay writes.
Retained Master decisions have exceeded that duration, so a healthy server could
still be working when the client reported failure and attempted reconciliation.
The synchronous FastAPI autoplay route already uses the worker pool; this is
not evidence of event-loop blocking or a global server outage.

Autoplay now uses the same bounded ten-minute ceiling as the existing long-running
simulator request. Reads and manual actions keep their thirty-second deadline.
The mutation gate, idempotency key, expected revision, response validation and
ambiguous-write reconciliation are unchanged. This prevents the known short
deadline mismatch; it does not accelerate decisions or cancel backend work.

## Validation

The new actual-client test loads `client.ts` through the existing Vite toolchain,
records timeout creation and exercises autoplay, match reads, health, manual
actions and legacy simulation requests. It verifies deadlines, signals, write
headers and validated match responses without waiting ten minutes or writing a
live match. Frontend unit tests, lint and production build pass.

This is a client/runtime contract check, not a long-session browser soak or
network-disconnection test. The live backend and frontend HTTP checks pass.

## Rejected Optimization

A private direct score-key encoder prototype passed 43 focused checks after an
initial guard rejected the engine's enum classes (eight failures, then corrected).
It preserved cyclic/shared graph references, excluded diagnostic log references
and rejected foreign serialization hooks. A thirty-key probe improved from
0.258 to 0.112 seconds, but the complete retained decision only changed from
30.00 to 29.39 seconds against an archived predecessor measurement. That does
not establish a useful overall gain. The prototype is not integrated: avoiding
additional complexity is preferable to claiming a microbenchmark win.

Evidence and the verified disposable source archive are stored on NFS under
the October 5 strategic-draw diagnostics, `autoplay-deadline-review`.

## Known Limitations And Next Upgrades

Complex decisions remain too slow for interactive play. Larger autoplay tick
batches may still exceed the longer ceiling. The backend does not cancel a
mutation merely because a client disconnects; reconcile uncertain outcomes
before retrying. Background decision jobs with progress/cancellation and broader
planning/rules/release acceptance remain unfinished.
