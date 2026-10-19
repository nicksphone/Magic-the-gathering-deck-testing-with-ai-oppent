# Start-recovery signal enrollment: diagnostic-only HOLD

This change does not fix or explain ERR_ABORTED. It reuses the existing bounded
createRequestSignalObserver before the original Network/Page/Runtime setup and
reload, then passes that same observer via the existing requestSignals option
when each Fetch trace is registered. Actual owned-origin/default-context/frame
checks and finite registry/record limits remain unchanged. There are no new
protocol commands, request wrappers, network/CORS/App/client behavior, retries,
clocks or scenario assertions. The early callback carries passive observation
only, before Fetch interception is enabled; no native ACK/event is fabricated.

The new whole7 source-fragment/real-helper protocol tests produced3PASS4FAIL
on original a7 code, then7PASS with the minimal diagnostic wiring. The first
whole11/317 run was287PASS30FAIL:4 existing VM environments lacked the newly
imported observer dependencies and26 existing passive-CDP fixtures rejected the
administrative /home TMPDIR. That frozen epoch remains immutable HOLD.

The separately authorized dependency-only VM adaptation imports the actual
helper, supplies backend/process.env and an inert onIntercept fixture, with
all original assertions/test callbacks unchanged. A fresh owned /tmp namespace
addresses the old path mismatch without editing passive-CDP guards or tests.
The fresh same317 run is316PASS1FAIL, not a qualified whole-green component.
The remaining original private-output-symlink test fails in Node22's permission
layer before the product: fs.symlink requires full filesystem read/write
permissions. No permission broadening, guard change, assertion weakening,
filter, skip, extra retry or follow-up execution is included in this packet.

All11 declared whole files executed; source full metadata and Node binary bytes
matched before/end, native13-denial controls passed per process, and no SQL,
provider, project child or actual browser was used. These are cooperative pure
unit protocols, not actual-browser/root-cause/native security qualification.
No original browser scenario is replaced by this evidence. Future test-runner
permission compatibility requires a separate review/grant. This publication
document was authored after the gate outside the gated source tree.
