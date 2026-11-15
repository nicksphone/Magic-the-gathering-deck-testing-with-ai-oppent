# Opt-In Forge App Session

The Forge Team/Card-Forge supplies the native rules, card implementations and
Default AI. Our code owns the process/HTTP/UI bridge; it does not translate
native choices into Python game actions or claim authorship of the engine.
Retain the [third-party notices](../../THIRD-PARTY-NOTICES.md) and separately
licensed [native adapter sources](../../tools/engine_evaluation/README.md).

## Implementation Boundary

The existing application now contains an opt-in native table alongside the
unchanged default Python table. It accepts the two selected saved 60-card
mainboards and the selected human seat. Saved sideboards remain untouched but
are not exported or used: this slice is a single game, not best-of-three.
Decklists are open, and the opposing controller is Forge's Default native AI.

- The host validates the current offered tokens and selection bounds before
  writing an answer. A callback return is not interpreted as a successful cast.
- The browser renders only the actor-authorized projection, native stack and
  current choices. Native reveal permissions can legitimately disclose a card
  otherwise in a hidden zone; an ordinary opposing hand stays hidden.
- Native activation fences Python autoplay, manual actions and match starts.
  Native and Python handles use separate browser-storage namespaces.
- Browser reload reconnects to the same running host session. This is not cold
  application recovery after a backend restart.
- A client-generated capability stays in private browser storage and protected
  HTTP headers, never URLs, responses or public test artifacts. Start and answer
  idempotency prevent a repeated request from creating or submitting twice.
- Process count, frame size, transcript, idle time and wall time are bounded.
  Explicit close and application shutdown reap owned workers and close pipes.

## Operator Setup

This is not a bundled Forge distribution or an automatic installer. With no
configuration, `/forge/status` reports `available: false`, and the existing
Python game remains available. No request downloads or builds an engine.

An operator must build/pin the native worker and its Forge dependencies using
the [adapter build instructions](../../tools/engine_evaluation/README.md), then
set `MTG_FORGE_RUNTIME_CONFIG` to a private local JSON file:

```json
{
  "argv": ["/absolute/operator/forge-worker-wrapper", "{session}"],
  "cwd": "/absolute/operator/forge-runtime",
  "sessions_dir": "/absolute/local/private-native-sessions",
  "build_id": "<64 lowercase hexadecimal build-identity characters>"
}
```

These are trusted operator settings, not browser inputs. The wrapper must
launch the actual qualified worker with the session directory argument, the
correct pinned classpath and the intended OS sandbox. The host does not create
an OS sandbox merely by executing a configured command. The qualified local
runtime uses process, network and filesystem isolation separately from the app.
Use local owner-only storage, not an NFS SQLite/runtime directory; create an
existing sessions directory with mode `0700`, or provide its existing parent.
Generated native journals can contain hands and RNG data and must remain private.

Once configured, select the decks and human seat, choose **Open native table**,
then **Start native single game**. Only actual offered native controls submit
answers. Closing the native session is explicit; it is not an automatic reaction
to a browser reload or a failed read.

## Qualification Status

Current component checks pass 63 process-owner tests and 12 isolated router
tests. The 35 frontend native-session regressions are included in the default
`npm test` command; the full frontend pipeline passes 1,031 TAP cases plus its
custom assertion scripts, and lint/build pass. Transport mocks and protocol
fixtures are labelled synthetic; none of those counts is a count of games.

Review reproduced two UI recovery bugs: a definitively stale answer could keep
the still-current question disabled, and a definitively rejected start could
retain a dead intent. Eight new regressions cover the narrow corrections while
unknown delivery stays fenced and no answer is automatically resent.

Real process testing also found a Linux parent-death lifetime defect. The
sandbox's child could die with a transient request thread while the backend
process remained alive. Process creation now happens in the session's existing
reader thread, which stays alive through reaping. The exact sandbox-prefix
control survives caller-thread exit, processes an answer and closes cleanly;
the sandbox flags are unchanged. Four new owner regressions cover lifetime,
launch failure and delayed/prelaunch close. Of the original 59 test functions,
58 remain identical; the reader-start failure test now correctly requires zero
child launches instead of assuming a child must be created before thread start.

The process-owner, router and frontend component checks are separate from a
completed real browser game. The first browser attempt stopped before native
startup because Chromium's temporary socket path was too long. A fresh attempt
then reached 145 actual rendered-control answers, with same-session reload and
authorization/idempotency checks, but stopped at an overstrict reveal audit:
native Cultivate legitimately revealed a land in the opponent's hand. Neither
attempt is a completed game or an AI-strength result. Their original failure
evidence remains private and unchanged.

A later attempt stopped after 123 UI submissions because the test driver
incorrectly treated every stale-version rejection as fatal. Another reached
22 accepted answers but reported `native_exit_failed`. The latter's screenshot
retains the actual reason, but its exact child exit code and an exclusive causal
trace were not captured; the separate process-lifetime proof is not retroactive
attribution. These failures remain failed app qualifications. The corrected
driver requires an explicit `stale_question` response, then rereads and makes a
fresh rendered-control choice; all other unexpected answer errors still fail.

### Completed Built-UI Game

On the corrected source, the actual built application completed one fresh
Control/Ramp single game in Linux Chromium, with the human in seat 0. Ramp won
naturally on turn 20. All 433 accepted human-controller answers came from
physical CDP clicks on rendered native controls: one start request, 433 native
starts and 433 matching returns, one genuine native final result, exit zero,
and the same outcome visibly rendered in the app. No winner, hand, native rule,
AI policy or game budget was forced. Wall time was 225.84 seconds within the
original 240-second game bound. The automated human-side picker is not expert
play or a training label.

Reload after two answers retained the same session, actor and pending question.
Wrong-capability reads/writes returned 404, an intentional stale answer returned
409, and an exact duplicate returned its existing receipt; all four checks left
the public native root unchanged. The successful game had no incidental stale
answer rejections, so the recovery regression tests, not that game, support the
stale-same-question fix.

The browser audit checked 2,600 native response bodies and 3,099 snapshots,
including helper reads. No body retrieval was suppressed during reload, and no
legacy action/autoplay POST occurred while native play was active. Ordinary
opposing-hand observations remained opaque. Four browser observations of one
real temporary reveal matched the bounded native reveal/acknowledgement episode;
its acknowledgement completed and permissions closed. Earlier native complete
evidence and labelled synthetic extra-card, wrong-owner, missing-callback,
unbounded-episode and post-revocation negatives separately exercise the audit.

All 16 app-gate source pins matched before/end and the current files. The actual
runtime classpath/build identity matched the prior qualified native build; all
33 expected owned adapter resources were post-checked and 31 actually loaded
origins verified. This gate did not capture a separate pre-game resource-hash
vector. All observed app/browser/native processes ended; the closed local DB
passed integrity checking, had no remaining journal files and had an empty
external fuser check. Private traces, screenshots and the complete earlier
failure ledgers remain archived privately, not public test fixtures.

This is one genuine built-app single game, not full browser-family support,
both-seat app coverage, strategic strength or RC completion. The live app was
not changed.

## Remaining Work

Broader choice/callback coverage, durable application save/restore, native BO3
and sideboarding, card art and interaction polish, practical packaging, both-seat
and broader-deck browser games, native-AI hidden-information review and measured
strategy quality remain open. The existing native cold-choice experiment is
separate from this app slice. Nothing here switches the live service, certifies
all cards or establishes RC readiness.
