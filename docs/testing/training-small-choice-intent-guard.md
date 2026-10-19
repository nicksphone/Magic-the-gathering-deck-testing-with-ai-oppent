# Replacement and trigger-target consumer guard

Production scope: `TrainingEnvironment.lookup_intent` only. The only new local
public imports are `ReplacementChoice` and `TriggerTargetChoice`. All prior
thirteen branches and production outside this function remain AST-identical.
No helper, API, schema, producer, engine, dataset, parent, or main edits.

Replacement display fields are `event` and `replacement_name`, nonempty strings.
Trigger-target display is `target_name`, a nonempty string. This is actual raw
legal-view decoration from `rules_engine.events.trigger_target_options`;
sanitized training hints omit it. Names do not select a source or target.
Unknown keys, including null aliases and nested root continuation contexts,
reject BEFORE completion. Even exact trusted pending context is rejected rather
than accepted and discarded. No source, target, controller, or choice inference.

Chosen parameters use the public models and strict `checked_action` legality.
For trigger targets, exactly one non-null `target_card_id` or `target_player`
is required. A recognized nullable alternative remains valid alongside an
explicit chosen card; an unknown null alias remains invalid.

Immutable original audit `fbe28458` (48 cases) is an explicit test dependency,
unchanged. Its baseline 24 unsupported failures / 24 passing independent
controls remains historical diagnostic evidence. Initial consumer attempt
incorrectly allowed no target display: four full-API target controls failed,
74 passed, 74.75 seconds. That log is preserved, not claimed green.

Corrected focused gate: original48 + NEW40 = **88 ordinary passes**, 78 datetime
warnings, 141.42 seconds, exit 0. Real both-seat counter order gives four versus
three counters; deliberate Sage targeting destroys only the chosen own/opposing
artifact. Whole raw/sanitized views, HTTP, full-pending restart, replay, root/DB
purity, and opposing hidden-identity input-byte equality are qualified.
New malformed display/context negatives preserve request and root; no helper
monkeypatch, contradictory witness, skip, or xfail is used to claim a pass.

The evidence report supplies the separate fresh shared neighboring gate and
source hashes. Limits: not all replacement domains, APNAP, player-target trigger
execution, or action-alias completeness. OptionalEffectChoice remains unchanged;
future paid-optional cost/affordability metadata requires actual-producer tests
and a separately qualified allowlist increment, not speculative acceptance here.
