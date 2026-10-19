# Start Recovery Signal Enrollment

This correction is published `a7a08c4f` plus the four-path observer recipe.
It changes test instrumentation, not App requests, CORS, retry policy, timeouts
or scenario assertions. The existing bounded signal observer is attached before
Runtime enable and page reload, then retained by the later response trace.
Unknown origins, nondefault contexts and unjoined frames remain inadmissible.

## Actual Unit Qualification

One execution passes all 317 cases across 11 whole Node modules in 3.577 seconds,
with no failures, skips, cancellations or TODOs. All 143 pre-import denial
controls pass; unexpected admissions are empty. These are pure protocol/VM
and owned-file fixtures, not actual browser scenarios or gameplay assertions.

The original response-metadata VM fixture receives the newly imported observer
binding; its original assertions and scenario bodies remain unchanged. The
seven new lifecycle cases first produce three passes/four failures, then pass
after the observer wiring. Earlier whole-cohort failures remain archived:
missing VM binding, an administrative TMPDIR outside the driver's required
`/tmp` namespace, and Node's native symlink permission restriction.

The final run uses one explicit trusted role for the whole 31-case passive-CDP
module. Node requires full native filesystem permissions to create its genuine
owned symlink fixture. That process retains the unchanged cooperative preload
guard's owned-write checks and SQL/socket/child/worker/provider denials. This is
not hostile-code native filesystem isolation. The other ten programs retain
their original permission arguments; no driver permission check is weakened.

Source, Node binary and preload-guard hashes match before/after. All 22 known
launcher/Node PIDs end, and actual fuser checks on four owned paths return one
with empty streams. No database, project child or provider is admitted.

The verified NFS evidence is
`diagnostics/ci/start-signal-enrollment-a7-TRUSTED317-PASS-20261017-5rsiok08`.
All 4,171 archive members receive readback verification. The original four-path
patch SHA256 is
`8cc1e851745afd2ae767add50ae4c01118cad8863ad734272c42c9aef9f3184d`;
the VM-only adaptation remains separately available, not an assertion rewrite.

## Hosted Failures Still Open

Exact `fb775e1e` browser job `117310867840` times out in the first lost-start
response scenario. Its observer enrollment is too late to retain the context.
Exact `a7a08c4f` job `117320971076` instead fails while waiting for a held v2
action response. Its joined signal records report TypeError with the two
observed signals not aborted; no POST response is captured. Neither trace
establishes the underlying cause of the native `ERR_ABORTED` events.

Both completed browser-job logs were read only after checking their exact
published workflow has no browser/global protected-input binding. No raw backend
job log or private synthetic trace was fetched or published. Earlier hosted
successes remain source-specific, and this unit result is not a new hosted
browser run, native-vendor qualification, Phase 1 sign-off or RC acceptance.
