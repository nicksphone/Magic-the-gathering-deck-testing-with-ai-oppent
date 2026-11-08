# Closed HTTP Owner Metadata Implementation Plan

> Execute inline using `superpowers:executing-plans`, TDD and fresh read-only
> review. Existing isolated worktree; no implementation subagents.

**Goal:** Preserve closed HTTP evidence without reading/hashing/copying an
owner-lock body, while retaining every other existing archival safeguard.
**Spec:** `../specs/2026-11-08-closed-http-owner-metadata-design.md`, `plan.md`
Gates1--3 and the existing protected-file constraint.

## Constraints And Interfaces

- Modify only `backend/tests/closed_http_runtime.py`, additive tests in
  `test_closed_http_runtime_lifecycle.py`, and accurate supporting documentation.
- Preserve all existing lifecycle/caller test assertions and parameters.
- `_inventory(roots)` records `owner-lock-metadata` with digestNone only for
  regular/single-link/mode0600/size0 owner locks. Unsafe locks and protected
  MODEL/FEATURES names fail before any body access.
- `_verify_archive(archive, roots, inventory)` verifies all other members and
  the complete manifest; metadata-only paths must have no tar payload.
- Tar creation excludes only those declared metadata entries before file open.
  Every other member must already be in the inventory; protected late additions
  and all unlisted members are rejected before a tar payload is opened.
  Receipt adds explicit metadata-only members and byte-member count; existing
  archive/closure/inode/readback/removal checks and fields remain.
- New synthetic protected files are created exclusively and closed immediately.
  Never read/hash/copy any lock/model body. Public FAKE SQLite-named fixture
  bytes are allowed only in fresh owned test paths; all actual SQL is denied.
- No app/network/AI/natural games, broad runtime adoption, RC gate closure or
  relabelling of previous terminal executions. No passed cases rerun for counts.

## Review Focus

- Payload omitted but still hashed: audit denial must catch any body open.
- Incomplete archive claims: manifest and receipt explicitly distinguish metadata.
- Unsafe type/link/mode/size or protected models: fail before deletion/body access.
- Late owner inode substitution: retain both roots and fail verification.
- Existing ordinary members, archive pin and closure failures retain their proofs.

## Task1: Regression Then Minimal Correction

- [x] Add owner metadata/payload, protected-model rejection, unsafe-metadata and
  late-inode tests using existing public roots/inert process fixture.
- [x] Freeze RED source with unchanged archiver and new tests; install pure
  SQL/network/process/app/protected-body guard before tests. Run new cases first
  and confirm failures occur before protected body access, retain all receipts.
- [x] Implement minimal inventory/tar-filter/verification/receipt correction.
- [x] Freeze GREEN source and unchanged guard; run the complete lifecycle and
  caller modules once, including all original cases and new regressions.
- [x] Run one separately declared full-discovery entry for the changed helper's
  import/collection integration under existing reviewed owned-SQL/owner guards.
  Preserve the known replay-CLI boundary; never present a green full suite or
  add overlapping counts. This source-change check is not a strength rerun.
- [x] Verify exact source/assertion/guard/closure/output bindings, obtain final
  read-only review, update README/roadmap/readiness together and export the exact
  committed tree. Full RC/AI/data/cold-process/network scope remains open.

## Ledger

- Start at clean2e044761; prior16whole2 checkpoint committed/exported. Static
  archiver gap independently reviewed; no protected body or cold app was run.
- GitHub roadmap issue2 remains open/unchanged June11; original full rules,
  training corpus and AI generalization requirements remain in force.
- REDepoch23564 terminalexit1:8newcases fail (7protected-body-open denials before
  contents;1hardlink-specific error mismatch),0errors/skips,source/harnesspins
  unchanged,protectedcreations8/fakeDBpaths7,no native app/SQL/AI/network/process.
  Closedwithnormalreap/groupabsence/output1,728,635 including close receipt.
- Prelaunchguard controls18denials/3emptycreations/closedFDs passed. First control
  metadata receipt write was correctly fenced outsideO; controls-v2 uses its own
  declared directory, unchangedguard, initialfailure/fixtures retained.
- First GREEN90111:whole29 cases pass,0denials,9newemptyprotectedcreations,
  25publicFAKEdbpaths, source/harness unchanged and normalclosure/output1,718,077.
- Source-change fullentry37092 is terminal230pass1knownunadmitted replayCLI
  failure, not a fullpass or additional coverage. Source/harness unchanged,
  221parent+5childnativeSQL/7cleanCLIchildren/factory1/8HTTPloops,normalclosure.
- Review-focus check identifies a later tar-stage gap: newly inserted protected
  or unlisted files could be opened before final inventory catches mutation.
  Four new late-insertion regressions are written before changing the filter.
  New isolated late-RED follows; no protected file body is permitted to open.
- Late-RED75446 terminalexit1:4newcases fail,3global protected-body denials and
  1per-test public-canary body denial,0errors/skips,source/harness unchanged and
  normalclosure/output1,705,326. No body opened. Filter now checks inventory
  membership and protected names before tar payload open; finalwhole33 follows.
- Ruling: fullentry37092 belongs to the first helper implementation, not the
  later filter correction. Do not rerun its already passed AI/game prefix for
  counts; final whole archive modules plus one full collect-only check will
  validate the final source. Full-suite execution remains explicitly unqualified.
- Final55224 terminalexit0:33whole2 cases pass,0runtime denials/actualSQL/AI/app/
  network/process admissions,12newprotectedcreation admissions/29publicFAKEdb
  paths. Source/harness unchanged, normalreap/groupabsence/output1,720,772.
- Finalcollection72784 terminalexit0:36,708unique nodes/0deselected/0executed,
  0SQL/AI/owner/children/ASGIloops. Finalsource packet equals final33 unit packet;
  allsource/harness unchanged, normalclosure/output10,960,373.
- Metadata/source verifier passes all6 source packets, original19assert/function
  preservation, all2697 final backend files, policy/control/receipt hashes,
  14positiveFAKE archives including2metadata-onlyowner archives, all closures/caps.
  No actualprotected/DB body is opened by verification. Final review follows.
- Finalread-onlyreview finds no actionable issue: helper/test semantics, current
  source/finalpacket match, originaltests,final33 XML,44JSONmetadata hashes and
  all6closures checked. Clarified ledger50entries total: parentverifier checksall,
  reviewer hashes44JSON and separately parses finalXML, excludes6XMLhashes.
  Supplementalmanifest pins8produced/baseline/control metadata files. No tests/
  app/protectedbody reads inreview. Source/docs checkpoint/export follows.
