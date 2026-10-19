# Shared toxic damage correction over frozen canonical stage

Base is immutable `4f86df95dfe8e4ebb60f41e1a8229ee633c7d009` plus the frozen
six-path canonical stage `34b3e174e1e9c1876d7da895bb753243e8b8d7d1a5bfee46c3a390b417a7629e`.
That old stage, its 91 cases and all historical evidence remain unchanged.

## Cause and narrow production seam

`rules_engine/damage_results.py` preimage SHA256:
`0d3d2d8693ea1b27888e2cc39542026e20a0985b89275446fcde0698273f9df5`.
The old player-damage resolver sums every numeric toxic mention in the entire
Oracle text. Full canonical Skrelv has one self-toxic clause plus a different
ability granting toxic to another creature; the old sum incorrectly gives two.

Toxic is absent from `_infer_keywords`, so consulting `has_keyword` alone cannot
recover the printed number. The correction recognizes only complete standalone
numeric toxic clauses after existing reminder-text removal. It supplements a
private copy of existing effective keyword counts, without duplicating printed
instances already represented in the card's base keyword list. Existing
`printed_abilities_suppressed` controls whether printed instances contribute;
resolved numeric grants retain existing effective-count/timestamp semantics.

Only this production file changes: imports, one small numeric helper, and the
old whole-text sum's call site. Infect, combat/noncombat gating, player damage,
counter replacement dispatch and source-LKI/context admission remain unchanged.
No named-card branch, Oracle mutation, Factory/state/continuous-layer change,
new cache, weights or resource policy.

The current combat caller uses a live source. Noncombat callers already supply
native source LKI/context and do not award toxic. Real battlefield departure
captures LKI in the new controls; no delayed-combat LKI transport is added or
claimed. Static numeric-grant parsing and every possible toxic interaction are
not certified. Repeated grants below use the genuine resolution-level
`grant_keyword`/`temporary_ability_loss` handlers, not a claim that Skrelv's
complete activated ability parser or any new spell route is qualified.

## TDD and preserved full cohort

Four whole modules, same pre-import five-canary SQL/socket/child/provider deny
guard, 900-second TERM plus 15-second KILL bound; no HTTP/browser/native/SQL.
The qualified FRESH interpreter/runtime is unchanged before/end.

- RED: **95 PASS / 18 FAIL, 11.41s**, unchanged production. Two inherited strict
  failures plus 16 new toxic failures. Both Delver characterization cases pass.
- Corrected: **112 PASS / 1 FAIL, 11.16s**. All inherited 91 cases retained;
  all 22 new cases pass. The original full-Skrelv toxic assertion now passes.

New outcomes cover both seats, one/three actual combat damage, ordinary
noncombat damage, genuine departure-captured noncombat LKI, ability suppression,
repeated numeric instances, grant/loss ordering, unmutated scoped query results,
and canonical Delver front restoration. No injected counter/event, skip, xfail,
test filter, changed old assertion or resource operand.

## Delver: representation assumption, not observed back-face retention

Factory applies the front, then deliberately restores the optional original
selector `None` into the card and printed-restoration record. The old manual
constructor had no such record; its first transform captured front selector `0`.
The canonical materializer preserves Factory's actual record, and bounce plus
snapshot consequently restores `None`.

Both seats prove the restored name, complete Oracle, mana, type, power/toughness
and face roster are the real front. Existing `select_cast_face(card)` maps the
omitted selector to front index `0`. There is no observed physical DFC reset
failure in this trace. The inherited assertion demanding literal `0` remains
unchanged and failing. No Factory/state edit or test adaptation is made; a parent
decision is required before touching that protected assertion.

**Combined component remains HOLD (112P/1F), not wholly green.** This increment
does not close global Task1.3 or certify all toxic/grant/LKI semantics.
