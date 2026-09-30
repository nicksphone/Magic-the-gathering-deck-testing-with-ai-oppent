# AI projection performance and gameplay identities

Date: 2026-09-30 UTC. This is a bounded performance/repeatability milestone,
not expert-player, matchup-balance or arbitrary-card certification.

## Changes

`AIAgent.choose_action` owns a context-local projection memo for its immutable
root state and acting player. Known, empty and unknown pending-removal results
are cached only for that synchronous decision. Other players, simulated
branches and later decisions do not share the result. Nested calls and
exceptions restore the outer context; concurrent threads have separate scopes.

Planning copies retain all gameplay fields, choices and RNG but omit historical
diagnostic log entries. Speculative operations still record their own new logs.
The authoritative state and its history are not changed. Search horizons,
complexity limits and gameplay rules were not shortened for this optimization.

## Measurement

A dense removal fixture uses canonical Sprite Dragon and Go for the Throat
metadata. Its nine removal spells are a stress fixture, not a competitive deck.
Before other heavy jobs were started, seven iterations per mode measured:

| Mode | Median decision seconds | Root-stack settlements per decision |
| --- | ---: | ---: |
| Reference ablation | 0.249900 | 10 |
| Optimized | 0.176077 | 1 |

This is approximately 29.5% shorter on that fixture. Actions and reasoning were
identical and full authoritative snapshots were unchanged. The ablation
disables the decision memo and restores full agent planning copies while
retaining the already-existing history-free pending-stack projection path.
Timing is local, not a CI threshold or an end-to-end/worst-case latency promise.

```bash
cd backend
.venv/bin/python scripts/benchmark_ai_decisions.py \
  --snapshot /path/to/private-engine-snapshot.json \
  --player 1 --archetype Control --difficulty master --iterations 7 \
  --output training_runs/ai_decision_benchmark.json
```

Use a private engine snapshot, not a public card view. Snapshot input contains
hidden information: do not publish it. Output contains timing/equality metadata,
not hands or source snapshots. The command fails if decisions differ or the
authoritative snapshot changes. It imports the engine but does not start API
lifespan or write the gameplay database.

## Drift found during validation

An initial eight-game before/after comparison found a different surviving token
in Ramp/Tokens despite matching winner and turn count. Three runs on unchanged
`5db5dc2` code with seed 74 produced two normalized gameplay-log hashes:
`4722a94bbfc096cc22d96ba312089007ba48988ef307569dd97f3edc02b75399`
and `79d8475f579e3ed9f9545782740a213707e8fddf6f4fb46baecca5b548cd78a0`.
The first observed name-level divergence in the initial comparison was log
line 689: Soldier versus Token dying to lethal damage. It was not dismissed
as cosmetic and was not evidence of a changed AI win rate.

Gameplay object creation used random UUIDs independently of the seeded RNG.
AI tie-breaking sorts card/stack IDs, including equal-score block assignments,
so those random IDs could change which token survived. All production gameplay
creation paths now allocate from `MatchState.next_object_id`: tokens, spell and
ability stack objects, triggered/delayed abilities, stack copies and copied
permanent spells. Match/job operational IDs remain random. The sequence is
persisted with snapshots, shared across object kinds, and does not consume
shuffle RNG. Old snapshots without the cursor skip occupied card/stack IDs;
they cannot recreate the historical random identities of earlier executions.

Replay normalization no longer erases the new sequence identities, so a change
in target or blocker identity causes a first-divergence report even when names
and outcomes are equal. Legacy random UUIDs remain normalized. Replays created
before this change have different hashes and should not be compared as if they
used the same identity/normalization policy.

## Validation boundary

Tests cover seven AI archetypes, empty/unknown memo results, same-object changes
between decisions, returned-map isolation, nested exceptions, thread isolation,
history omission, RNG/choice retention, shared token/stack/copy identities,
snapshot/legacy restoration and identity-sensitive replay normalization.

The broader comparison uses the offline shipped built-in metadata, Master AI,
seeds 73 through 76, a 1,600-tick cap, and both seats for Dimir Control/Tempo,
Tokens/Ramp, Midrange/Drain Deck and Tribal/Burn. Optimization-disabled and
enabled executions use the same stable-ID policy. Repeated games are checks of
repeatability, not independent statistical samples. Concurrent matrix timings
are deliberately not used to claim speed improvements.

All eight complete game results, including identity-sensitive traces, match
between enabled and disabled optimization. No game reached the tick cap or
logged a cast-time cost/target rejection. Three separate Ramp/Tokens seed-74
executions all produced
`f1718a176f472355c1cc58cb2e6380e54668056f4a9a21d079511a9038c73c57`.
The compact [evidence summary](ai-projection-evidence.json) records the paired
seeds, turns, tick counts and hashes without full hands or logs.

The separate timeout-diagnostic interpreter crash remains unverified. Removing
repeated CPU work does not establish its root cause or fix it. Broad supported-
corpus semantics, full live/restart parity, strategic evaluation and long-session
soak remain unfinished in the root plan.
