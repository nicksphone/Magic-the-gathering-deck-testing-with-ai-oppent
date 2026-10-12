# Terminal Draw Utility And Combat Allocation

This increment is over public `3a7db1e241034752bfd87ed14a22d445b4675986`.
Only `backend/ai/agent.py` changes in production. No rules, policy weights,
search depths, hidden-information access, existing tests or dependencies change.

## Behavior

A shared terminal utility treats an actual draw (`winner == 0`) as neutral,
rather than a loss, in strategic evaluation, attack search and both rollout
paths. Existing win/loss magnitudes, nonterminal evaluation and attack tie-breaks
remain unchanged.

For the attacking source's own damage choice, a stable effective-indestructible
sort puts destructible blockers first. The original threat order remains within
each group; the foreign-chooser branch is unchanged. Toughness, marked damage,
prior assignments, deathtouch and trample lethal-assignment rules remain intact.
Indestructibility does not exempt a blocker from lethal assignment for trample.

## Observed Qualification

- The initial twelve new cases reproduced ten failures and two passes (2.05s).
  The same twelve then passed (2.07s).
- An independent parent run of both complete new modules passed all 36 cases
  in 5.32s, with precollection SQL/socket/process/provider denial and no unexpected
  denial. Source hashes were unchanged before and after.
- The three unchanged whole HTTP/combat neighbor modules passed all 86 cases in
  47.39s, with 70 warnings and no failures, errors, skips or selection filters.
  The isolated source/input manifest remained equal. Database owners, connections,
  workers, jobs, threads and socket endpoints closed; actual database fuser output
  was empty after the command completed.

An earlier strict-I/O nine-module run recorded 213 passes, two failures and two
setup errors: ASGI socket selfpipe operations were denied. An unchanged baseline
independently reproduced that guard incompatibility. These ledgers are preserved;
the subsequent 86-case cohort is separate and is not a claimed 217-case rerun.

## Evidence Boundaries

Full canonical Crypt Rats and paid Bolt actions establish actual draw/loss/win
outcomes for both seats. Damage allocation uses checked attacks and blocks,
an offered choice, production AI allocation and actual resolution. The new
allocation kills the destructible Bears instead of wasting all damage on the
indestructible Sentinel; the Sentinel survives and the attacker dies.

Old-board creatures, mana and keyword/counter setups are declared fixtures, not
paid acquisition certificates. The attack-ranking check injects genuinely
resolved endpoints at the projection boundary: it proves utility/ranking, not
a complete natural attack continuation or overall AI strength.

Fixtures contain public canonical API bodies/provenance and pinned public-source
comparison methods. Private game traces, databases, runtime harnesses and hosted
raw logs are not published. Verified private evidence is under RCHFiles
`diagnostics/ci/current-3a7-ai-draw-allocation-public-20261012-qhnIuC2R/`.

Complete configured CI passes on the preceding `3a7db1e2`, as documented in
[its checkpoint](current-3a7-complete-ci.md). The new increment requires its own
hosted qualification. Expert-AI benchmarks and original release gates stay open.
