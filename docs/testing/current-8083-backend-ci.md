# Exact 8083 Backend CI Result

Hosted run `38804377544`, backend job `116661304016`, is terminal failure on
`8083a80e8c1b7c602a6c3537c095a6a3a6a98482`, completing on October 15, 2026.
The sanitized metadata accounts for 29,251 unique nodes: 29,001 passed calls,
168 failed calls and 82 setup skips. The skips are not executed passing bodies.
Its 87,671 phase records have no duplicates, missing phases, collection or
setup/teardown errors, or deselections. Separately, 111 subtests pass.

All 168 failures are in `test_startup_media_pins`: 159 report `ValueError` and
nine report `AssertionError`. This is not a passing whole backend run. Repair
requires checking the exact source-binding mismatch and retaining the
generator's closed input and mutation rejection, not bypassing its validator.

The retained 603-case cache/knowledge component is independently joined to
all 1,809 passing setup/call/teardown records. All 19 test-module hashes match
this exact published source, including the Task 1.2 protocol correction's 33
cases. That closes the component's hosted evidence gap without relabeling the
whole run or transferring its results to a later changed source.

Only the exact allowlisted backend metadata artifact was downloaded. Its ZIP
contained solely `backend-metadata.json`; no raw backend log or protected game
trace was retrieved. Private immutable metadata and reconciliation are under
`diagnostics/ci/hosted8083-backend-metadata-20261016-3vprkhl6/` in the project's
NFS archive. The independently verified receipt SHA-256 is
`51175b593fd7c89c6bcd54e7389aa437c16d6447148deed9aa0da5e49621646a`.

## Reviewed Source-Binding Correction

Only one of the generator's 12 public input pins is stale: hydration still
points to `a234c5ab...`, preceding the reviewed cache-rule correction. The exact
`8083` and current hydration input is
`8497ed903beccf72deba05bf5f03b5342c223cd98eb7c68bc86633f8b2455cce`.
The correction changes that single literal, not any validator, native I/O
body, test assertion or permission. Inverse substitution restores the entire
old generator byte-for-byte. There is no wildcard or alternate-hash allowance.

The original whole module first reproduces all 168 hosted failures, alongside
24 passes. After correction the unchanged module passes all 192 cases; the
two-whole-module neighbor declaration passes 193. Independent comparison
finds all 163 SVGs and all artifact fields identical except the manifest's
reviewed hydration source-pin entry. Hydration itself is checked and parsed,
not executed by this generator. These are bounded local results; a later
changed-source whole hosted pass remains separate.

The parent subsequently runs one integrated 22-whole-module declaration:
370 ordinary passes in 35.54 seconds, with no failures, errors or skips. It
retains this unchanged 192-case module alongside the canonical fixture and
transform regressions. Precollection physical SQL/socket/child/provider denials
remain active, source and runtime bytes are unchanged during the run, and no
database or lingering FD/thread/child remains. Generated placeholder SVGs are
explicit source additions, not silently described as a completely equal file
set or a fresh deployment-startup proof.
