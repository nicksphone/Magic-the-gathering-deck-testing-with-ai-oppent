# Published 7d CI Checkpoint

GitHub run `38771370703`, attempt 1, succeeds on exact published source
`7d2d77bd053e3a7f7eade9a7b542338f2f15c24a`. Backend job `116547745594`
completes successfully at `2026-10-15T21:09:22Z`. Its test step runs from
`16:45:32Z` to `21:09:16Z`; observation timeouts were not treated as failures or
used to restart the job.

## Independent Metadata Reconciliation

Only the exact allowlisted artifact
`backend-metadata-7d2d77bd053e3a7f7eade9a7b542338f2f15c24a-1` is downloaded.
Its GitHub transport digest matches, and its sole ZIP entry is
`backend-metadata.json`. No raw backend log, protected witness or trace is read.

Independent reconciliation finds **29,212 unique collected nodes**, 87,554
ordinary phase records, **29,130 passed calls** and 82 setup skips. The skipped
bodies are not passing executions. All teardowns pass; collection/discovery
counts match, with no failed, missing, duplicated, unexpected, deselected or
expected-failure phase. The 111 passing subtest reports across 21 parents are
counted separately, not added to the unique-node count.

All retained 899 Phase 1 component identities match exactly one passed setup,
call and teardown. Twenty-seven of their 29 module sources match the preceding
`b443` roster. The two changed modules are the explicitly updated fuzzy-request
fixtures in cache recovery and stored-deck corpus CLI; their retained identities
still pass. The same published completeness-audit function is independently
executed on sanitized hash-only records, with no application or test import.
The 33 new Task 1.2 identities also independently match all 99 passed phases;
their source hash equals the exact published module. That roster is recovered
from the separately retained local JUnit and collection transcript, not inferred
from the aggregate hosted total.

This run qualifies the `7d` shared copier and Task 1.2 protocol changes on their
actual source. Its generic browser and frontend jobs also succeed. It does not
qualify the subsequent `8083a80e` cache repair, native Firefox, live migration,
the literal handwritten-card-data requirement, measured AI strength or release.

Private metadata reconciliation is archived under
`diagnostics/ci/backend-7d-terminal-metadata-reviewed-20261015/`.
Its reconciliation SHA256 is
`7fffe7067c5de32ac5c9534b1315faf60e3990ac2c65191fabc9b4d32dd3c1a4`;
the full manifest SHA256 is
`77d80194b645a2502927af944c71d3f6def9db51f605aba4260cc5ef479780da`.
