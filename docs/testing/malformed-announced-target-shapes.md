# Malformed Announcement Shape: Executed HTTP Handoff

## Scope And Dependency

TESTS/REPORT ONLY; no production edits or ownership inheritance.
Depends on immutable fShdn2 target product source, source-only.tar.gz SHA256
556dae5f246ffae6ac1390545587f9344668d904cae77aa0911d981174c88a0b,
production.patch7ac951a51155c526bfccbf2acb184b75f44235b3c5445b081c182fdcd478d30f.
Targeting pin c2461718a26abeb036bc5c99f9cefda420f90ddeb766e778b73c6451a7f23092;
stack_engine pin4b3d7ac6540bcbfdaca5d7b88a72b99c9caee1d5b02d4a8da2783b57ac83256f.
No moving parent/main reads/writes. Existing production archive and original
scheduler2 preimage failure evidence unchanged; no fixture adaptation included.
Earlier pure-only archive IoQeQ7 is immutable and truthfully marked HTTP pending.
This report supersedes ONLY that pending status with executed evidence.

## Actual Whole Ledgers

Pure whole40:10PASS30strict desiredFAIL2warnings12.17s, exit1.
Guard denies all SQLite and network. Eighteen AttributeError and twelve TypeError
escapes across ten helper cases and twenty actual paid conditional frames. Direct
resolver finally checks prove no root mutation. Ten real paid falsy-announcement
controls reject ActionRejected and preserve root. All ordinary desired assertions,
no skips/exclusions/xfails, no invented gameplay cards/Oracle/positive StackItems.

HTTP whole12:0PASS12strict desiredFAIL26warnings10.14s, exit1.
Explicit slot after Lagrange terminal; bound300, serial fresh memory/file DBs.
Session68850, timeout1370684/Python1370685 terminal/gone; slot released.
All12 actual status500; all12 exact root/controller/SQL before/after comparisons
passed. Every file case cold SQLite readonly subprocess restore BEFORE and AFTER
request passed; in-process controller restore from persisted record also passed.
Only final desired422 assertion failed, verified from XML and saved receipts.
No setup/resource error, test source change during gate, live API/game/DB contact.
TestClient raise_server_exceptions=False observes actual HTTP response instead of
rethrowing runtime exception. No lifespan/socket listener; network forbidden;
SQLite restricted to owned audit root/memory by guard. Shared qualified3.12.3
interpreter, no dependencies installed or copied. Source/test hashes stable.

## Source-Grounded Cause And Minimal Proposal

rules_engine.targeting._target_reference_shape assumes dict announcement root,
iterable card-ID/distribution containers, dict mode mapping and dict selections.
validate_announced_target_references builds shape BEFORE validating the receipt.
Thus invalid shapes leak raw Python exceptions before structured ActionRejected.
resolve_top_of_stack invokes this before conditional pop (raw direct roots stay
unchanged). checked_action operates on a copied candidate; API assigns/persists
only on successful return. main.take_action catches ActionRejected only, so leaked
exceptions produce HTTP500 despite root/SQL immutability. This is a structured
rejection gap, NOT observed mutation, corruption or illegal gameplay admission.

Propose bounded explicit announcement-container validation in the NEW pure shape
helper before get/iteration/items: dict root, list IDs, dict distribution/modal,
recursive dict child selections, valid card-ID leaf shape. Reject with
ActionRejected; preserve legal empty shapes, independent slots/player recipients,
legacy absent-reference behavior and inherited copy references. No broad engine/API
exception catch, production permission requested rather than inferred. Amount and
unknown-key semantics need separate scope agreement, not silently broadened here.

## Test Intake And Actual Episode

Use existing full raw UnholyHeat/Cloudshift canonical fixture bytes and actual
checked paid cast/resolution from frozen product early_path. Deliberate malformed
announcement injection occurs ONLY after actual paid actions; genuine reference
bundle/StackItem/source/controller remain intact. Controlled negative episode is
installed in fresh owned match controller and persisted using existing hook, not
runtime auto-repair or invented announcing spell/cause. Three malformed families
(root-number, IDs-null, modal-child-null) x both seats x memory/file =12.
Full before/after actual receipts captured as JSON; no fields ignored.

## Delivery

Tests-only patch adds two new backend/tests modules plus testing doc; zero existing
source edits. Applycheck/apply must reproduce exact new bytes. pure.log/xml and
http.log/xml/exit, guard scripts, exactpins, receipts.tar.gz, and this report retained.
No runnable SQLite file exported to NFS. Fresh owned SQL fixture files remain local
until evidence copy verification and own completed scratch cleanup.
No universal target/grammar/ability claim, no readiness claim from red tests.
