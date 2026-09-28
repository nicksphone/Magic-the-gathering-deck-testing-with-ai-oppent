# Token zone-transfer boundary audit (2026-09-28)

Status: partial implementation, broader transfer model not certified.

## Rule and current evidence

[Comprehensive Rules 111.7-111.8](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf) require a token that leaves the battlefield to remain in its first destination until the next state-based check, when it ceases to exist. The zone change still generates applicable triggers.

- Reproduced: direct graveyard return could put a destroyed token back onto the battlefield before SBA. The shared departed-token predicate now rejects supported graveyard returns, recasts, dredge selection, escape payments and mass-graveyard exile.
- Reproduced: a bounced token counted toward a discard activation cost and could be selected as a land to put onto the battlefield. Cost admission/selection, hand discard, generic hand-to-battlefield effects, Ninjutsu, legal moves and exile-play permission now reject it.
- Generated tokens have a persistent `is_token` identity independent of mutable `types`; legacy snapshots with a `Token` type marker still restore. Nontoken triggers and continuous token buffs use this identity. Snapshot/public-view tests cover a type-changed token.
- The existing SBA path removes departed tokens from player zones and marks an internal `ceased` state, retaining source data for already-generated triggers. Bastion of Remembrance and Grim Haruspex fixtures bound trigger behavior.

## Remaining boundary

Direct zone-list mutations still exist in `effects/handlers.py` (search/topdeck/draw-to-hand and exile-top effects), `game_state/state.py` (draw), and `rules_engine/engine.py` (pregame/land/cast transitions). These call sites were inventoried, not all reproduced with a reachable same-resolution token fixture. Do not infer that every path is broken or that rule 111.8 is globally certified.

Next gate: define one checked transfer operation for card/token moves with an explicit first-exit marker and event ordering; migrate supported non-battlefield transfers to it. Add golden tests for a token moving to hand, graveyard, exile and library, an attempted second move before SBA, trigger collection, and snapshot/replay behavior. Then verify the same cases through HTTP actions where the effect sequence is actually reachable. Do not substitute a type-list check or an early SBA call for this transfer rule.
