# Complete Exile-Then-Return Audit

Tests-only on exact immutable published `55ebc8c6cba982300f85289bdbe3d114fa29b2e5`.
No current-parent/main/live reads or writes, production edits, or old-test edits.
Original lifecycle40 archive stays immutable. No 21db code-equivalence claim needed.

## Ordinary Ledger

Whole new module28: 8 PASS, 20 FAIL, 34 warnings, 10.04 seconds, exit1.
No skips, expected failures, exclusions, fabricated stack frames or injected events.

- Four complete-body compiler failures: both full canonical instructions compile
  to `exile` with a target ID only, dropping the mandatory return clause.
- Sixteen actual paid HTTP failures: two cards, two seats, normal/foreign owner
  initial boards, memory/file SQLite. Fertilid's real paid activation remains on
  stack; paid Cloudshift(1) or Flicker of Fate(2) responds. Both players pass;
  the source is exiled and never returned. Payment and retained-stack cold restore
  succeed before the first incorrect outcome. Reentry and later private search
  assertions are present but NOT qualified because this earlier failure stops them.
- Four absent-target negatives preserve the complete original root and costs.
- Four opposing private full-card identity permutations preserve actor input and
  moves byte-equivalently and leave the original root unchanged.

First attempt is separately preserved: 4 FAIL, 8 PASS, 16 setup errors, 3.60 seconds.
Only missing basetemp parent directory caused setup errors; the corrected run used
identical source/tests after creating the scratch parent. No engine failure claim
is derived from setup errors.

## Canonical And Ownership Boundaries

Cloudshift's full unchanged official raw response is reused from the earlier
verified intake. Flicker of Fate was fetched in full directly from the official
Scryfall named-card API before offline tests. Adjacent intake text and SHA256SUMS
record URLs, UTC timestamps and exact hashes. No Oracle shortening/replacement.

Cloudshift returns under the resolving controller's control. Flicker of Fate
returns under the card owner's control. The foreign-owner variant is explicitly
a lawful stolen-creature starting board, NOT proof of a natural control-changing
spell. The initial canonical Fertilid/counters board is likewise controlled setup.
Creature reentry needs two zone changes, fresh entry counters and summoning sickness;
the old paid activation must still belong to its original resolving controller.
These are desired assertions, not claims that broken current reentry passed.

HTTP uses TestClient against real endpoints and SQL repositories. File paused
stack snapshots reopen read-only in an independent process and state/controller
roundtrip; in-process application restoration is verified separately. This is
not a separately deployed HTTP server or an all-entry/replacement certificate.

## General Fix Proposal, Not Product

`oracle_effects.infer_effect_from_oracle` currently admits any `exile target`
substring and returns the single exile effect. `effects.handlers.exile_permanent`
correctly performs that one primitive; it has no retained-return executor.

Propose an anchored COMPLETE exile-then-return instruction matcher BEFORE the
broad exile fallback, no named-card gate. Emit a deliberate target plus explicit
return-controller policy (resolving-controller vs owner) to a separately owned
shared executor. Bind the actual exiled object and its new sequence, not a new
target inferred later. The same resolution must move that object once, respect
entry/replacement/counter/static/LBF/ETB sequencing and not conflate its old paid
activation with the fresh battlefield object. Unsupported extra clauses must not
silently compile to free exile-only reward. Any executor/continuation ownership
requires further coordination and approval; no ABI is invented as executable here.

Tokens, Auras, animation/type changes, multiple blink targets, delayed return,
replacement competition, and naturally acquired control are NOT qualified by
this bounded two-card creature audit. Ray of Command remains a separate unsupported
delayed-control family. Jason owns the independently assigned retained-activation
source-reference fix; its product is not consumed or reimplemented in these tests.
Animation/compiler writes are coordinated through parent pending exact Averroes ID.
