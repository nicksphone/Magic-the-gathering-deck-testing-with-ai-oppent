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
offers only `start-recovery` (the default), `ui-v2`, and `ui-v2-prefix`.
A closed shell case retains the default's original two literal program names and
the UI-only `browser-ui-v2.mjs`. The prefix case selects exactly
`browser-cors-transport-diagnostic.mjs`, `browser-driver-async.mjs`, then
`browser-ui-v2.mjs`, in that order. Unknown values exit 2 before launching the
browser runner.
Only schema 1 and the validated scenario enum are emitted in the scenario notice.
No request identifiers, paths, URLs, errors, or arbitrary input commands are added.

Both UI cases share the same reservation of the fixed fresh
`$RUNNER_TEMP/ui-v2-localization-evidence` directory, rejecting existing paths
and links, creating it with mode 0700, and exporting it as `MTG_UI_EVIDENCE`.
The default and unknown cases do not create this directory. No user-supplied
path or runner change is involved.

The existing 183-case Node step still runs from `frontend`, retaining its bounded
regular-file JUnit summary and primary exit status. After it passes, one fixed
Python step runs the entire existing localization workflow unittest module,
including its six default-shell mock conditions, then the separate new
four-case scenario protocol module. The latter uses inert Bash controls,
not actual browser, App, or SQL execution. No original tests are modified.

The browser launcher, 720-second outer TERM bound, 15-second kill grace, service
origins, sandbox setting, port checks, and primary-status ordering are unchanged.
The existing focused launcher retains its preliminary 30-second runtime proof and
generic 300-second outer process limit for each selected program. The ordinary
full suite instead uses 45 seconds for CORS, 30 for async readiness, and 180 for
UI. All in-program waits are unchanged. Focused mode stops at an earlier selected
program's nonzero exit; the full suite records the CORS diagnostic status and
continues to async readiness. A failed prefix must not be called a UI pass or
proof that UI ran. This is a bounded context experiment, not full-suite timer,
failure-policy, or browser-matrix equivalence. The four-case ASGI job remains
independent.

## Qualification Boundary

At test-first commit `159d64002dcf29ea89b46076208f9b036437e752`, automatic
run `39370701549`, job `118457690493`, passed the unchanged 183-case Node cohort.
The new prefix protocol method then emitted only schema 1, the closed scenario
`ui-v2-prefix`, runner exit 2, `argv_matches=false`, and
`evidence_exported=false`; its first exit-0 assertion failed ordinarily. Offline
and native browser steps were skipped. This proves the missing workflow branch,
not a browser or application failure.

The prefix implementation is unexecuted at preparation time. Only after the exact
revised head passes Node183 and the unchanged Python wiring modules (two old
methods and four scenario methods, separate cohorts) may the coordinator dispatch
one `ui-v2-prefix` diagnostic on that same head. A normal workflow-changing push
already triggers the default scenario; do not duplicate it with a manual
start-recovery dispatch.

This is complementary localization, not a replacement for full CI or proof of
the unresolved browser root cause. It claims no full browser matrix, AI game
matrix, Phase 1 completion, or release readiness. Permissions, event names, push
filters, other CI/native workflows, and application code are unchanged by this
workflow/doc proposal.
