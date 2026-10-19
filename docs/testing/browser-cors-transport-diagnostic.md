# Bounded CORS Transport Diagnostic

The held-POST cancellation at `5763e072` remains unexplained. This diagnostic
compares four native CDP interception configurations on the existing hosted
browser, backend and prebuilt development probe: Fetch disabled, the current
request-stage override, response-only interception, and dual static request/
response patterns without that override. It does not load the application UI.

Each case has one fresh fixture/page and one genuine cross-origin land-action
POST. A single two-second observation budget covers polling and canonical state
reads; unavailable reads remain unavailable. Only a native POST-200 pause can
be held, sampled and released once. There is no retry, fulfilled substitute,
proxy or sandbox change. Command/callback/target-closure failures remain failures.
An observed abort does not prove that no later mutation occurred.

Output is bounded `CORS_TRANSPORT_DIAGNOSTIC` metadata: finite enums, counts,
revisions and booleans. It does not print URLs, IDs, headers, bodies, hashes,
raw exceptions or private match content. This record is not an application PASS
banner or a new stage in the original 45-stage/501-banner declaration.

Only generic hosted CDP runs execute the comparison. Native vendor paths report
not-applicable and retain their existing prerequisites and entire original suite.
Unknown-vendor rejection is unchanged. A diagnostic failure is saved rather
than preventing the original suite from running: an original failure keeps its
own status; otherwise the saved diagnostic failure is returned at the end.

Protocol TDD passes 42 cases after a 35-pass/seven-failure baseline. Five whole
protocol/neighbor modules pass 167 cases. Twelve inert Bash controls execute
the actual hook/footer with an owned fake timeout command; they prove shell
status flow, not a physical browser timeout. The two-span inverse recovers the
complete original launcher, and all original scenario bodies remain unchanged.
Independent review finds no remaining scoped issue after the status-flow fix.

The corrected normal `npm run test:unit:native-browser` command subsequently
passes all 267 cases in 11 whole modules: the original 225 ordered identities
plus these 42 controls. Its source, executables and full release runtime remain
unchanged; recorded helper children close. Those are controlled unit/helper
processes, not a real browser, service, database or native capability probe.

No actual four-mode browser comparison has run at preparation. These protocol
results are not a transport fix, native-vendor acceptance or release completion.
Source/evidence is archived under
`diagnostics/ci/20261016-cors-deferred-hook-P2-PURE167-PREP-Jason-ppYopzxB/`.

## Actual Baseline And Closure Follow-Up

The exact `5e8a8509` and later `bf62c2b2` browser jobs each execute one baseline
case: the real action returns 200, the revision advances once, and the selected
land moves to the battlefield exactly once. Fetch disable and callback drain
succeed, but the page-closure observation fails. No precise closure failure
reason was captured. The remaining three modes are not reached, so these are
not completed four-mode comparisons or evidence of an interception fix.

The correction keeps the existing close call exactly once. Valid target-list
observations can wait for actual absence within one 15-second deadline starting
before that call, with at most 100 reads and 20-millisecond sleeps. Each request
receives only the remaining deadline. Failed HTTP, malformed lists, unavailable
identity, callback errors, permanent presence and budget exhaustion still fail.
New output fields contain only bounded closure reasons, HTTP status, counts,
presence and elapsed time; no target identity or raw error is added.

All 42 earlier controls remain unchanged. The corrected component passes 54
cases, and the actual unchanged normal native-browser unit command passes 279
cases across 11 whole modules, retaining all prior 267 identities plus the 12
new closure controls. Source and release-runtime inventories remain equal and
the recorded helper processes close. Independent review is clear. This remains
unit/protocol evidence: no physical browser was run for that local correction.

The separate original suite at `bf62c2b2` reaches 465 literal PASS console lines
before failing manual start recovery. Its third recovery POST returns 200 and
finishes; follow-up legal-moves and start requests are canceled. That trace does
not identify the cancellation cause, and the later closure correction is not
part of the failed job's source. The private bounded browser-log intake is
archived under `diagnostics/ci/bf62-browser-parent-terminal-20261016-9MOPWuCB/`;
the 279-case qualification is under
`diagnostics/ci/20261016-cors-close15s-normal279-QUALIFIED-Jason-TBY2gVQp/`.
