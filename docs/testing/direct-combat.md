# Direct Battlefield Combat

Select attackers by clicking cards; select a blocker then its target or drag the
blocker onto an attacker. Selections are local drafts until confirmed. Ordinary
blockers move between targets, while engine-supported multi-blockers may retain
several targets. Clear buttons undo the draft. Detailed controls remain available
for alternate defenders, payments and unusual declarations.

Attack moves expose effective `banding_attackers`. Block moves expose direct
`legal_blocks` and `blocker_capacities` (JSON null means unlimited). These fields
describe existing engine rules; final checked actions validate group requirements,
taxes, capacity and band propagation. Two ordinary attackers cannot gain banding.

## Checks

- Frontend unit tests cover draft purity, legal/illegal bands, defender
  consistency, block edges, finite/unlimited capacities and API contracts.
- Backend `test_direct_combat_views.py`, `test_attack_bands.py` and
  `test_ai_combat_intents.py` cover effective metadata, unchanged state during
  move generation, flying restrictions, band propagation and both-seat capacity.
- `browser-direct-combat.mjs` uses real Chromium pointer clicks and explicit
  HTML DragEvents through App, HTTP and the engine for both seats. This does not
  certify OS-level pointer dragging across devices.
- Existing capacity, payment, declaration-limit and BO3 scenarios retain their
  assertions and explicitly select attackers before submitting.

## Manual Review

Review physical drag gestures, keyboard/touch ergonomics and crowded boards on
the intended desktop browser. This change does not certify all Magic rules,
expert AI or matchup balance.
