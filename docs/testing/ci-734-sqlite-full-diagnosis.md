# 734 Backend SQLite Full Diagnosis

Run38204900242, commit `73458804c7f66b3ed69215321f14ac1521530b05`:
frontend/browser pass, backend114666109212 fails. Metadata generation and upload
succeed. Only the single-file sanitized metadata artifact11731151060 was read;
its published ZIP digest matches. Protected raw logs/trace/input remain unread.

26,006 collected/unique nodes: 25,324 call passes, 66 call failures, 534 setup
failures, 82 setup skips, all26,006 teardown passes. Zero missing/duplicate/
unexpected phases, no metadata errors, complete diagnostics, pytest exit1.
This proves recorded phase completeness, not a passing backend.

All534 setup failures identify native SQLiteOperationalError with error13
SQLITE_FULL and known primary13 SQLITE_FULL. The public source chain ends in
`capacity.py` startup/backup and `verify_storage_restore.py:85`. Unlike the
earlier Other classification, this identifies SQLite FULL; it does not alone
distinguish filesystem exhaustion, SQLite limits or other capacity state.

This commit predates the passed-snapshot cleanup increment `8fff3117`. Newer
CI runs must provide their own terminal evidence; no retrospective closure or
timeout/budget change follows. The separate 66 call failures span32 public
definitions, some with later bounded fixture corrections, not transferred CI
qualification. All original release gates and measured AI quality remain open.

Full private ledger: `diagnostics/ci/current-734-backend-terminal-sanitized`,
dated 2026-10-12. No fixture values or private parameter identities are published.
