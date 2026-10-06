# Targeted library search resolver stage

Baseline: immutable Git b81862a20ade2cad1173336ebfda09a5528a43e4.
Production scope: effects/handlers.py search_library and new private _search_resolution_context only; AST preservation outside those functions verified.

Existing search_library ABI retains contains/destination/count/tapped/shuffle. Explicit strict target_player selects library/choice/destination owner. Original controller comes from a genuine retained __resolving_item on re-entry; continuation_controller remains original. Targeted search without frame fails closed before mutation. Legacy omitted-target direct calls keep their no-frame behavior, but shuffle now uses central shuffle_library rather than raw RNG. Restricted searches permit fail-to-find []; no eligible cards still shuffle. The target's chosen library IDs/owner/zone/filter/count and retained incarnation/zone-change references are checked before placement. Existing entry/counter/continuation pipelines remain authoritative.

## Qualification and limits

37 new resolver contract cases plus whole library_search_rules, shuffle_observer_resolution, land_entry_choice and entry_replacement_order: 114 pass, 4 warnings, 16.73 seconds. Contract cases use the genuine item captured from a paid canonical Rampant Growth; explicit retargeted packets are unit-level ABI exercises, NOT claims that Rampant Growth's printed instruction targets an opponent. Snapshot round trips and checked-action root immutability are covered. Entry/suffix tests are explicitly controlled effect_sequence fixtures, not certification of Fertilid's Favor compilation.

Separate unchanged desired runtime dependency ledger: 8 ordinary failures in 1.26 seconds (initial ledger: 1.20 seconds), both seats each:
- Fertilid lacks a legal activation in the pinned compiler.
- Fertilid's Favor paid cast rejects unsupported full resolution.
- Production own-search transport omits the real frame; central shuffle emits cause=None.
- Public pending search packet exposes options/library_ids/effect_payload.

No xfail, skip, exclusion or assertion weakening closes these failures. Targeted full compiler, source departure/blink, cold network HTTP/process restart, and target-specific SQL persistence/privacy are NOT qualified here. Existing neighbor API tests use ASGI TestClient, not a network server. This stage is NOT promotable until compiler/frame/privacy dependencies and full coupled runtime gates pass. No UI/AI/schema/compiler/cost/keyword/shuffle/event edits, no broad card support claim.

New full canonical raw fixtures (Fertilid, Fertilid's Favor, Rampant Growth, Forest, Breeding Pool) have intake URLs/oracle IDs and SHA256 in provenance.json; no Oracle alteration. Favor's complete counter suffix remains a compiler-owner obligation; unknown tails must fail closed, never partial search success.

## Separate-owner dependencies

Privacy seam: rules_engine/optional_reveal.py public_choice; game_state/serializers.py serialize_match publishes its result. Redact search_library/optional_search internal packets in public serialization without removing actor-private legal options. Actor-required options, ordered library_ids, effect_payload, resolving_item, continuation_controller and internal __search_references are not public fields. No edits to this seam in this stage.

Frame seam: rules_engine/stack_engine.py resolve_top_of_stack injects the actual popped StackItem only for shuffle_graveyard_into_library and sequences containing it. Registry already propagates __resolving_item within sequences. Separate owner must transport the genuine item for direct search and admitted search-containing sequences. Do not reconstruct source IDs/frames from card names.

Shuffle helper currently uses current source incarnation except retained graveyard-trigger references. Jason must confirm departed/blinked activated-source cause behavior. No resolver-created replacement receipt or guessed source reference.
