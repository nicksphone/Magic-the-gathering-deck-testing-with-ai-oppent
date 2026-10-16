# Firefox Runtime Observer Protocol Slice

This is a private, mocked-protocol prerequisite for the original browser launcher,
not native Firefox or whole-launcher qualification. It does not grant execution.

## Source And Scope

The preimage is commit `79e215fb4c39ccc49073c1a3963712608d25203c`, with transport
SHA-256 `7742d365e0d3cd67399d20e5b23b0a6e7670c64193f2c0682526e80e64237594`.
Only the transport, wire-name allowlist, an additive diagnostics branch, the new
runtime-observer protocol test, and this document change. Original scenario
files, assertions, deadlines, shared driver and accepted Fetch collector tests
remain unchanged. Parent owns graph refresh on integration.

The mandatory callers are `browser-ui-v2-costs.mjs` and
`browser-start-recovery.mjs`. Both await `Runtime.enable` without inspecting its
result. This implementation is their bounded realm-observation compatibility
operation, not a complete CDP Runtime domain. Passive CDP evidence remains
unavailable on Firefox.

## Native Registration And Observation

Empty-options, top-page `Runtime.enable` sends real `session.subscribe` for
`script.realmCreated` and `script.realmDestroyed`, scoped to the actual owned
top context. Only a matching native success with a nonempty subscription ID of
at most 256 characters establishes ownership and yields the actual result.
Concurrent callers join that registration. Repeated calls reuse the previously
acknowledged result; this is not a new native receipt. Registration errors are
latched, including timeouts: a late unknown reply cannot establish ownership.

Existing realms can be replayed before the subscription ACK. Routing is installed
before sending, with at most 64 live window-realm associations and 64 pending
event projections per page. Overflow or contradictory owned identity fails
closed rather than silently evicting routing identity. Pending projections are
published in observed order after ACK. The ACK transition and buffer drain share
one success step so a following event cannot be stranded behind promise cleanup.

Only genuine window realms belonging to already owned contexts are correlated.
Workers, unknown context IDs and unknown destroyed realm IDs are not assigned to
the last page or to a guessed context. A destruction uses the saved native
realm/context association, including when context destruction arrived first.
No raw origin, sandbox name or arbitrary native payload is retained in the
projected event. Native parameters and derived correlation are separate fields.

Projected observations are explicitly branded `webdriver-bidi`, with genuine
`script.realmCreated`/`script.realmDestroyed` method names. They never fabricate
`Runtime.executionContextsCleared`, execution-context IDs or navigation events.
A later hook sees later real events, not a fabricated historical replay.

Failure diagnostics expose separate local realm/context ordinals and a top-level
boolean within the existing 64-event, 16-identity-per-map diagnostic limits.
Unknown/malformed diagnostic inputs do not throw into command handling. Success
does not publish a failure report. Diagnostic failures cannot replace original
command results, native errors or callback exceptions.

## Cleanup And Limits

Page close rejects while this registration is pending. The new subscription has
its own owner slot; matching unsubscribe ACK retires that exact ID and its
registry. Negative ACK retains ownership and propagates the error. A later
context-close failure does not cause explicit subsequent cleanup to remove an
already retired subscription. There is no automatic retry or deadline increase.
Existing Fetch collector cleanup and all other subscription paths are unchanged.

The wire observer records only allowlisted method names and existing safe scalar
metadata. A projection callback failure latches `observerFailed` without masking
the real command result. No native browser, OS isolation or runtime readiness is
proved by the synthetic wire fixture or its cooperative JavaScript I/O guard.

The normative design reference is W3C WebDriver BiDi `index.bs` at revision
`f922e6af669ead51496db85f37813f39438ef171`, sections `session.subscribe`,
`script.RealmInfo`, `script.realmCreated` and `script.realmDestroyed`. Specification
semantics do not establish implementation behavior of a particular Firefox run.

Viewport/mobile, reduced-motion media, native browser identity, full application
interception and the original full launcher remain separately unqualified.
The existing Target auto-attach HOLD and passive-CDP rejection are unchanged.

## Executed Protocol Checks

The29 new regression cases first produce2PASS/27FAIL, then29PASS. A strengthened
native-ACK ordering case separately produces28PASS/1FAIL before correction and
then29PASS. The private whole declaration passes194 cases, but exceeded its
declared180-case scope by14; that deviation is retained explicitly, not silently
reclassified as within the earlier authorization.

Following independent static review, the parent composition with navigation
metadata passes383 cases in nine whole Node modules. Both additive helper
branches have exact inverse proofs. The normal `test:unit:firefox` command now
includes this module alongside all three original operands and passes170 cases;
the complete frontend test command, build and lint pass as well. The locked
runtime's3674 files, four links and429 directories remain unchanged afterward.

These are ordinary mocked-protocol and driver checks, not a real Firefox run,
an OS-isolation proof or permission to remove the remaining capability HOLDs.
