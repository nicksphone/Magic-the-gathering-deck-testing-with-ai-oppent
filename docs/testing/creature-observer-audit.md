# Canonical Creature Observer Audit

Source is frozen corrected-prefix tar 9b14c9af788f4bdfb7af2491e502c103a16caaafa21ed6862ccf61eab2d61b0e. This new audit adds no product changes.

Primordial Sage: complete official Oracle says whenever you cast a creature spell, you may draw a card. Actual funded Grizzly Bears casts produce no Sage trigger for either seat.

Soul of the Harvest: complete official Oracle includes trample and whenever another nontoken creature you control enters, you may draw a card. Actual funded Grizzly Bears casts resolve to battlefield without a Soul trigger for either seat.

Retained observer boards, turn-five main phase, canonical Island libraries, and explicit seeded mana pools are controlled fixture setup, NOT naturally played games. Every stimulus is a checked paid cast; token entries are actual Raise the Alarm resolution. Tests do not create events or StackItems. Read-only compilation probes consume actual captured event payloads and never install their results.

Final new module: 56 cases, 36 PASS / 20 ordinary FAIL. Failures: 8 optional-outcome cases stop at missing trigger, 4 source-response cases stop before bounce due missing trigger, 8 HTTP cases stop after actual cast/entry, cold GET and fresh-process snapshot roundtrip at missing trigger. No skips, xfails or deselections. Optional accept/decline and source independence for these two families are NOT yet qualified. Four actual Harvester of Souls/Village Rites optional-death controls pass, as do four compiler-only probes producing draw_cards amount 1 with __may=true. Twelve actual opponent/noncreature/token/self-entry controls pass; absence alone cannot certify a presently missing observer's eventual predicate implementation. Sixteen HTTP wrong-actor/underpayment checks prove snapshot/controller/SQL atomicity on memory and file repositories.

Minimal proposed product seams, not implemented: events._collect_triggers cast admission should reuse exact subject filtering in _matched_cast_trigger_clauses rather than card-name checks; events._entry_observer_clause and _matches_enters_battlefield_trigger need structural optional nontoken filtering with another/controller/type checks. Compile the matched complete optional body through existing conservative routing; preserve optional ownership and no partial compound reward. Current direct compiler probes already retain controller/source and __may, so no optional-handler repair is established by this audit.

Historical c16 four-red observer diagnosis stays separate and was not rerun. Original 291/coupled 2179 were not rerun. Three distinct whole neighbor modules pass 40 cases. All source and evidence are pinned to this immutable archive, not current parent composition.
