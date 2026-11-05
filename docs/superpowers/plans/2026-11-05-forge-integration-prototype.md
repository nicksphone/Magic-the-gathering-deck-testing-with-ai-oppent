# Forge Integration Prototype Plan

> Implement inline with the executing-plans workflow. Keep the live app untouched.

**Goal:** prove or reject the native-engine shortcut beyond card-definition tests,
without weakening the original AI, privacy, BO3 or application requirements.

**Architecture:** a separately licensed, isolated Java probe calls the pinned
Forge native APIs. Existing app deck lists remain the input. Existing Python/UI,
saved matches and private training artifacts are not modified or exposed.

**Source:** Forge `61e9442c433711a82258daca3236f936a1d6f70e`, as evaluated in
[the card comparison](../../testing/external-engine-card-knowledge.md).

## Constraints And Review Focus

- Preserve upstream copyrights/license notices and credit Forge beside its use.
- No fabricated Oracle, board events, winners or terminal rewards.
- Do not use the CLI's timeout-to-draw fallback for qualification.
- Validate imported card quantities; unknown cards must not disappear silently.
- Declare open deck lists for this diagnostic; opposing hands/library order are
  still private. A raw remote object is not presumed safe for a browser.
- Bound execution; censored runs remain incomplete, not draws or victories.
- Use local active data and mounted, byte-verified NFS archives for closed evidence.
- No production cutover or root-license changes from a successful prototype.

## Task 1: Complex Native Match

- [x] Reuse the verified cached Forge classpath and sandbox; no new framework.
- [x] Generate Ramp and Dimir Control from the app's exact main-deck lists.
  Add clearly labelled constructed 15-card sideboards, not tournament provenance.
- [x] Write an original credited caller for `Match.createGame/startGame`;
  never call a setter to manufacture a terminal game result.
- [x] Assert deck inventory conservation and record native game outcomes, turns,
  timing, deck changes and private logs across a real first-to-two-wins match.
- [x] Verify the full native terminal sequence, not just process exit zero.

## Task 2: Actor/Choice Boundary

- [x] Audit native human-controller callbacks and hidden-card visibility before
  serializing anything for an app client; no raw `GameView` passthrough.
- [ ] Add failing privacy/choice tests before implementing an actor-scoped adapter.
- [ ] Prove an actual user choice reaches the native engine and updates state,
  with wrong-actor and unavailable-choice rejection and no private-zone leakage.
- [ ] Report unresolved privacy, sideboarding, persistence and packaging gaps.

## Completion Boundary

This prototype is not RC or expert-AI acceptance. It must produce an adoption
decision backed by concrete integration evidence. Existing app/source/data remain
the fallback. Continue the full goal after these prototype tasks; do not redefine
AI completion as these tasks passing.
