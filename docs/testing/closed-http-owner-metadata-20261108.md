# Closed HTTP Archive Protected Bodies

Closed test-runtime archives now keep valid owner locks as **metadata only**.
Their bodies are never opened, hashed or copied into tar payloads. Empty regular,
single-link, mode0600 locks remain represented in the inventory, and the receipt
explicitly lists metadata-only members alongside the byte-member count.
Protected model names and unsafe lock metadata fail before body access or cleanup.
The tar filter also rejects any member added after the first inventory before
opening its payload. Existing ownership, closure, inode, archive-pin, readback,
ordinary-member byte checks and failure-retention checks remain in force.

Only the test archiver and additive lifecycle tests change. Application gameplay,
AI scoring/search, canonical card facts, runtime defaults and deployment remain
unchanged. All nineteen original lifecycle assertions/functions are preserved;
the caller test module is byte-identical to the base. The final two whole modules
pass **33 cases: 21 original and 12 new**, zero failures/errors/skips.

## Evidence And Preserved Failures

All epochs use separate immutable packets from base `2e044761` plus declared
helper/test overlays. These overlapping counts are not summed.

| Epoch | Result | Meaning |
| --- | --- | --- |
| Original helper, eight new regressions | 8 failures | Seven protected opens denied before contents; one hardlink error mismatch |
| Initial correction, two whole modules | 29 passes | Initial metadata-only behavior and prior lifecycle/caller checks |
| Late-insertion regressions | 4 failures | Three global protected-body denials and one per-test public-canary denial, before contents |
| Final correction, two whole modules | 33 passes | Includes all original cases and twelve new regressions |
| Full discovery on the initial correction | 230 passes, 1 failure | Known replay CLI guard boundary; not final source or a full pass |
| Final-source full collection | 36,708 collected, 0 deselected | Zero cases executed; collection is not passage |

The full-discovery failure is
`tests.test_action_replay::test_offline_cli_status_privacy_and_input_preservation[valid-0]`:
`unknown-child-script` is denied before CLI launch. That execution belongs to the
first correction, before the later filter fix. Its prefix is not rerun for counts
or AI timing; final-source collection and both complete archive modules validate
the later changes within their actual scopes. Full backend execution remains open.

Pure archive tests use real filesystem/tar operations, public FAKE SQLite-named
bytes and inert process fixtures. They execute no app, actual SQL, AI, network or
child process. New synthetic protected files are created exclusively and closed
immediately; invalid-metadata cases change only those disposable fixtures. Audit
hooks stop any protected-body access before it occurs, including on the RED runs.
Eighteen guard denial controls and three native empty-creation/closed-descriptor
controls bind the protocol. An initial control receipt write is correctly denied
outside its owned directory; a fresh control namespace fixes the receipt path
without relaxing the guard. Both records remain.

The metadata/public-source audit verifies all six packets of 5,146 public
SHA-256/Git blobs, final 2,697 backend files, harness/control/receipt pins and
fourteen positive public-FAKE archives. Two archives contain owner metadata;
neither has an owner payload or body digest. All six workers are reaped with
explicit owned-group absence and final output below 128MiB including close receipts.
The verifier opens no actual lock, model or database body. The final collection
records zero SQL, AI-choice, owner or child admissions and no test execution.

Final independent read-only review finds no actionable issue. It confirms current
code against the final packets, preserved original tests, 33-pass XML, 44 JSON
metadata hashes and all six closure records. The parent audit verifies all 50
receipt hashes, including the six XML files; supplemental metadata also pins the
produced collection manifest. No application or tests are rerun by review.

The pure epochs retain CPU 120s/inner 180s/outer 210s/4GiB/retries 0 limits; broader
checks retain CPU 180s/inner 240s/outer 270s/8GiB/retries 0. Timing boundaries are not
AI performance comparisons. Private declarations, source bindings and receipts
remain under `/home/nick/mtg-rc-evidence-20261108/closed-http-owner-metadata/`.
No private runtime, model, database, hand, trace or snapshot body is published.

This removes one prerequisite for the original cold-restart module. Its actual
native process, loopback, database and newly owned lock protocol still needs
separate qualification. The previous terminal matrix partials/fifteen flags,
full rules and Oracle/data plan, thirteen-style/expert AI, clean installation,
hosted CI, build inputs, browsers/native runtime and all original RC gates remain
open. [Roadmap issue 2](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/issues/2)
remains open; this change does not redefine its scope.
