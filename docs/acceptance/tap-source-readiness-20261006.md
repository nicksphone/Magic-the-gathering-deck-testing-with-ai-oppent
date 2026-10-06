# Shared Tap-Source Readiness

The shared activated-cost availability check rejects a self-tap cost when its
source is an effective Creature with summoning sickness and without effective
haste. This applies to all callers of that cost check, not named cards.
Non-tap creature abilities and noncreature tap costs retain existing behavior.

## Executed Evidence

- New controlled-board tests: 18 passed. Identical baseline: 6 failed, 12 passed.
- Eight complete affected modules, including those tests: 277 passed, 19.52s.
- Unchanged canonical Scout/Atlas core module: 32 passed, four known decline
  failures, 7.71s. HTTP module: eight passed, four known decline failures, 67.12s.
  All twelve prior sick-creature admission failures are closed in that isolated
  composition. The optional-land decline hook was not applied there.
- A separate composition with the verified optional-land validator hook then
  passed all 48 unchanged canonical tests, 83.65s. That hook is not included in
  this milestone; the guards-only failure ledger above remains unchanged.
- The first HTTP attempt had twelve setup errors because its evidence-directory
  environment variable was missing. That ledger is preserved separately.
- Initial neighbor execution: 251 passed, 26 failures in discard-choice tests
  whose freshly placed Rummaging Goblin was summoning-sick. The fixture now
  explicitly represents a creature ready to tap; all assertions are retained.

## Limits

The controlled-board tests exercise effective haste granting/removal and snapshot
restore, not full canonical casting of every fixture. Animation, control-change
episodes, untap-symbol costs, arbitrary-card support, and live deployment are
not certified by this slice. Live user databases and main checkout are untouched.
