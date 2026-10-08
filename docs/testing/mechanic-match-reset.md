# Mechanic Draft Match Identity

Baseline: `780f1a3a87d9920de6bc1582e576d9200b14d7ce`.

The actual Controls regression fails because identical offered choice IDs retain
a selected discard card after switching matches. The reset key now includes match
ID and game number, in addition to the existing complete mechanic-choice identity.
This also clears combat-damage allocations through their existing reset effect.
No action is inferred or submitted by the reset.

The unchanged regression passes after the correction: a same-view draft persists,
match/game transitions clear it, confirmation is disabled until a fresh selection,
and the fresh choice submits the exact actor/action. The complete configured
frontend test suite, lint and build exit zero. No backend or dependency changes.

The test uses compiled Controls with deterministic state/effect hooks. This is not
mounted React, browser, HTTP, natural-game or release-wide acceptance evidence.
