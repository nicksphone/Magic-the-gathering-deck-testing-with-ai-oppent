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

## Acceptance Evidence (2026-10-05)

- Frozen backend `c8bf6ab`: 8,335 tests pass across all 337 recursive test files,
  assigned exactly once to four isolated source copies with empty initial
  databases; all 658 source/fixture hashes match. Backend is byte-identical to
  the subsequent frontend-only draft repair `5bdbdfe`.
- Frontend unit tests, ESLint and production TypeScript/Vite build pass.
- Complete browser harness passes, including restart recovery and natural
  AI/AI, human/AI and human/human BO3. The functional draft follow-up landed
  during that run; final-source direct-combat, multi-block capacity/payment,
  combat branch/payment and automatic-priority cases were rerun and pass.
- Evidence is archived and verified under RCHFiles `diagnostics/direct-combat/`
  in `20261005T100340Z`. No fresh dependency installation or universal rules/AI
  certification is claimed.
