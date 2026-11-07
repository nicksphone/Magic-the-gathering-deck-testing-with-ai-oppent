# Current Master Complex Core BO3

The Python gameplay source is `15aa3c77`. These are core engine matches, not
browser, human-controller, sideboarding or expert-play certificates.

Both players used the unchanged default Master policy and its 128-unit shared
combat allowance. The app's complete 60-card Drain and Tribal mains, empty
sideboards, declared matchup profiles and root seed `2026110517` were retained.
No learned checkpoint, lower-allowance override or native Forge engine was used.

## Completed Outcomes

| Deck Order | Natural Result | Checked Committed Actions | CPU / Wall Seconds |
| --- | --- | --- | --- |
| Drain / Tribal | Tribal 2-0 | 307 + 660 = 967 | 311.99 / 313.96 |
| Tribal / Drain, longer-limit qualification | Tribal 2-1 | 266 + 625 + 399 = 1,290 | 618.71 / 621.38 |

Across these two completed series, all five games finished naturally and all
2,257 committed actions passed the native checked-action path. Incoming hands,
ordered offers, proposed actions and outcomes were recorded in protected
evidence. A checked action is legal execution, not proof it was the best play.

## Preserved Resource-Capped Comparison

The first reversed-seat comparison retained the original 600-second series
allowance. It ended at 1-1 after 336 committed actions in game three, using
595.10 CPU seconds. Its result remains incomplete, not a draw, loss or completed
best-of-three.

Only after that actual terminal result, a separate reverse-only qualification
changed the operator allowance to 1,200 seconds. AI difficulty, search allowance,
game code, decks, seeds and policy were unchanged. The already completed forward
series was not rerun. The longer run matched all 1,227 available committed actions,
incoming ordered hands and ordered legal offers from the capped run. Its final
63 actions are a new suffix, not an invented match to missing baseline evidence.

The longer completion does not retroactively pass the original time limit or
establish a same-budget strength improvement. Source hashes and modes for all
4,333 qualification files matched before and after execution.

## Decision Time And Quality Limits

For the longer reverse series, completed `choose_action` intervals had a
nearest-rank p95 of 1.884 seconds and a maximum of 16.268 seconds. Overall CPU,
wall time and per-phase intervals are different measurements. These results do
not certify a UI latency target; slow choices remain an improvement area.

Narrow decision screens retained two floating-mana pass flags and one chump-block
flag for contextual review. A flag alone does not prove a bad move. Unavailable
historical bad-block aggregates remain unavailable, not zero. No tactical
optimality, general fairness or all-deck strategy claim follows from completion.

Generated hands and complete traces remain private, not public test fixtures.
The separately evaluated Forge bridge and its replay work are not the engine
used for these outcomes.

See [AI status](../../AI-STATUS.md), [the implemented search correction](post-denial-speculation.md)
and [the native integration boundary](forge-native-human-worker.md).
