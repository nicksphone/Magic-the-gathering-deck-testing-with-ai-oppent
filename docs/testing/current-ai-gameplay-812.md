# Current AI Gameplay Review

Source: `812c91bcfc07ced851e127219425b9dfd74cbaeb`. These three fresh Python-engine
games are development diagnostics, not fitted training data or held-out acceptance.

| Deck Seats | Natural Outcome | Accepted Actions | Wall Seconds |
| --- | --- | --- | --- |
| Midrange / Blue Control | Blue Control won | 695 | 301.43 |
| Tribal / Tempo | Tribal won | 302 | 99.75 |
| Tempo / Tribal | Tempo won | 298 | 93.83 |

All 1,295 recorded actor frames and accepted actions replayed exactly. Native
SQL/network/subprocess guards reported no violations and the game collectors'
source hashes stayed equal. No winner was injected and no model was activated.
Both player hands and all raw decision traces remain protected evidence, not
public Git fixtures.

The new Midrange/Control run matches the previous incomplete 584-action prefix
exactly. It had a declared 600-second CPU budget instead of the old 300-second
bound, so completion is not a controlled whole-game speedup comparison. The
original censored result remains incomplete in its immutable archive.

## Decision Review

The old diagnostic script incorrectly passed one action at a time to
DecisionQualityAccumulator, whose row contract is a whole game's trace. The
corrected reviewer uses one complete game per call. A regression check on the
unchanged historical trace demonstrates the unavailable-versus-available
distinction; the production analytics implementation was not changed.

Available screens raised no missed-land, unused-floating-mana, repeated-stall,
screened-lethal, redundant-removal or validated-bad-block flags in these games.
All twelve player/metric combinations are available in each Tribal/Tempo game.
In Control/Midrange, eleven are available: one actual Control block's producer
returned an uncertain result. Its bad-block count is not certified zero even
though the full trace exists.

These narrow heuristics do not evaluate every target, bluff, card sequence,
partial attack or long-horizon plan. They are not expert labels, a matchup
balance result, BO3 qualification or a claim that the AI is complete.

## Learning Diagnostic

Two bounded, explicitly synthetic model-protocol checks each learned all sixteen
training rows and all eight opposed state-contrast pairs, including a variant
with irrelevant repeated context. No real game labels, sealed feature bodies or
private fitted checkpoints were read, and no resulting weights were retained
or activated. This shows the shared default trainer can learn those simple
conditional preferences; it does not repair the rejected real-card fits or
qualify gameplay generalization. Fresh, current-source learning admission remains
open rather than reheadering old training data.
