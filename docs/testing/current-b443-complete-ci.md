# Published b443 CI Checkpoint

GitHub run `38737292285`, attempt 1, succeeds on exact published source
`b443db8ad51d4d86662991e634afbb017b81e406`. Backend job `116429717964`
completes successfully at 2026-10-15 17:15:40 UTC. The workflow is terminal
success, not merely a locally passing subset.

## Independently Reconciled Backend

The exact allowlisted artifact contains only `backend-metadata.json`. Its
transport digest and sole ZIP entry are verified before reconciliation. No raw
backend log, protected trace or witness was downloaded.

There are 29,150 unique collected nodes and 87,368 phase records: 29,068 passed
ordinary calls and 82 recorded setup skips. The skipped bodies are not passing
executions. The 111 passing subtest reports across 21 parents are separate,
not additional unique nodes. No failed, errored, missing, duplicate, unexpected,
expected-failure or deselected phase is present.

The independently retained 899-case Phase 1 roster matches all 2,697 passed
setup/call/teardown phases, and all 29 component module hashes match the retained
source manifest. The five source-compatibility guards that failed on `2d106588`
now pass all phases; 17 added identities also pass, with none removed. The
historical failed run remains failed. Production backend and workflow bytes are
unchanged between `2d106588` and `b443`; the approved correction is test-only.

Private immutable evidence is under the project's NFS archive:
`diagnostics/ci/backend-b443-terminal-metadata-reviewed-20261015-UUfhYYBK/`.
The receipt SHA256 is
`ab8519e5a11835e96767b66d94af10393ff20b73561be5feab5a314b7d4c556c`.

## Newer Source Is Separate

The later published `7d2d77bd` changes the shared copier, AI/mana copy callers,
knowledge-ingestion protocol and tests. Its backend job is a separate run;
the `b443` whole pass does not certify those changes.

The newer frontend and generic browser jobs pass. Browser job `116547745996`
in run `38771370703` independently matches all 45 ordered stage headers and
501 PASS banners, with the same 546-entry stream as `b443`. The unchanged
zero-argument launcher declares 68 programs. All 239 reviewed source files
match Git and remain unchanged during that reconciliation. Its private receipt
is `diagnostics/ci/browser-7d-independent-20261015-qbhPgGtp/receipt.json`, SHA256
`4e906930a67db9495a1ab4076d2d48e1aae364815312e5734ecaeb62168b384b`.

The generic browser job retains its inherited no-sandbox mode. This is not native
Firefox acceptance, secure vendor-browser qualification, LAN deployment,
measured AI strength, a completed Phase 1 or release sign-off.
