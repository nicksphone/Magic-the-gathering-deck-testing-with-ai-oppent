# Fixed Producer Raw Receipt Correction

This separate component supersedes the old175 raw-file admission claim, not
its immutable measurements. The old175 source/archive and unexecuted full228
PREP remain immutable HOLD. Base: a32dbd0d67586d5f6e4d5dcea2ec8860ff9ee550.

## Defect And Correction

The immediate write/readback succeeded, but the additive producer discarded
the full write_private_game receipt. Packaging checked JSONL/gate output
receipts without reopening game01/02. Deleting or mutating the original raw
files could therefore still yield eligible=True from their independent rows.

The producer now retains the exact genuine full receipt, ordinal, actual
schedule coordinate and full result as passed to the writer, before the
existing evidence adapter adds its four-field summary to the returned result.
No receipt, raw hash, or unavailable counter is synthesized from JSONL.

Packaging rereads each actual private game file, bounded before decoding by
the existing result/snapshot cap. It rejects symlinks, hardlinked duplicates,
nonregular/foreign-owner files, identity changes, missing/mutated bytes,
unknown/unjoined game files, incomplete or substituted receipts, wrong
ordinal/coordinate, and inconsistent raw/result/sample/report-row joins.
The check runs immediately before eligibility, after the external package
charge and before its write, and again before delivery. Canonical full record
bytes, genuine record SHA and raw SHA must all agree. The complete pair needs
both actual files. Draw/resource/writer stops remain ineligible diagnostics;
missing evidence is never repaired, retried, copied or replaced with zeroes.

Only run_fixed_game_measurement and package_measurement change in this P2
increment. The genuine write_private_game, old report/comparator/default
entrypoints, round-robin/BO3 bodies and existing optional pre-encoding hook
are unchanged. No game, matrix, A/B or native artifact quota has been run or
qualified by these inert protocols.

## Actual Pure Evidence

The unchanged old175 production plus NEW19 produced actual18F/1P. Strengthened
NEW23 on the same old production produced actual22F/1P. The missing/mutated
file failures are actual incorrect admission, not an absent API import.
The real deadline characterization is the passing case in both RED epochs.
Both source stages, raw logs, JUnit, source/runtime maps and exits are retained.

After the correction, all three whole modules passed: comparison126 + old
package49 + NEW23 = actual198 PASS, 0F/E/S, pytest64.80s, outer0. All old175
ordered identities remain; 594 setup/call/teardown phases passed. Native
preimport SQL/socket/process/provider/main deny controls remain unchanged.
Full source/runtime before/end equality, identical FDs, empty children and
threads, and absence of default/owned databases were checked. No original
155/24 module bytes or assertions changed. The original report29 trusted CLI
and round-robin24 were not executed in this component.

## Real Deadline Limit

The controlled clock is used by a genuine ResourceBudget, not a fabricated
SimulationResourceLimit. It reaches the shared deadline after mirror one's
actual counter extraction and before mirror two starts. Real check_deadline
raises dimension=deadline. Only genuine game01 remains, resolved and not a
timeout. There is no second game, retry, producer file or positive package.

This proves retained first raw evidence and fail-closed incomplete execution,
NOT a durable aggregate incomplete receipt. Existing guards disallow further
packaging IO after the same deadline; no emergency retention deadline, cap
change or IO exception was added. Persisting a new stopped aggregate after
expiry would require a separately reviewed retention policy. Whole-frame
diagnostic absence must not be represented as a completed/timeout result.

## Qualification Boundary

The new complete public patch applies ONCE over immutable a32, including the
old five paths and this P2 test/document. A separate P2-only patch applies to
old175, never after the cumulative patch. Full affected roster is derived
from actual XMLs separately and is PREP ONLY until granted. The trusted
original CLI remains unaudited inside the genuine child; no inherited child
audit, PID isolation, hard stream cap, or native/SQL execution is claimed.
No UI, App, API, rules, AI, weights, game clocks, provider or CI changes.

Private raw files and test ledgers remain private archived evidence, not
public game fixtures or authentic gameplay proof. These are cooperative
owned-file integrity checks, not a kernel-atomic hostile-filesystem sandbox.
