# Joint Retained Opening Hands

Only the required `mulligan_bottom` and `opening_hand_exile` selections use the
joint helper. It enumerates at most35 removal subsets from a seven-card hand,
restricted to actual offered IDs. Whole retained hands are compared using the
existing opening profile: critical misses, color access, preferred land window,
quality, then existing retention value. Exact ties retain legacy value/ID order.
The inputs, zones, opponent private cards and both RNG states are not modified.

Known own battlefield lands join the profile because a free opening permanent
has already entered before an exile instruction. Full canonical Caverns controls
include its actual public luck counter; no fictitious seventh hand card or mana
resource is added. This remains the existing approximate opening-hand heuristic,
not a general mana/payment planner, nonland-accelerator forecast, or optimality
certificate. Nonstandard hands larger than seven retain the legacy fallback.

Global retention prices, cleanup/discard, sacrifice, search, combat and opening
keep/mulligan policy are unchanged. Pregame learned-ranking bypass is unchanged.
Canonical component tests use controlled public poses, not live-game replays,
trained-model calls or claims about eventual wins. After the native batch closed,
18 whole pure AI/pregame modules passed: 490 tests and 13 subtests. The guard
reported no SQL, socket, subprocess or trained-payload accesses. Mixed HTTP
opening-hand modules were not included, so this is not an API or game-strength
certificate. This AI edit creates another engine contract;
the immutable2ea snapshot and old model/proofs are not retagged or reheadered.
