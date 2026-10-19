# Bounded Fetch Observer Protocol

This isolated diagnostic patch uses source commit
`83a0f359fd3e05de27603ed7ce0fe10a44c7cff7`. It does not fix or reproduce a
native Brave failure, qualify another browser, or change application behavior.

## Actual Unit Evidence

The new eight deterministic protocol tests first produced eight expected
assertion failures with no fixture, guard, or reporter errors. Their frozen
SHA-256 is `f0166db343dc77d895126baafc85c955be6d1669b7190fb94a8168112f60a725`.

The final whole ten-module run on system Node v22.23.3 produced **287 PASS,
0 FAIL, 0 ERROR, 0 SKIP**, including all eight new cases and all 279 unchanged
existing cases. Source and system before/end metadata matched. The cooperative
mock guard reported no violations. Actual TAP is retained; there is no claim
of a separate test-phase ledger or JUnit report.

Earlier administrative discovery/reporter failures remain preserved separately.
The first implementation run was 286 PASS / 1 FAIL because the legacy UI
snapshot expected a Network-only event list. The implementation, not the old
test, was corrected. Subsequent complete runs were 287 PASS. No old test file,
assertion, injected promise, continuation argument, request filter, recovery
predicate, wait, or timeout was changed.

## Observation Contract

- Existing callbacks and native commands still run once per original call;
  errors and return values are forwarded unchanged, including repeated IDs.
- Local pause/command, owned-transport, child-session and enable-generation
  ordinals are bounded. They are not native wire command IDs or proof of the
  underlying target of an unjoined child session. Missing provenance stays
  unknown; a Network `Fetch` type never invents a native Fetch pause.
- The same 64 retained-event slots hold both existing and new observations.
  Existing Network/Page/Runtime observations retain priority over passive
  additions; evicted or excess observations increment omission counts. The
  first UI snapshot partitions those same slots into the legacy
  `browserMetadata.events` and `causal.events`, without a second event buffer.
- The 16-ID namespace, 16-pause and eight-command-per-pause limits are unchanged.
  Once association or generation limits are exceeded, correlation is unknown,
  never an invented association or authority to suppress an event.
- The first failure snapshot is frozen. `requestLifecycleFinal` contains only
  retained observations after its ordinal watermark, sampled after the existing
  bounded failure-only reads. This is a point-in-time snapshot, not callback,
  target, transport or browser closure proof; pending counts and omissions remain
  explicit. There are no additional remote reads, timers or waits.
- Native pause `resourceType` and stage are recorded independently of Network
  type. Raw IDs, URLs, request bodies, headers, credentials and native error
  messages are not added to the exported causal records. Firefox pattern
  validation and adapter behavior are unchanged.

## Trust And Limits

These are trusted in-process mock units, not native OS network isolation.
Node's permission model denies child/worker/addon privileges; a cooperative
preload rejects network/child primitives, while tests explicitly inject their
existing fakes. There is no browser, vendor, protected Python runtime, SQL,
service, provider, pipeline, game or lease execution qualification. The actual
Brave InvalidInterceptionId and ordinary Chromium ERR_ABORTED causes remain
unknown until separately authorized native evidence is captured.

The AST-only graph refresh occurs after test closure. Its generated files are
joined separately to the executed source map and are not retrospectively
claimed as the tested full tree.
