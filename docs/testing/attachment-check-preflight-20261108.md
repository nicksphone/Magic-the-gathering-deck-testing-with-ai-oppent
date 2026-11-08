# Attachment state-check preflight

The attachment state-check helper repeatedly classified the same battlefield
when no permanent required attachment work. A read-only preflight now shares
one rules-query scope. It returns only when every battlefield permanent has no
attachment target and is neither Aura, Equipment nor Fortification. When any
candidate exists, that scope closes before the original per-card mutation loop.
The fallback, departure ordering, replacement preflight and fresh queries remain
unchanged. Search policy, allowances, copy behavior and printed data are unchanged.

## Regression and captured-state evidence

The new whole module has 27 controls. Unchanged production reports four failures
and 23 passes: the both-seat sixteen- and thirty-one-permanent fixtures expose
quadratic classification. The candidate passes all 27 in 1.38 seconds. Its
thirty-one-permanent fixture reduces printed layer-four checks from 961 to 31
and preserves the complete pickled root/RNG. Other cases cover legal/invalid
attachments, unattached Auras, bestow, nonattachment detachment, replacement
failure atomicity and fresh classification after an earlier Aura departs.
Canonical fixture records retain their complete printed facts and source pins.
One explicitly abstract Fortification case tests structural detachment only.

On the actual captured turn-29 Control position, with 31 battlefield permanents
and no attachment candidate, one helper invocation reduces battlefield-scan
generator calls from 992 to 32 and layer-four calls from 124 to 94. The complete
root/RNG remains unchanged. A separately bounded fresh Master choice takes
19.54 seconds and matches the baseline's complete decision, action, fresh-agent
history and authoritative root/RNG. This is one timing witness; practical Master
latency remains open. Original whole-game agent history was not captured.

The candidate also reconstructs all 998 accepted actions of the retained partial
Control game exactly, reaching the same turn 33 with no winner. Reconstruction
calls no AI and starts no new natural game. All 2,695 bound backend inputs and
both retained input hashes match, no denied operations occur, and the supervised
worker closes normally. The existing game remains resource-limited and partial.

A separate post-change cProfile decision also matches those complete outputs,
fresh-agent history and root/RNG, with all 2,695 source files and three declared
input hashes unchanged and normal process closure. It takes 47.56 seconds under
instrumentation. Across this entire choice, layer-four scan-generator calls
fall from 5,803,456 to 4,795,845; attachment checks execute 1,072 times on both
sources. Total state copies remain 945, including 917 planning copies. Cumulative
profiler timings overlap and do not establish an uninstrumented speedup. The candidate evidence now contains two choices total: one uninstrumented
comparison and one allocation profile. Neither starts a natural game.

## Whole-module qualification

The declared nine-module cohort comprises the new preflight module plus Bestow,
BasicLand layer goldens, Aura departure preflight, equip context, Aura costs,
attached scaling, attached characteristics and static Aura control.

The first epoch records 309 passes and eight failures in 150.24 seconds. All
eight failures are audit-denied subprocess launches from the existing Aura
snapshot-roundtrip helper before its assertions run. Four declared BasicLand
children finish with pinned read-only startup guards; 16 observed SQL connections
use owned file targets, all 2,878 source/audit hashes match and the process group
closes normally. The failed epoch remains retained.

A second one-shot harness adds the exact existing Aura serializer script and
its sixteen owned before/after snapshot paths to the four BasicLand children.
The helper's existing explicit PYTHONPATH would omit the startup guard, so an
exact-script/path/environment wrapper adds only the pinned read-only guard to
that test subprocess environment. Original tests, assertions, arguments, stdin
and timeouts are unchanged. Four allow controls, nineteen rejection controls
and two wrapper controls pass without application calls or child launches.

The second epoch passes all **317 ordinary tests** in 160.21 seconds, with
70 existing deprecation warnings and no failures, errors or skips. JUnit's 317
ordinary testcase elements agree with the console result; no aggregate subtest
count is treated as a separate test. All 2,878 source/audit hashes and runner,
script and guard pins verify. Sixteen observed SQL connections use owned file
targets; none uses process-local memory. All four BasicLand and sixteen Aura
read-only children finish without denied operations and are absent afterward.
The supervisor exits zero, reaps its worker and verifies the process group is
absent, without a timeout, forced cleanup or leftover group.

Independent read-only review accepts the source, tests and bounded evidence
for commit/export with no source blocker. Parent verification compares the frozen backend/audit inputs with the working tree and checks the
captured choice, reconstruction, JUnit, connection targets and closure metadata
without executing more application work. Review additionally confirms the
recorded cleanup-helper hash and distinguishes sixteen connections from their
three distinct owned target files.

## Limits and retained evidence

ASGI cases use the previously declared 10ms test-loop timer for this sandbox's
self-pipe restriction. SQL evidence covers observed connection targets, including
process-local memory when used; it is not a general filesystem or SQLite ATTACH
fence. Source admission markers do not establish operator capacity ownership.
Dependencies are reused. These are component qualifications, not a clean install,
hosted whole-backend, browser, native Forge, strength or release certificate.

The original full Master matrix remains on its original frozen source and
limits; it is never restarted or transferred to this candidate. All original
release gates remain open. Private evidence is retained under
`/home/nick/mtg-rc-evidence-20261108/attachment-check-preflight/`, including RED,
failed and successful epochs, source pins, launch declarations and closure
receipts. Raw game, snapshot and agent bodies remain private.
