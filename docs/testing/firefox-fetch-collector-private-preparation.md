# Firefox Fetch-Only Request Collector: Private Preparation

Base: `e4f797e68196ad3565fe4ecf66b23de92ad90df4`. This is a private,
mocked-protocol slice of whole-launcher enrollment, not a native Firefox result.
All original scenario/assertion files remain unchanged. The implementation and
new tests are subsequently composed into the working repository after review.

## Shared Fix

`firefox-transport.mjs` acquires one page-owned request-data collector before
registering a Fetch intercept. The collector identifier is published only by the
matching successful native reply handler. Fetch/Network enables join the same
pending registration; repeated Network enables retain their existing native
subscriptions. Invalid Fetch options fail before collector creation.

Close and future-child arming reject an in-flight collector registration rather
than closing early or creating a second collector. Network acquisition also refuses
active child arming. The existing child registration receipts and command ordering
are otherwise unchanged; no Target.attached/debugger-pause equivalent is fabricated.

A negative/malformed collector reply admits no Fetch intercept or invented cleanup
identifier. If intercept registration fails after a valid collector ACK, the known
collector remains owned by the page and is removed by its existing close path.
Fetch.disable/rearm retains that collector until page close. Cleanup errors stay
errors; there is no implicit retry, fallback, deadline increase or swallowed ACK.
All native-command/pending/data limits remain unchanged.

## Recorded Pure TDD

The first administrative RED is retained: 2 passes/14 assertion failures, plus a
harness receipt write denial on exit. The receipt path was then admitted exactly;
new race assertions were reordered to detect duplicate collectors promptly instead
of waiting for the original protocol timeout. No original test was edited.

The corrected baseline RED is 2 passes/14 assertion failures, exit1, empty stderr.
The same new16 cases then pass, exit0, with no further test changes. The four whole
modules pass138 cases in1.426s: original transport89 + driver32 + new16 + the
navigation module's test-file entry1 (its two console PASS messages are not extra
Node test cases). The only whole-cohort stderr is the existing MockTimers
ExperimentalWarning. No failures/errors/skips/cancellations or unexpected denials.

The administrative preload runs before project imports, rejects real socket/HTTP/
DNS, child/worker, native-addon, SQLite and provider entrypoints, and restricts test
writes to the owned temp root. Its13 denial controls pass; no child survives. This
is a cooperative JavaScript test guard, not kernel sandbox/native-syscall attestation.
The tests use explicit synthetic socketFactory replies and owned temporary files;
none of their replies is native browser evidence. No browser, SQL, provider, lease,
runtime clone, install, native probe or native grant was used.

## Remaining Whole-Launcher Barriers

This only addresses collector prerequisite F in the sealed CpWFhJ5T architecture
proposal. Common runner/owner enrollment, exact async data-URI handling on the
current driver, genuine Runtime observation, viewport/mobile/media semantics,
truthful Firefox profile ownership, expanded runtime/role/source bindings and a
separate parent-owned full-gate contract are still required. Response-body caching
stays disabled for this launcher; raw CDP Input and Target autoattach remain
unsupported, and Firefox passive-CDP evidence still fails closed. No part of this
pure test packet qualifies the original45-stage/68-entry whole browser launcher.

The parent reviews the source and independently verifies that the composed code
and tests match the tested postimages. Do not use this document or these pure
results as native execution authority.

## Independent Cleanup-Ownership P2 Correction

The original138-case candidate and its archives remain historical. Independent
review found that page close retained a collector ID after successful removal;
a later unsubscribe/context-close failure made explicit cleanup remove that ID
again. The child-arming removal caller already cleared ownership after its ACK.

Only page close is corrected: capture the exact collector ID, and retire that
same ID in the matching successful native removal callback. Negative/late-unknown
replies cannot retire it. Later cleanup failures still propagate; the first failed
close remains failed. No automatic retry or cleanup-deadline change is introduced.

Four new protocol cases use opt-in stateful mock ownership that rejects duplicate
removal: unsubscribe failure, context-close failure, stalled then failed context
close after removal ACK, and a negative removal ACK retaining the ID until an
explicit successful cleanup. The old16 test-case bodies are byte-identical; only
their common fixture gains this opt-in strict mode and mock teardown release.

On frozen138 production source, the new20-case module is17PASS/3FAIL; only the
three successful-removal/later-failure cases fail. The corrected source is20PASS;
the same original four-module cohort is142PASS, exit0 (original121 + new20 +
navigation test-file entry1). These are pure supplied protocol replies and owned
temporary-file controls, not real Firefox/runtime/security acceptance. All previous
whole-launcher and native-execution limitations above remain open.

## Normal CI Enrollment

The parent adds the new module to `test:unit:firefox`, retaining both original
module operands. The existing top-level `npm test` already invokes that script.
The missing-script check first fails; after this one-line enrollment correction,
the actual `npm --prefix frontend run test:unit:firefox` passes all 141 cases
with no failure, cancellation or skip. This three-module command excludes the
navigation file's separately counted entry, explaining its difference from 142.
It is not a native browser run or a new physical I/O-confinement certificate.
