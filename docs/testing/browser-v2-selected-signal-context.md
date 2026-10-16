# V2 Selected-Signal Context Observation

The V2 browser scenario now installs the existing bounded signal observer before
its original setup and reloads, enabling passive Page and Runtime notifications
inside the original cleanup protection. The later failure trace reuses that
observer instead of losing execution contexts learned before interception.
This changes test diagnostics, not App/API behavior, request signals, deadlines,
Fetch continuation ordering or scenario assertions.

The existing codec still requires an observed matching frame and same-origin
default execution context, exact scalar fields, at most 1,024 input bytes, and
16 records/contexts. Destroyed, cleared, duplicate, foreign or malformed contexts
do not acquire ownership. Snapshots copy records defensively. Signal observations
remain partial and are explicitly not joined to native Network request IDs.

Native request rows additionally retain finite `networkType` and `initiatorType`
categories. Native initiator request-ID links remain distinct from coincident
ordinals. An OPTIONS method, status 200 or acknowledged error-response pause does
not prove a native preflight, successful HTTP response or JavaScript signal abort.
Unknown categories remain bounded `other`/null values without raw data leakage.

On immutable `93630f38` plus this exact four-file component, meaningful focused
controls first report 43 passes and four failures, then all 47 pass. The full
frontend test command, production build and lint each exit 0. Its native unit
group passes 326 cases, Firefox group 170 and development-build group 27;
the original 309 native cases remain in order. The emitted development request
function exercises the existing opt-in branch using a protocol-only fetch.
Default production opt-in stays off and production build outputs are unchanged.
Source, dependencies, runtime and child/resource closure are preserved. An
independent static review finds no actionable issue in this bounded component.

The earlier exact `a75ce7cf` hosted browser job `117039078846` also succeeds:
45 ordered scenario headers and 501 literal PASS lines, all four transport modes,
one actual POST 200 and revision 0-to-1 transitions, plus drained callbacks and
closed targets. These lines are not 501 unique assertions. It uses the older
diagnostics: zero signal rows and unobserved context acceptance do not establish
an abort cause. This older success does not qualify new notification delivery.

The historical intermittent abort cause remains unknown. This patch is not a
production fix, genuine native-browser acceptance or evidence of Phase 1 closure.
Private execution, source pins, independent review and terminal-browser intake
remain archived under `diagnostics/ci/` on NFS; no private raw log is published.
