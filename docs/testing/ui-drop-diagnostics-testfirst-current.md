# UI Drop Diagnostic Localization

## Test-First Baseline

The test-only checkpoint `026644f4ead2ac1faf18855eef68e9dd7f245619`
retained production bytes from `2f7e7adb4553af8e8b934576ecb7e602e55778f3`.
Its automatic push run `39366304763`, attempt 1, reported nine whole Node
modules: 183 cases, 173 passes, ten ordinary failures, zero errors/skips, exit 1.
The public six-field summary does not identify individual failed test IDs.
Both required diagnostic exports were statically absent. The subsequent offline
SQL probe and native browser steps were skipped; the separate four-case ASGI
job succeeded. These observations are a diagnostic-feature RED, not an App
failure classification or product GREEN.

## Closed Scenario Selection

Pushes retain the existing CORS-plus-start-recovery selection. Manual dispatch
offers only `start-recovery` (the default) and `ui-v2`. A closed shell case selects
either the original two literal program names or the complete
`browser-ui-v2.mjs`; unknown values exit 2 before launching the browser runner.
Only schema 1 and the validated scenario enum are emitted in the scenario notice.
No request identifiers, paths, URLs, errors, or arbitrary input commands are added.

Only the `ui-v2` case reserves the fixed fresh
`$RUNNER_TEMP/ui-v2-localization-evidence` directory, rejecting existing paths
and links, creating it with mode 0700, and exporting it as `MTG_UI_EVIDENCE`.
The default and unknown cases do not create this directory. No user-supplied
path or runner change is involved.

The existing 183-case Node step still runs from `frontend`, retaining its bounded
regular-file JUnit summary and primary exit status. After it passes, one fixed
Python step runs the entire existing localization workflow unittest module,
including its six default-shell mock conditions, then the separate new
three-case scenario protocol module. The latter uses inert Bash controls,
not actual browser, App, or SQL execution. No original tests are modified.

The browser launcher, 720-second outer TERM bound, 15-second kill grace, service
origins, sandbox setting, port checks, and primary-status ordering are unchanged.
The existing focused launcher retains its preliminary runtime proof and generic
300-second selected-program limit; this is not an assertion of full-suite timer
or browser-matrix equivalence. The four-case ASGI job remains independent.

## Qualification Boundary

This workflow extension is unexecuted at preparation time. The actual 183-case
RED does not qualify a later product candidate. Only after the exact revised
head has an ordinary 183-case GREEN may the coordinator dispatch one `ui-v2`
diagnostic on that same head. A normal workflow-changing push already triggers
the default scenario; do not duplicate it with a manual start-recovery dispatch.

This is complementary localization, not a replacement for full CI or proof of
the unresolved browser root cause. It claims no full browser matrix, AI game
matrix, Phase 1 completion, or release readiness. Permissions, event names, push
filters, other CI/native workflows, and application code are unchanged by this
workflow/doc proposal.
