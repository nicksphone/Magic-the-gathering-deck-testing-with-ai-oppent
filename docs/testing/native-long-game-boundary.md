# Native Long-Game Worker Boundary

This is an opt-in integration correction, not a live engine switch, trained
model, expert-play certificate or general save/BO3 qualification. It uses the
Forge Team/Card-Forge implementation and retains its upstream notices and GPL
license. The live Python AI and its weights are unchanged.

## Correction

The prototype worker previously failed on a native event after global turn 30,
even when the game remained legal and unfinished. Remove that arbitrary turn
cutoff. Bound journal growth instead: one synchronized counter admits at most
536870912 bytes (512 MiB) across that worker's journal streams, including each
row's newline. Check before writing and account only after successful I/O.
Exhaustion fails the worker; it never manufactures a win, draw or completion.

Strict UTF-8 encoding retains the former writer's rejection of malformed
UTF-16. An intermediate `String.getBytes` implementation silently substituted
invalid characters; review and new negative controls caught it before game
qualification. That intermediate candidate remains rejected.

The byte bound is not a global disk quota. Checkpoint/direct diagnostic files,
the owner's separate transcripts, and other sessions are not included. Existing
process ownership, sandbox, heap, CPU, frame, input, transcript, wall and idle
limits remain unchanged. No resource limit was raised during a game.

## Verification

The strict worker's six classes were independently rebuilt byte-for-byte and
composed with the unchanged seven-source/nine-class native-AI prefix. Explicit
profile schema 6 admits exactly that eight-source/fifteen-class composition;
prior profile schemas, launch validation and atomic publication are unchanged.

Separate cohorts passed:

- Seven whole native SDK classes: **85 tests**, zero failed/skipped/ignored,
  plus 59 configuration invocations. These include labelled controlled poses,
  internal counter-boundary fault injection, strict encoding and actual I/O
  failures. They are not natural games or a real 512 MiB journal stress test.
- Runtime-profile checks: **26 tests**, retaining the original 24 test bodies.
- Native transport checks: **65 tests plus 52 subtests**, including transcript
  exhaustion after processing starts and after a pending terminal result.
  Ownership, uncertain/processed answer receipts and process closure remain
  checked; no owner production code changed.

The SDK observed fourteen of fifteen overlay classes loaded. The later actual
game loaded all fifteen from the exact approved prefix; no class was forced to
load merely to satisfy a count. All source/class bytes and 59,971 pinned native
resource files matched the qualification's before/end checks.

## Actual Built-UI Game

A fresh built-UI Control/Ramp game reused the retained seed of the earlier
turn-31 failure. The automated human-side picker used actual offered choices
through rendered browser controls; it is not an expert policy or training label.
Human Ramp occupied registration index 1. Native Default AI played Control.

**Control won naturally at turn 35**, after **439 rendered UI answer submissions**
in **243.662 seconds**. Native final state and public outcome agree. All 439
starts and returns balance under the causal completion contract. This run did
not consume a replay reference and is not claimed as a reference replay.

The declared game/supervisor bounds were 900/1200 seconds. One earlier browser
attempt failed before any native session: Chromium paused the CORS preflight
through the same interception hook as the POST. A separate HTTP-only probe
reproduced that behavior. The corrected private helper continues only the exact
endpoint's genuine POST preflight unchanged, then inserts the exact decimal seed
into one start POST without changing any other payload bytes. Five synthetic
checks and an actual Chromium probe passed before the separate fresh game.
The failed attempt is preserved, not relabelled as gameplay.

Browser authorization, stale-input, reload and ordinary opponent-hand privacy
checks passed. No explicit hand-reveal episode occurred in this game, so it adds
no positive hand-reveal coverage. The supervisor exited 0; all 23 observed owned
processes ended, visible owned handles were absent, an actual external file-use
check was empty, and the closed local SQLite database passed integrity checking.
Unrelated process-visibility limits remain recorded. Generated hands, seed,
traces, screenshot and database evidence stay private on project artifact storage.

This is Chromium coverage, not separate vendor-Chrome, Brave or Firefox
qualification. One game proves neither strategic win rate nor whole-app adoption,
durable native cold saves, sideboarding or best-of-three acceptance.
