# Source-Qualified Player Prevention

This is a bounded generic rules repair on immutable
`79e215fb4c39ccc49073c1a3963712608d25203c` plus the separately frozen 28-path
damage/life canonical-fixture candidate. It is not a full-backend, current
deployment, natural-game, or Phase 1 completion certificate.

## Behavior

The player-prevention matcher retains the optional opponent-source predicate.
Only qualified clauses consult source control. Unqualified clauses, effect
ordering, used-source filtering, numeric shields, nonpositive amounts and
unpreventable damage retain their existing paths.

Both discovery and application receive source ID, retained LKI, explicit
controller when available, and retained HAND context. The existing
`damage_source_control` resolver remains authoritative. Its active-player
fallback is not evidence for a qualified clause: absent/malformed control or
an unretained departed physical source does not manufacture an opponent.
Valid HAND context intentionally supplies no proven source controller;
malformed/conflicting HAND provenance retains the resolver's rejection.

The noncombat caller forwards its existing source LKI/context. In particular,
the existing spell-copy code already records the real copy controller in LKI
and transports it through pending choices and batch continuations; this repair
does not replace that with an ability controller or a physical owner's seat.
The combat caller supplies its actual source ID.

The legacy numeric-shield preflight now uses the existing readonly
`stack_engine._damage_replacement_source_context` projector and selected-to-root
HAND-context fallback. It does not change the veto, exception, recipient
selection, conditional-instruction selection, or `total > known` condition.
This keeps qualified discovery consistent before stack pop/event mutation.

## Qualification

- Same ten whole modules: eight originals, existing 46-case fidelity module,
  and new `test_qualified_player_prevention.py` (60 cases).
- Actual RED: 45 failed / 127 passed, 17.08 seconds. This includes the original
  strict Hekma pause failure; no original assertion was adapted.
- Same identities and new-test bytes GREEN: 172 passed, 15.37 seconds.
- Twelve separate whole neighboring modules: 237 passed, two dependency
  deprecation warnings, 65.58 seconds. No errors, skips or xfails.
- All 66 original functions / 274 assertion ASTs, actions/resources and frozen
  RAW bytes are retained. The earlier 1F/111P HOLD ledger remains immutable.

The new cases cover both defender seats, own/opponent controllers and foreign
ownership at actual query/application/combat boundaries; a delegating
before-helper full-RAW witness; query purity; departed/reentered activation LKI;
real paid Bolt/Twincast copy frames, original departure, JSON snapshots and
choice resumes; unknown/malformed/HAND controls; and legacy rejection before
pop with full-root purity. No manually appended copy frame is claimed as a
native cast. These are bounded rules fixtures, not natural game outcomes.

Runs used the parent's fresh locked 3,674-file/four-link HF runtime via direct
`bin/python -B` with inherited `PYTHONDONTWRITEBYTECODE=1`. The existing seven
precollection native SQLite/socket/child/provider canaries and guard function
bodies were unchanged. Successful phases recorded no unexpected denial, no
database, identical existing source/runtime bytes, equal FD sets, no children
and no non-main threads. No permission was broadened after a denial.

A separate neighbor preparation attempt collected zero tests: an overbroad
static import scan reached function-local `main` imports, left the module list
unwritten, and the launcher failed reading that list. Its exit/stderr are
preserved. The qualified neighbor phase used a fresh output after static
top-level import review; this is not a hidden test failure or a guard waiver.

## Limits

Typed internal retained provenance is not authentication of arbitrary stored
data. This does not expand the existing HAND control boundary, certify every
possible qualified Oracle form, or qualify every conditional/sequence producer.
The parent's future composed backend CI remains separate. No SQL, browser,
provider, NN, learning, schema or StackEngine change is included.
