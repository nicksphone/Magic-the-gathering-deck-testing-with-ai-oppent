# Private Operator Startup Diagnostics

Baseline: `92a59e1135fa53e1c4363734a61211bfb88e4a81`.
The existing foreground entry remains `ops/caddy/run.py`; no new installer,
service, logger, option, browser launcher or configuration field is introduced.
CI's file-only operator stage now also runs the new 14-case pytest module.
The integrating parent verifies that command without `MTG_CADDY_BINARY` set:
14 passes, zero observed native SQL/socket/process operations. This does not
start or qualify an actual backend or HTTPS service.

If either child exits without a supervisor stop request, the operator reports
only the literal service (`Backend` or `HTTPS`) and its numeric exit code.
Unexpected zero exit and negative signal return codes are still failures.
An `OSError` while spawning reports only the service and exception class,
then propagates through the existing cleanup/error path. No child output,
exception arguments, config values, credentials or key paths are printed.

Normal Ctrl-C/SIGTERM remains exit zero. Original child argv/environment,
DEVNULL streams, runtime lock release, 30-second shutdown waits, timeout KILL
and nonzero recovery result are unchanged. `--check` remains configuration-only,
not backend readiness or health acceptance.

## Unit Acceptance

- New whole 14-case module against the old producer: 3 passes, 11 strict
  missing-message failures, zero errors. Corrected producer: 14 passes.
- Four WHOLE operator pytest modules: 63 passes in 7.28 seconds, zero failures,
  errors or skips. This is the original 49 nodes plus 14 new nodes, not a
  backend or native HTTPS qualification.
- The original standalone runtime inventory script separately passed its
  12 file-only controls; these are not additional pytest/JUnit nodes.
- Every actor installed the inherited physical SQL/socket/process/provider
  fence before project imports, observed seven denied canaries and zero
  unexpected I/O, and preserved the full source file map before/end.

The new tests invoke real `main()` but replace settings admission, runtime-lock
creation, Caddy validation and child processes with explicit inert fixtures.
They capture actual supervisor output and preserve privacy, normal stop,
signal/timeout cleanup and check-only behavior. No real service, SQL connection,
socket, browser, native Caddy, deployment or clean-machine install ran.

Existing HTTPS/browser/LAN/recovery evidence remains on its original source pins.
This closes only the silent-launcher-diagnostic unit gap, not Gate 3 or the full
one-app release. A future composed runtime remains separate acceptance.
