# Firefox Release-Owned Launcher Protocol

The release-owned launcher now has source wiring for the existing genuine
enrollment publisher and lazy application factory, current backend PID/start
identity across restart, and the three original BO3 capture windows. The first
47 application scenarios remain outside capture. The original 50-case program,
callbacks, outcomes and work/cleanup limits are retained.

Firefox startup also waits for its actual owned loopback listener before the
one-shot BiDi session. The launcher-local TCP readiness barrier closes every
probe before proceeding, stays within one fixed 90-second deadline and still
requires the transport's actual readiness acknowledgment. It adds no generic
transport retry and changes no Chrome or Brave launch behavior. Only
`ECONNREFUSED` is retryable; other asynchronous socket errors retain their
original identity and reject after the probe actually closes.

## Protocol Evidence

The corrected-realm launcher cohort previously passed 289 protocol-unit cases:
223 JavaScript and 66 Python. Its corrected before-producer cohort had 12 passes
and 16 assertion failures. Earlier raw ledgers remain separate: the original
28-case run had 11 passes and 17 failures, including two realm-fixture failures;
the original whole289 had 287 passes and those two fixture failures. Fixing the
test helper's array realm also unmasked the original UNKNOWN-owned guard gap.
No original assertions were normalized or removed.

The first listener tests-first cohort had two passes and six assertion failures
across eight cases. A later 11-case tests-first cohort, retaining those eight
cases and adding asynchronous-error preservation controls, had ten passes and
one assertion failure before the error correction. These are separate RED
epochs, not a combined result or native listener evidence.

The corrected component subsequently passed all 300 cases across ten whole
modules: 234 Node and 66 Python, with zero failures, errors or skips, at
2026-10-19T19:22:42.480271Z. Source before/end hashes matched, trusted unit API
fences reported no unexpected denials, temporary roots closed and owned process
groups were absent. These fences are not a universal native OS sandbox.
The closed receipt is
`diagnostics/ci/firefox-LISTENER-ERRORFIX-300PASS-CLOSED-20261019-6fTXocAA/RECEIPT.json`,
SHA256 `09eb5d4e671c11ca7b917ef4df45f039ff23ae5a848c857b6710b390ce43164a`.

This publication source starts from exact capacity commit
`57e864a91a02884dedc544e0337e4acceef8442c` and overlays only the nine declared
nongraph Firefox publication paths before an AST-only graph refresh. The
earlier component pass does not certify this fresh full-source composition.
Parent qualification must execute the same whole 300-case cohort on this exact
source, plus the separate single Firefox unit-schedule check, and record actual
counts and source/IO/resource closure before publication.

The normal `test:unit:firefox` command preserves its original six operands and
order, then appends the 28-case launcher contract and 11-case listener protocol
modules. The existing schedule test adds the same two literal expectations;
its original six module expectations, enclosing assertion and test identity
remain. No dependencies or lockfile are changed.

## Qualification Boundary

These are source and inert protocol-unit contracts. They do not start or qualify
Firefox158, a real application factory, the original 50 browser scenarios, a
Chrome/Brave/Firefox matrix, deployment or release. Genuine gen0 factory startup
and current signed native runtime intake remain separately reviewed integration
prerequisites. The existing health-smoke PREP remains bound to its exact older
launcher4b9 source; this publication does not silently rebind it to the listener
candidate or grant it execution authority.
