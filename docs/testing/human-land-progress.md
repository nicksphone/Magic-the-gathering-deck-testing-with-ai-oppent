# Human Land Plays and Explicit Progression

## Reproduced boundary

The saved human position with an available Mountain produces a legal land move,
and a Chromium pointer click reaches its enabled control. That probe captures
the real state through GET requests, intercepts all browser fetch writes and
does not modify the user's game. A second saved position already has its land
drop used: two Mountains in hand do not permit another drop that turn.

The actual progression defect is separate: **Next Step** previously called
autoplay. Autoplay correctly pauses at human decision windows, including a legal
land drop, so this explicit button could return without passing or advancing.
The before-fix browser probe records that autoplay request. After the fix it
records a seat-correct `pass_priority` action instead.

## Current behavior

- Next Step explicitly passes human priority. AI seats still execute one AI tick.
  Both players must pass to advance, and stack objects resolve before progression;
  no phase or response window is forcibly bypassed.
- Required choices and human pregame decisions disable the progression control
  until an appropriate legal pass exists. Choosing Next Step can voluntarily skip
  a land opportunity; automatic progression still pauses rather than making that
  decision for the human.
- Unavailable lands explain main-phase timing, turn/priority ownership, pending
  choices, stack occupancy or exhausted allowance, rather than saying "not castable."
- Public player views expose a nonnegative `land_plays_remaining`, derived from
  the same maximum and turn-stamped counters used by land legality. Old responses
  without the field retain a conservative generic explanation. The UI never
  invents a legal land action from this number.

## Checks

162 isolated backend checks pass, including both-seat allowance/drop/restart,
stale previous-turn counters, recorded-counter drift, serializer purity and a
unit-injected larger allowance. This last check tests arithmetic, not a new card
or certification of every extra-land effect. Existing land classification, view,
entry and API smoke regressions are included.

Frontend contracts reject negative, fractional, string or null allowances; unit
checks cover explicit timing/priority/choice hints and legacy payloads. Frontend
unit checks, hooks lint and the production build pass. The physical pointer probe
also verifies that the legal land button is not obscured or clipped.

The natural human BO3 browser flow now alternates Next Step and Pass Priority for
both human seats, retaining its authoritative revision and game-state checks.
The complete final-source browser harness passes, including natural human-vs-AI
and human-vs-human BO3, required choices, sideboarding, ambiguous writes and
backend restart recovery. The combined isolated backend suite passes 7,354 tests.

The first browser run exposed a test-driver race: asynchronous readiness
predicates were coerced to truthy Promises before completion. Persisted engine
state had the correct discard count. The shared driver now awaits predicates;
new tests cover delayed success, asynchronous false, rejection and synchronous
checks. The full rerun passes without weakening the discard assertion or changing
discard rules to accommodate a test race.

Raw probes, screenshots, both browser attempts and isolated backend checks are
preserved in the verified RCHFiles evidence archive linked from
[AI projection reuse](ai-destruction-reuse.md).

## Limits

Clearer controls do not make lands playable during draw, an opponent's turn or a
nonempty stack, and do not grant an extra land drop. Broader land permission,
replacement and older-wording coverage remains the rules roadmap. Scripted BO3
and the pointer probe are not a long-session, accessibility or LAN certificate.
