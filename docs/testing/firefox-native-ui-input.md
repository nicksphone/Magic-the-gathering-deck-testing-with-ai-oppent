# Firefox Native UI Input Component

The generic driver exposes `uiInput` only for an explicitly configured Firefox
page. It provides `pressKey('Enter' | 'Escape' | 'Tab')` and `clickAt({x, y})`.
A Firefox binding missing either method fails initialization and closes its
owned page; it cannot fall through to Chromium. Raw CDP `Input.dispatch*`
commands remain unsupported on Firefox.

The v2, direct-combat and redesign programs explicitly use these gestures when
available. Their original Chromium command blocks, coordinate calculations,
assertions and deadlines are retained. Required fake-driver fixtures gain the
new interface without removing existing assertions.

## Native Contract

Each gesture awaits a genuine BiDi `input.performActions` reply. Main Enter,
Escape and Tab use key-down/up pairs with `E006`, `E00C` and `E004`. A primary
click contains viewport positioning followed by button-zero down/up; finite
fractional CSS coordinates are forwarded without rounding or clamping. Unknown
keys, extra options and invalid coordinate shapes are rejected before sending.
The bounded input queue is page-owned, serialized and retains native failures.

This is an explicit gesture interface, not arbitrary CDP-event equivalence.
Direct combat intentionally gains a Firefox positioning move. Native Enter
activation does not reproduce independently specified CDP text/code overrides;
Firefox determines native click detail rather than accepting a forced count.
The [Mozilla action implementation](https://raw.githubusercontent.com/mozilla-firefox/firefox/main/remote/shared/webdriver/Actions.sys.mjs)
and [key definitions](https://raw.githubusercontent.com/mozilla-firefox/firefox/main/remote/shared/webdriver/KeyData.sys.mjs)
inform this mapping, but main-source documentation is not runtime proof for
the guarded Firefox 158 build.

## Cleanup Correction

Every admitted gesture keeps its original admission-based 15-second deadline.
Close joins the admitted queue, then starts one shared 15-second native-cleanup
window. Consequently, close can take approximately 30 seconds if called while
input is pending; this is not an unchanged aggregate close deadline. UI and
external limits are not increased, and an outer limit can still preempt cleanup.
There are no retries, fabricated acknowledgements or repair gestures.

The first 119-pass component had a review finding: starting cleanup's clock
before draining input could exhaust it before context closure. The corrected
regressions advance both timers and monotonic time, require the actual close
command and acknowledgement, and retain both errors if cleanup also fails.
The earlier ledger remains historical, not acceptance of that defect.

The final two-module declaration passes 121 cases: 89 transport and 32 driver.
It preserves the preceding 94 cases and independently passes review on frozen
source. The parent's complete frontend test, build and lint also exit zero,
with all eight source/test hashes unchanged before and after. These are
inert-wire/code-level controls, not native-browser execution.
Full Firefox application, launcher, child/profile, mobile/media and ancestry
requirements remain open; this component does not complete Phase 1 or release.
