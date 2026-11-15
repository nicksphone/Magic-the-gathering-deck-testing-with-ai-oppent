# Modal Draw Wins

Gameplay change: `7bfbfad4c389eb134ec0b5a34d6deea46ac55f73`.

The initial hypothesis that ordinary modal draw chose the wrong recipient was
not reproduced. A separate decision error was: on both seats, Strong Control
paid three mana to counter an opposing Inspiration instead of using Archmage's
Charm's legal, equally priced draw mode to win against an empty opposing library.
The real paid winning alternative was independently resolved from the same root.

Single-mode selection now checks whether a complete targeted-draw mode produces
a terminal win in the existing actor-visible continuation before applying its
ordinary mode heuristics. It reuses checked materialization, payment and opaque
draw forecasting. It preserves the offered action's target and cost constraints;
it does not invent a cheaper action or substitute the opposing recipient when
the actor already chose itself. Explicit modes remain explicit.

## Evidence And Limits

- The new regressions first ran six failing choices with passing controls.
- The final focused union passed 80 tests in 56.20 seconds.
- Independent qualification on the installed application runtime passed nine
  whole modules, 378 tests in 128.30 seconds, with no forbidden I/O. All 2,634
  reviewed backend inputs remained byte-identical through the run.
- The 24 new cases cover both-seat paid wins, ordinary counter preference,
  real draw replacement, unknown private-draw choices, hidden-information
  permutations and preservation of explicit modes and recipients.
- Only mode selection and its materialization call changed; the other function
  ASTs match the preimage. No engine, schema, model weights or dependency changed.

These are constructed-state paid-outcome checks, not complete-game strength or
performance acceptance. Multi-select modes, other compound draw bodies and
unrelated targeting-validator defects remain separate. No card-name exception
or overall AI-completion claim is made.
