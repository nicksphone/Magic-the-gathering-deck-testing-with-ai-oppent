# Backend Capacity Rejection Annotations

The pre-private-input capacity admission now emits one optional, bounded GitHub
error annotation before the existing rejection line. It does not change the
SDK removal plan, protected paths, byte floor, 300-second cleanup timeout, or
rejection exit status 2.

## Public Metadata Contract

Exact title: `Backend capacity rejection`. The ASCII JSON body has exactly
three keys: integer `schema: 1`, string `reason`, and integer `exit_code: 2`.
The whole stderr annotation line, including its newline, is at most 256 bytes.
Example:

```text
::error title=Backend capacity rejection::{"schema":1,"reason":"byte-floor","exit_code":2}
```

The closed reason set is:

```text
runner-path
sdk-path
protected-overlap
hosted-backend-context
runner-image
workspace-binding
sdk-identity
sdk-cleanup-timeout
sdk-cleanup
sdk-remains
byte-floor
arguments
filesystem-observation
unknown
```

Readers must validate the exact title, byte bound, complete key set, primitive
types and enum; reject unknown fields, duplicate keys, coercions and multiple
matching records. A matching annotation describes that admission rejection only,
not a successful job, SDK deletion, capacity sufficiency, or game outcome.

Known reasons retain the entire old stdout behavior and final
`CI_BACKEND_CAPACITY_REJECTED reason=<reason>` line. Unknown `CapacityError`
text is explicitly hardened to `unknown` on both streams rather than copied.
`OSError` maps to `filesystem-observation` without formatting its message.
Annotation write/flush failures of type `OSError` or `ValueError` are optional:
no retry, recursive report or replacement of legacy stdout/exit2 occurs.
JSON construction and the legacy stdout print remain outside this exception
guard; unrelated programming errors are not swallowed. Success emits no error
annotation. No raw error, path, command, environment or private input is added
to the annotation.

## Observed Qualification And Limits

The parent reports four whole stdlib modules completed on 2026-10-19 at
19:19:42 UTC: original capacity26, original job roles8, NEW reason annotation7,
and NEW optional-sink3; 44 PASS, zero failures/errors/skips. Production SHA256:
`1c8da9290688847d35985099910fb7e81d45e2e77d33fa9c7266722a5d877475`.
The actual cohort used the existing stdlib API guard, full source before/after
equality, nine expected negative API controls plus one FD-read escape denial,
an owned-FD positive control, no unexpected denials, no remaining temporary
paths, and no extra threads. This is not a physical OS sandbox claim.

In this final run, stdlib `shutil` was bound before the `os.open` wrapper, with
its FD-capability registry unchanged. The actual `shutil._rmtree_safe_fd` route
made 168 observed owned opens; `safe_fd_cleanup` and
`native_fd_registry_unchanged` were true. The earlier 19:12:31 semantic44 PASS
receipt is preserved but is not used as proof of that real FD-cleanup route.
Final finite receipt:
`diagnostics/ci/capacity44-REAL-SAFE-FD-FINAL-CLOSED-20261019-AGG4jVoh/RECEIPT.json`.

These are helper/unit and owned-filesystem protocol tests. Privileged SDK
cleanup is mocked; the result does not establish real SDK deletion, hosted disk
capacity, whole-backend acceptance, or a historical failure's cause. The earlier
sink regression had six expected branch assertion failures; its initial run
also had 168 failure-reporting read denials and was not boundary-qualified.
It is not relabelled as qualified by the later green run.

PR5 run `39294722603`, worker2 job `118207855228`, failed capacity admission
before dependency/private/test execution. Its precise rejection reason remains
UNKNOWN. No archived job logs or ZIPs were fetched for this change; the early-log
reader stayed a proposal. Future exact bounded annotations remove the need to
read raw logs for this finite rejection reason.
