# Modal Fixture Binding

## Observed Baseline

Commit `ca08e0abe49ef86cdedf6386c87808ab79a38496`, hosted run `39373566949`,
job `118466567410`, completed the three whole fixture modules with 54 passes,
two ordinary failures, and zero errors/skips. Both fixed binding notices reported
`first_admitted=false` and `raw_lookup_calls=0`, in forward and reverse order.
This demonstrates the first genuine table losing its binding after a second
registration; no raw logs or individual parameter telemetry were needed.

## Candidate Scope

The fixture-only helper retains independent bindings per actual table and target.
The existing table/row identity and typed snapshot checks, canonical RAW reader,
and other fixture paths are unchanged. Non-string names return no RAW before key
lookup. Four new protocol cases cover `None`, a boolean, a list, and a mapping,
retaining input and no-RAW controls. No application or game-rule code changes.

The workflow appends that entire compatibility module to the unchanged six-case
binding, twelve-case fidelity, and thirty-eight-case row-protocol modules: four
whole modules, sixty prospective cases. Its existing pre-import SQL/network
audit, `-s` capture setting, limits, dependencies, and primary-status handling are
unchanged. This is Main import-only with the previously declared cache extras,
not startup or a universal process/native-denial certificate.

## Qualification Boundary

The sixty-case candidate is unexecuted at preparation time; hosted GREEN remains
pending. The observed baseline is a separate fifty-six-case RED, not qualification
of the new compatibility cases. The original full-CI namespace failure still
requires composed verification. This checkpoint does not close all fixture,
backend, browser, Phase 1, or release acceptance.
