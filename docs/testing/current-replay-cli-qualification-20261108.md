# Current Replay CLI Qualification

Status: **ten original CLI cases pass**, with ten independently clean child
receipts. This is a selected component execution on frozen `52b63daf`, whose
2,697 backend files equal `542c5054`. The earlier
[230-pass full-discovery attempt](current-backend-synthetic-owner-20261108.md)
retains its guarded replay-launch failure and incomplete status. Its first twenty
replay cases and earlier passing modules are not repeated or added to this count.

## Original Cases And Checks

The two unchanged functions in `backend/tests/test_action_replay.py` run once,
including every original parameter:

| Function | Modes | Cases |
| --- | --- | ---: |
| `test_offline_cli_status_privacy_and_input_preservation` | valid, drift, overwrite, malformed | 4 |
| `test_cli_private_decision_export_provenance_privacy_and_no_overwrite` | valid, drift, existing, existing_report, same_output, input_alias | 6 |

They verify reconstruction status, input preservation, private output provenance,
both-seat decision records, mode0600 outputs and rejection of existing/aliased
outputs. All original assertions and parameters remain unchanged. Constructed
canonical Island fixtures execute their original checked actions; these are not
natural games or competitive deck/AI evaluation. Generated hands and traces stay
private locally and are excluded from the public change.

The ten exact `scripts/reconstruct_action_replay.py` children return two expected
exit 0, two exit 1 and six exit 2 statuses. Expected nonzero status never waives a
clean receipt: every child separately verifies source/harness pins, disabled
user-site startup, unchanged AI-entry profile guard, zero admitted SQL/AI choices,
zero runtime denials and no nested children. Missing, duplicate or dirty receipts
fail independently of the original test's exit-code assertion.

## Admission And Prelaunch Correction

Only the pinned original test code/frame, pytest case/mode, actual temporary
fixture, executable, script, exact arguments and one invocation per mode can
launch a child. Child startup fails closed before script imports. All SQL and
socket operations, provider imports, AI action search and nested processes are
denied. Child output writes require the declared new paths and exclusive create;
input writes, existing outputs and symlink writes remain denied. This is
trusted-test instrumentation, not a general filesystem sandbox. No owner-lock
fixture is used, and protected operator files and user databases remain excluded.

Review catches a prelaunch mismatch: default pytest assertion rewriting changes
the caller bytecode that the exact native-code guard expects. Explicit
`--assert=plain` preserves source-native bytecode and ordinary Python assertions;
optimized interpreters are rejected. Compile controls prove rewritten signatures
are rejected, both native signatures match and `assert False` raises. No test
source, assertion or signature check is weakened. The initial runner and finding
remain recorded; no application run is spent on that mismatch.

Controls also record the original dispatcher denying replay RED, ten source-native
frame positives using inert stubs, sixteen command/frame/mode/environment
negatives, eighteen native primitive/output denials, one compiled-native AI-entry
denial, one new empty exclusive-output positive, ten fabricated clean-receipt
positives and fifteen receipt negatives. They import no application, open no
successful SQL connection, execute no AI search and launch no CLI child.

## Verification And Remaining Scope

All 5,141 frozen public SHA-256/Git blobs and current backend files verify, with
all sixteen harness pins, historical control versions and actual child receipts.
The guard's strengthened manifest-value report predicate has a separate pure
control; existing admission/audit/profile helpers retain their controlled ASTs.
Reviewed recursive output accounting and closure functions remain unchanged.

JUnit records 10 passes, zero failures/errors/skips and 30.803s. Worker time is
31.236s and supervisor time 32.025s; these distinct boundaries are not performance
comparisons. CPU 180s/inner 240s/outer 270s/AS 8GiB/output 128MiB/retries 0 and original
child 30s limits hold. Output including the close receipt is 5,520,838 bytes. The
direct worker is reaped, its owned group is absent, and no outer stop or cleanup
intervention occurs. The metadata-only verifier reads no private fixture/trace,
database or lock bodies.

Final independent read-only review finds no actionable issue. It checks 5,140
public source files (excluding the frontend environment template), all current
backend files, sixteen harness pins, nineteen receipt hashes, child/JUnit/control
evidence and closure without reading protected or private fixture bodies.

Evidence is retained in
`/home/nick/mtg-rc-evidence-20261108/replay-cli-current/FINAL-VERIFICATION.json`.
This does not qualify the whole replay module in one execution, a full backend
suite, cold restart, browser/TLS, clean installation, hosted CI, native runtime,
AI strength or any RC gate. The historical matrix partials and fifteen flags,
thirteen-style/expert-AI scope, missing build inputs and full rules/data plan
remain open. No branch publication, deployment or default-runtime change occurs.
