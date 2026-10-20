# Public storage-owner rename regression

```bash
node --test frontend/tests/release-owned/public-storage-owner-rename-budget.test.mjs
```

This one whole module declares21 tests:20 protocol cases and one owned-filesystem
atomic-rename control. It is not a rerun or qualification of an older larger
cohort. The `public487` case label preserves existing public case identities;
it is not a source version/hash requirement.

The helper reads the sibling checked-in `run-current-built-acceptance.mjs` at
test runtime and extracts `outputBudget`, `missingLiveChromeCacheLeaf` and
`storageReceipts` with the existing top-level-function pattern. Only those
actual bodies run in the VM. There is no copied function projection, source-
hash golden, alternate source path or import/execution of the launcher module.

The20 protocol cases use inert filesystem/process callbacks and synthetic
receipt/identity operands. The final case uses only a fresh `mkdtemp` directory
and removes that directory in `finally`. When `UNIT_EVIDENCE` is supplied it
must be absolute; if unset, the owned directory is created beneath `os.tmpdir()`.
No existing directory is removed or used as a fixture cleanup target.

These tests do not start an application/browser/DB/process, query `/proc`, send
signals, or qualify a genuine publisher/browser/native acceptance run. Caps,
negative cases and all original public assertions remain strict.
