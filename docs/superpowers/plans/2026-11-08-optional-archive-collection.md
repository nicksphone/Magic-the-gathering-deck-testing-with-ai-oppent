# Optional Archive Collection Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; no implementation delegation. Independent read-only review before commit.

**Goal:** Let ordinary opaque-selection tests collect when an optional external archive is unreadable, preserving the archived cases' original availability/failure behavior.

**Architecture:** Defer the same `not NATURAL.exists()` skip condition from module import to pytest setup for the archived cases. Do not catch permission failures as absence, add exclusions, change assertions or read archive bodies.

**Tech Stack:** Python3.12, pytest's existing lazy skip-condition evaluation, public canonical fixtures.

**Spec:** Full backend entry on the prior candidate fails at the eager archive probe in `test_ai_opaque_top_choose_horizon.py:336`. Original Gates1–3 remain open.

## Constraints and review focus

- Archive absent: retain the existing explicit optional skip/reason; available: retain admission and all original assertions.
- Permission denied: retain a visible setup failure for the archived case; never turn it into absence, skip, xfail or a passing archive claim.
- Module import must not call the archive metadata probe; ordinary public tests can collect.
- Do not change the archive path, parameterization, test body, policy, models or production code.
- All permission controls use synthetic metadata faults and inspect no real archive/model/owner body. Never restart the original matrix.

### Task1: Regression and one-condition correction

**Files:** new `backend/tests/test_optional_archive_collection.py`; the archived-case decorator in `backend/tests/test_ai_opaque_top_choose_horizon.py`.

- [x] Add actual-module import with a targeted archive `exists()` permission fault; require ordinary definitions to load without probing the archive.
- [x] Exercise the original archived case's actual pytest marker with absent/available/unreadable metadata, retaining skip/admit/error behavior.
- [x] Retain meaningful RED, defer only the condition, and pass the complete new module.
- [x] Run the whole affected module with explicit fail-fast and IO/source bounds; retain any archived setup error as a failure, never an exclusion.
- [x] Attempt full backend discovery again; report any next blocker by name rather than claim whole-suite acceptance.
- [x] Review exact body/parameterization preservation and evidence; prepare the accepted correction for commit/export with source boundaries explicit. Verify exported committed tree before reporting completion.

## Execution ledger

- RED3 failures/1 pass; GREEN4 passes0.93s. Metadata faults are synthetic;
  actual module/pytest evaluator used;no archive/model/owner body reads.
- Whole2 modules,--maxfail1:106 passes(4new+102existing) and1 preserved real
  archived setup PermissionError,0skips,11.79s. Not a whole-module pass.
- Full entry now passes collection:72 passes then declared sqlite3.connect
  denial. Separate ownedSQL entry:81 passes,1 subprocess.Popen-denied CLI test,
  28warnings70.31s,25connections/11ownedfiles,25authorizedhandles,0SQLdenials.
- Guard prototype failures remain: too-early handle event before Connection
  initialization; VACUUM control attempted before commit. Corrected native
  controls and actual extracted final guard pass, including1owned/3memory
  connections,5SQLprimitive and6native/URI/factory/foreign-target rejections.
- Full owned-stage declaration label corrected only; guard ASTs equal, canaries
  not rerun. All5126 frozen inputs remain unchanged; all three nonzero workers
  are reaped normally, group absent, no outer timeout/forced cleanup.
- Parent public-source/JUnit/AST/guard/closure verification passes; production
  backend/audit exactlycc29147b. Independent final read-only review accepts; commit/export tree verification
  follows before reporting completion.

- Final review accepts preserved semantics, all non-green suffixes, overlap and
  SQL/guard/process evidence. Coverage-overlap wording clarified; no reruns.
