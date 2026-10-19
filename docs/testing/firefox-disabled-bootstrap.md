# Firefox Disabled Bootstrap

This component closes the enrollment startup cycle: the real publisher writes
an owned, atomic disabled record before returning its controller, and the ASGI
cache factory can validate that record before importing the genuine fixture.
It does not start or qualify a Firefox browser or the application.

Generation zero has `enabled: false`, null episode/context and zero clock
strings. It retains the existing publisher UID/PID/start, source and origin
bindings. It authorizes no capture or native command and consumes none of the
six generations reserved for the original three BO3 windows. Enabled records,
native ACK requirements, body limits and TTL are unchanged. Replacement,
rollback and changed-publisher controls remain fail-closed.

Initial publication retains the exclusively created file's descriptor until
success or rollback. Rollback validates the root and both candidate leaves
against that retained inode before deleting owned files. It does not chase
moved files or close a descriptor reused for another inode. Failed or unknown
cleanup retains both errors; it is not reported as clean closure. These checks
assume the existing trusted same-UID protocol, not a hostile-process sandbox.

## Component Evidence

The 2026-10-19 corrected baseline ran seven whole modules: 232 passes and 20
missing-bootstrap failures. All 224 original cases passed. The first harness
attempt also exposed omitted source operands and Node's permission-mode fsync
restriction; that distinct failed attempt is retained, not labeled gameplay.

The final eight-whole-module declaration passed 195 Node and 66 Python cases,
261 total, with no skips or errors. It retains the original five whole modules,
adds 28 bootstrap controls and nine real-file fault-injection controls. Actual
write/fsync/rename/close, foreign/replaced-leaf and reused-descriptor failures
are covered. Historical four-file and close-error failures remain recorded.
Source bytes stayed equal during each run; expected denial controls passed,
unexpected IO was empty, and owned processes/groups and temporary roots closed.
The Node fence is a trusted-unit API/file fence, not a universal OS sandbox.

The original four JavaScript modules remain in their original order in
`test:unit:firefox`, followed once by both new modules. A separate one-method
workflow-schedule contract failed before this wiring and passes afterward.
Dependencies, lockfiles and the top-level npm hook are unchanged. Local Node
component execution used one process; normal npm worker execution remains a
separate hosted observation, not an inferred pass.

The Python positive stops at the genuine factory-import statement; it does not
substitute an application and claim startup. Genuine Firefox 158/BiDi, owned
server/SQLite lifecycle, current public fixture manifests, the application-50
port and the complete default launcher remain separate required acceptance.
No private historical trace is read or published by this component.
