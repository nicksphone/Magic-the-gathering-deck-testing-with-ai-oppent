# CI Runner Closeout Observations: Bounded Qualification

## Scope
This checkpoint adds bounded typed runner-closeout observations and strict optional-metadata validation. It preserves the selected runner exit priority and the existing workflow, budgets and private-input boundary. Observation availability is not test success, and an unknown status is not inferred to be zero.

## Actual Evidence
- Real Bash writer baseline: three tests, zero PASS and three ordinary missing-record assertion failures, zero errors/skips, unittest 2.763 seconds. The same three tests passed on the product.
- Product Bash writer gate: three PASS, zero failures/errors/skips, outer wall 2.902826 seconds (the duration comes from the terminal JSON, not an inferred unittest timing). It closed independently at 2026-10-20 00:49:37.586317 UTC.
- Separate five-whole-module gate: 111 PASS, zero failures/errors/skips, unittest 58.912 seconds; physical release at 2026-10-20 00:51:09.001215 UTC. Its modules were:
  - `test_backend_ci_closeout.py`
  - `test_backend_ci_privacy.py`
  - `test_ci_backend_closeout_metadata.py`
  - `test_ci_backend_metadata.py`
  - `test_ci_backend_shards.py`

The three real-Bash tests and the 111 tests were separate invocations. There was no coupled 114-case gate. Full source/runtime/system equality, finite-role checks, resource equality and scoped physical closure were recorded for both product invocations.

## Limits
The Bash tests use public synthetic sentinel programs to exercise the real runner. These are trusted source-specific functional roles, not a claim that parent audits are inherited by every child or that an OS sandbox was qualified. No protected game input or actual fixture output is published with this change. Full receipts remain outside the public tree.

The historical CI run 39334281279 reported pytest exit0 with 10114 PASS and ten skips, but its outer runner exit2 remains unexplained and unqualified. This checkpoint does not retroactively identify that cause or claim a new full hosted CI pass.

No gameplay, App, native-browser, AI-strength, Phase1 completion or release-candidate claim is made. The AST graph refresh is structural evidence only, with zero API-token use.
