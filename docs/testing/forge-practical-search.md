# Native Forge Search On Practical Decks

This isolated comparison uses the Forge Team/Card-Forge engine and existing
Flat Monte Carlo AI, revision `61e9442c433711a82258daca3236f936a1d6f70e`.
We did not write that engine, search implementation or card programs. The
original GPL license and notices remain in
[`tools/engine_evaluation/forge`](../../tools/engine_evaluation/forge).
Our original caller and tests carry explicit credits and GPL-3.0-or-later headers.

## Actual Completed Evidence

The app's unchanged 60-card Burn and White Weenie main decks were each run with
empty sideboards. These are not tournament deck claims or sideboarding tests.
Two development seeds were each run with both players' search off and on, in
four separate offline JVMs. Both arms use the Default profile, public deck lists,
filtered opening hands off, cheat shuffle off, MAX/LITE off and the scoped naming
controller. The app, native upstream originals and live matches were unchanged.

| Seed | Search Off | Search On |
| --- | --- | --- |
| `2026110501` | White Weenie wins 2-1; 13/19/12 turns | White Weenie wins 2-0; 17/12 turns |
| `2026110502` | Burn wins 2-1; 13/11/13 turns | White Weenie wins 2-0; 13/16 turns |

All four matches completed naturally within their independent 300-second bounds:
10 games, 3,157 actor-priority observations, native first-to-two terminal footers
and conserved inventories. No forced winners or timeout draws. The launcher
status is administrative only: independent verification required every case's
actual zero exit, terminal footer and game outcomes. Raw hand/game traces remain
protected, not public fixtures or the app's exact action-replay format.

Search-on recorded 51 decisions, 128 rollout attempts and 33 decisions made by
rollouts. Positive native sample traces confirm successful sampling, rather
than inferring it from an enable flag or attempts alone. Native statistics
reported zero rollout exceptions. One Lava Spike candidate failed revalidation
in one game; that comparison fell back to the heuristic. The largest per-game
decision-time p95 was 1,107.89 ms, measured under four concurrent JVMs. Default
450-ms decision budgets are not hard wall-clock guarantees; no causal timing
diagnosis or whole-app performance claim follows.

The search-mode test first passed the off case and failed the on case. After
wiring the switch, eight whole native classes passed **183 tests, zero failures
or skips**: the previous 181-case cohort plus the two configuration checks.
This is not the entire native or app suite. A first launch did not execute Java
because the owned wrapper lacked its execute bit; invoking that existing wrapper
through `bash` corrected only the launch command. Both ledgers are retained.

## Interpretation And Next Work

This proves bounded real search and completed ordinary games, not an AI strength
ranking. Both players changed policy together, seeds were development inputs,
time budgets can alter sampling, and there are only two pairs. White Weenie's
better results cannot be attributed to Burn becoming better or worse. Native
rollouts use the pinned hidden-information sampler, but full-policy fairness,
past reveal-memory conditioning and all hidden-zone cases remain unqualified.

The next integration step is a real actor-scoped native UI/IPC and persistence
bridge. No native engine or experimental weights have been installed in the
running application. Distribution/license review remains required before adoption.
