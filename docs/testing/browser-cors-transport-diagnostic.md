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
