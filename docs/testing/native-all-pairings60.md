# Native All-Pairings 60-Game Composition

## Scope

On 2026-11-07, composed evidence accounts for 60 unique original native single
games, IDs `00` through `59`, with native exit 0 and zero native errors for each
completed game. This is completion evidence, not a strategic-strength benchmark.
The native rules, baseline AI and complete card programs are the work of the
Forge Team/Card-Forge contributors, under their GPL-3.0-or-later notices; see
[third-party attribution](../../THIRD-PARTY-NOTICES.md).

The six exact built-in deck recipes are Burn, Dimir Control, Midrange, Tempo,
Ramp and Tribal. All 15 unordered pairs have both seat orders under each fixed
seed, `2026110701` and `2026110702`: four games per pair, 30 games per seed and
20 participations per archetype. No case ID was replayed or substituted.

## Composition And Preserved Failures

This is **five bounded native cohorts, not one successful 60-game process**.
The original cohort terminal records remain unchanged:

| Native Cohort | Declared | Originally Certified | Runner Terminal |
| --- | ---: | ---: | --- |
| First-seed initial shard | 30 | 22 | Exit 2, launch-reserve `TimeoutError` |
| Second-seed initial shard | 30 | 22 | Exit 2, launch-reserve `TimeoutError` |
| First-seed tail | 8 | 8 | Exit 0 |
| Second-seed tail | 8 | 5 | Exit 2, `KeyboardInterrupt` |
| Fresh continuation, IDs `58`/`59` | 2 | 2 | Exit 0 |

Before the pause, 57 games were certified. Case `57` already had native exit 0
and complete output, but the interrupted adapter had not written its result.
The unchanged original adapter subsequently certified that output offline:
there was no new game execution. Cases `58` and `59`, previously not started,
were each launched once in the fresh continuation. Thus the composition is
57 prior certifications + one offline certification + two fresh games.
Neither timeout nor interruption is relabelled as a successful original run.

## Recorded Outcomes

These are observations from these exact decks and two seeds, not estimates of
archetype strength, policy improvement or causal effects of particular plays.

| Archetype | Observed Wins | Participations |
| --- | ---: | ---: |
| Burn | 7 | 20 |
| Dimir Control | 16 | 20 |
| Midrange | 8 | 20 |
| Tempo | 2 | 20 |
| Ramp | 11 | 20 |
| Tribal | 16 | 20 |

There were no draws. Recorded global turn counts range from 9 to 31. Execution
durations are not a source-matched performance comparison.

## Identity And Evidence

- Candidate content ID: `842989f447e0986ddc3eae0b884cc3979462051f8a63674ad034648f9b1c9a28`.
- Profile build ID: `919bdc1c845fd4b455c1d0fd8bcd8992dd8d8c0c852a547c1a1d5370e8a929e0`.
- Schema 11: 14 source files and 23 physical override classes. Observed class
  origins were checked; all 23 classes were not forced to load in every game.
- The 59 complete canonical card programs, declared inputs and 59,971 base
  resource files remained unchanged across the composed evidence.
- Operator-held records: `REPORT-COMPOSED60.md`, `COMPOSED60-RESULT.json` and
  `COMPOSITION-PINS.json`. Raw hands, frames and traces are not public fixtures.
- Result SHA-256: `83603466d1c8959ea748fe96dc9903a0519e41e9535cf0adba63c464a7ee24a4`.
- Composition-pins SHA-256: `7abccafd3df924fba377cab6296739b0174e02e6704688ca8cb7349a8d762241`.

The committed [native source package and profile prerequisites](../../tools/engine_evaluation/forge/native-ai/linked-pressure/README.md)
describe the candidate lineage. They are not a standalone reproduction command
for this operator-held five-cohort composition. The earlier
[six-pairing baseline](native-six-archetype-baseline.md) remains separate evidence.

## Limits

Complete recorded actor traces do not supply the initial root chooser decision
or a complete legal/affordable action set. Certified legal-opportunity metrics
remain **null, not zero**; a loss alone is not a tactical defect.

This composition does not establish expert strength, hidden-information fairness,
training or learned-policy quality, best-of-three/sideboarding, rendered human
UI acceptance, application adoption, or a live/default profile switch. It does
not complete the broader AI-quality work. Tactical review remains separate.
