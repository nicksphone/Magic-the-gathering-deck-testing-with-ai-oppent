# Two CPU-limited games: evidence and options — 2026-11-17

This note changes no code, limits, seeds, plan or acceptance rule and authorizes
no execution. Both completed declarations retain their failures. Full evidence
and measurement scopes are in the [pilot and health results](archetype-v3-pilot-evidence-template-20261116.md).

| Observed game | Pair / physical seat | Last written progression | Waited CPU / cell wall | Trace / written actions |
| --- | --- | --- | --- | --- |
| v3 trace2 pilot 001, seed 2026112001 | Blue Control seat 2 vs Dimir Control seat 1 | Turn 44, upkeep | 1,199.922 / 1,205.364 s | 78,417,648 bytes / 1,282 |
| Health 032, seed 2026112101 | Drain Deck seat 1 vs Ramp seat 2 | Turn 26, postcombat main | 1,199.940 / 1,202.771 s | 25,597,276 bytes / 761 |

Both game children hit the unchanged **1,200-CPU-second** shared cell allowance
before any verification phase. Neither exhausted 1,500 wall seconds, 128 MiB
trace, 10,000 actions or 100 turns. They are distinct seeds/matchups/progression,
not a repeated deterministic turn-44 failure. Some verified health games finish
at turn 44: turn count alone does not predict CPU cost.

Their flushed prefixes are AI-inclusive-cost dominated: pilot 922.229 AI seconds
of 1,175.006 process CPU; health 947.867 of 1,050.373. That category includes
planning copies and engine simulations inside master AI, so it is not proof
that AI alone is buggy or that engine work is cheap. The health receipt covers
752 actions, while nine later written actions have no later CPU attribution.
The unrecorded interrupted operation remains unknown. Its last 20 visible
actions traverse nine turn-26 steps; a final priority pass does not demonstrate
a stuck loop. These facts suggest a **workload/budget limitation** worth making
explicit, not a demonstrated rules defect, divergence, infinite loop or AI-
strength finding. No new profiling or replay was run for this note.

## Options for a separate maintainer decision

| Option | Consequence and required pre-registration |
| --- | --- |
| Raise CPU allowance | Might permit expensive games but is not known to finish either one. Declare a new ID, source/runtime, shared game-plus-verification CPU **and wall** budgets, schedule, trace/storage bounds and campaign admission before execution. Raising CPU alone may merely move failure to wall or leave too little for verification. Retain all prior charges and obtain explicit budget/launch approval; no silent borrowing or retroactive pass. |
| Add/lower a turn cap | Bounds progression but does not directly bound AI cost: health already stopped at turn 26. Under unchanged zero resource-limit tolerance a turn-limit cell still **fails health**, not a draw or a solved timeout. Scoring it as a draw or changing tolerance would be a different acceptance policy, requiring explicit review and a fresh declaration before data. |
| Document the limitation | Preserve the failed zero-tolerance health result and report that master AI plus exact replay/parity cannot complete every tested cell inside 1,200 CPU seconds. Do not claim RC engine-health acceptance, strength or the statistical gate from 71 survivors. An RC disposition of that limitation is a maintainer decision, not supplied by this note. |

The evidence supports documenting the limitation now while deciding whether a
new budget experiment is worthwhile. A performance investigation or a suspected
engine/AI defect would need its own bounded scope, fidelity tests and approval;
no search-quality reduction, rules/AI edit, retry, resume or extra run is
proposed as an automatic response. Available registry seconds do not authorize
those actions. The original statistical gate remains unmet whichever option
is selected; the health run cannot be relabelled to replace it.
