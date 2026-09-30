# AI Pending-Removal Awareness

## Implemented Scope

AI projects the announced stack through the existing rules engine on an isolated state copy. It does not guess new opposing responses or inspect additional hidden information. Historical logs are omitted from the copy because resolution does not consume them. The projection is bounded to 128 priority passes and stops at unresolved mechanic, replacement or trigger-order choices.

For supported simple instant/sorcery destruction, exile or bounce effects, target materialization excludes opposing permanents already covered by pending removal. It can select an uncovered threat instead, or hold the spell. A known counter or pump response can make the first removal insufficient, allowing backup interaction. Exile can retain value when pending destruction would instead leave the card in the graveyard. Text with recognized secondary-effect verbs is retained conservatively rather than assumed redundant. This is a bounded AI policy, not a human cast restriction or complete effect-value analysis.

The same real-card fixtures exposed two engine defects: targeted destruction ignored indestructible, and the pure numeric clause `Target creature gets +N/+M until end of turn` was not interpreted. Shared handlers now respect indestructible and infer signed numeric targeted P/T changes through the existing temporary-effect machinery. AI directs purely positive changes toward friendly creatures and purely negative changes toward opposing creatures. Mixed signs, X, granted keywords and compound pump clauses are not certified here.

## Diagnostic Contract

Decision traces include stack ID/controller/kind, label, saved source/copy characteristics, effect payload, announced targets, source last-known information and engine-detected counterability. A missing source remains an explicit stack entry instead of disappearing. Internal continuation keys are not included in the effect payload.

`redundant_removal_casts` is the sixth shared decision-quality metric. It flags a selected simple removal target already covered by the bounded projection. Legacy or malformed producer evidence, and a projection blocked by unresolved choices, make the metric unavailable. The report must not convert that absence to zero. Zero flags still do not certify every possible removal, secondary clause or tactical line.

## Before and After

Baseline agent: `3589cd9`. The comparison uses the updated rules engine and trace producer with the baseline agent loaded separately; it is not a byte-for-byte old-engine run. Both agents receive identical state and legal moves in four canonical fixtures:

| Pending effect / target | Baseline | Updated |
| --- | --- | --- |
| Go for the Throat / Sprite Dragon | Cast duplicate removal | Pass priority |
| Fatal Push / Sprite Dragon | Cast duplicate removal | Pass priority |
| Naturalize / Mind Stone | Cast duplicate removal | Pass priority |
| Naturalize / Phyrexian Arena | Cast duplicate removal | Pass priority |

The Dimir Control seat-one / Tempo seed-711 game reproduces the original four-removal burst with the baseline agent. The new producer identifies three redundant casts at turn 42. Updated play records zero redundant casts: when Tempo counters a pending Fatal Push, Dimir can commit Go for the Throat instead of prematurely spending all its removal. The game winner remains Dimir; outcome alone would have missed this resource error.

Fixtures preserve real Scryfall IDs, Oracle IDs and printed characteristics for ten cards in `backend/tests/fixtures/pending_removal.json`. Production logic has no card-name exceptions. Tests cover repeated target conservation, uncovered threats, known counter/pump responses, indestructible, snapshot preservation, surviving spell-copy trace characteristics, positive-pump target selection and unavailable evidence.

## Validation

- The isolated backend full suite passes 1,629 tests. Frontend lint/build/unit and the complete Chromium action/recovery/BO3 harness pass.
- Tempo/Dimir seeds 710-711 and Tribal/Blue Control seeds 720-721 run twice per matchup with both seat orders: eight games. Dimir wins four of four; Blue Control wins three of four. No matchup timeout or cast-time target/mana-cost rejection is observed. Both seats have available redundant-removal evidence with zero flags in all four matchup aggregates.
- Seeded three-game BO3 replay reports zero determinism failures and no drift labels.
- Counter-tax nonpayment is ordinary resolution behavior, not a cast-cost rejection. One Blue Control blocking diagnostic is unavailable because the existing bounded combat validator cannot certify its line; its raw zero is not treated as measured evidence.
- Logs, initial-state comparisons and JSON evaluations are retained under `/tmp/mtg-pending-removal.p4glI9/`. These are local diagnostic artifacts, not a permanent shipped dataset. Relevant commands are the documented head-to-head runner, regression replay runner and isolated browser harness.

## Known Limitations and Next Upgrades

This projection is only as correct as the engine's supported effects. It keeps interaction available when choices are unknown; it is not an opponent-response search. Additional beneficial removal clauses, modal/multi-target effects, prevention/replacement families and protection-removal planning need independent golden tests. A later [pure-destruction target guard](ai-destruction-targets.md) addresses indestructible targets even without pending removal; arbitrary compound effects remain outside that guard. The tiny matchup sample does not establish balance, optimal play or seasoned-player competence. Broader seat-balanced archetype evaluation remains open.
