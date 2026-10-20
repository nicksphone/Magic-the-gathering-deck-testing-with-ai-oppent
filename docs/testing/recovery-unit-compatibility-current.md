# Recovery Unit Compatibility Checkpoint

## Scope

This test-only compatibility candidate is based on
`1ac1ef219fd4f192aed39ef9957c3d353a3fe81f`. It does not change browser
production code, package scripts, dependencies, permissions, or browser bounds.

Two curated-script expectations append paths already registered in the package
scripts. The legacy recovery diagnostic fixture binds the actual current phase
reporter separately from the original legacy sink. Its original 14 test names
and 54 assertion-bearing lines are preserved, with two additional inverse-source
negative controls. Real failure scenarios still execute the current program;
the inverse source is used only by the existing preservation check.

The localization workflow adds one fixed protocol step after dependency
installation and before browser operations. Its static roster is 47 cases:
the complete legacy diagnostic module (16), phase diagnostic module (10), and
public storage-owner budget module (21). The bounded regular-file JUnit summary
emits only schema, case count, runner exit, failure count, error count, and skip
count. The original Node exit remains primary; an invalid report fails closed
when Node otherwise succeeds. No arbitrary workflow inputs are introduced.

## Evidence And Limits

On the base head, hosted frontend build and lint passed. The failing
`test:unit:native-browser` command reported 456 cases: 450 passed and six ordinary
assertion failures. This is not the total of all frontend unit commands. Earlier
commands passed, but the chain stopped before the Firefox command, so the
portable 21-case unset-temporary-directory fallback was not executed there.

The full CI reference job had two ordinary metadata-selftest failures, preventing
backend collection; backend workers were skipped. The two focused localization
jobs passed at the base head, within their separate declared scopes.

These compatibility posts and the new 47-case workflow step are **unexecuted**.
Earlier component passes do not qualify this new combined roster. The full UI
V2 failure remains unexplained: a deadline line is an unverified source hint;
zero response/drop observations and canonical revision zero do not establish
whether request-stage activity occurred. A bootstrap line-one cleanup fallback
does not establish an actual bootstrap fault.

This checkpoint claims no browser root-cause fix, full browser matrix, Firefox
50-case qualification, AI 110-game result, Phase 1 completion, or release readiness.
