# Cooperative CI Progress Shutdown

PR33's first CI attempt exposed an existing startup race in the progress helper:
the parent could send SIGTERM before Python installed its handler. The real wait
status was 143, not a clean zero. The strict infrastructure test correctly failed;
the backend reference collection and worker suite had not started.

The parent now writes one fresh private `progress-stop` request and uses the
existing drain/KILL poll counts. The request survives helper startup. The helper
validates the bounded marker before observing and still emits its normal final
nonfinal observation before returning. Empty/missing requests mean no stop;
unknown, oversized, nonregular and aliased requests reject. The existing signal
handler remains for direct callers, but the parent no longer races it at startup.

No exit-code normalization is introduced: forced kills and nonzero diagnostic
waits still fail qualification. Actual pytest failure/timeout precedence,
source/process identity checks, shared closeout deadline, public projection and
private raw streams remain unchanged. Stop publication rejects existing paths
before redirection (including FIFOs and dangling symlinks), then uses noclobber.

A deterministic control holds the real helper before handler setup until the
stop request arrives. The old implementation returns 2 with pytest0/progress143;
the corrected implementation returns 0 with a genuine progress wait0. Four whole
affected protocol modules pass 50 tests, including the unchanged real
reference/four-worker/failed-worker end-to-end test, stalled helpers, privacy and
failure precedence. These are public protocol controls, not app/game execution.
Parent I/O auditing is not claimed to propagate into every child process.

Independent review caught the FIFO publication edge case. An integrated regression
first reproduced the blocked closeout, then passed after explicit path rejection.
The original 45 affected test methods and the end-to-end file remain unchanged.

Full hosted selftests and backend qualification remain independently required.
