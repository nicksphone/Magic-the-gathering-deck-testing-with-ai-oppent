"""Passive causal tracing around the unchanged strict paid target assertions."""
import pytest

import test_paid_exchange_desired as original
import test_triggered_target_control as desired
from rules_engine import events, targeting
from rules_engine.continuous import effective_keywords

facts = desired.facts


@pytest.mark.parametrize('seat', [1, 2])
def test_strict_paid_target_assertion_with_passive_causal_trace(facts, seat, monkeypatch):
    observed = {'actual_items': [], 'target_checks': [], 'accepted_target_selections': []}
    options = events.trigger_target_options
    validate = targeting.validate_hexproof_shroud_targets
    select = events.resume_trigger_target
    record = original.record

    def trace_record(label, *args, **kwargs):
        return record('passive-trace-' + label, *args, **kwargs)

    def traced_options(state, item):
        observed['actual_items'].append({
            'stack_id': item.id, 'source_card_id': item.source_card_id,
            'controller': item.controller, 'effect_key': item.effect_key,
            'trigger_event': item.payload.get('__trigger_event'),
            'existing_stack_kind': targeting.stack_object_kind(state, item),
            'retained_source_lki': item.payload.get('__source_lki')})
        return options(state, item)

    def traced_validate(state, actor, selected, source_card=None, **kwargs):
        result = validate(state, actor, selected, source_card, **kwargs)
        target = state.cards.get(selected.get('target_card_id'))
        if target is not None and target.name == original.SOURCE:
            observed['target_checks'].append({
                'actor': actor, 'source_card_id': getattr(source_card, 'id', None),
                'target_id': target.id, 'target_controller': target.controller,
                'canonical_target_oracle': target.oracle_text,
                'effective_keywords': sorted(effective_keywords(state, target.id)),
                'validator_kwargs': kwargs, 'actual_result': result})
        return result

    def traced_select(state, stack_id, target_card_id=None, target_player=None):
        result = select(state, stack_id, target_card_id, target_player)
        target = state.cards.get(target_card_id)
        if result and target is not None and target.name == original.SOURCE:
            observed['accepted_target_selections'].append({
                'stack_id': stack_id, 'selected_target': target_card_id, 'result': result})
        return result

    monkeypatch.setattr(events, 'trigger_target_options', traced_options)
    monkeypatch.setattr(targeting, 'validate_hexproof_shroud_targets', traced_validate)
    monkeypatch.setattr(events, 'resume_trigger_target', traced_select)
    monkeypatch.setattr(original, 'record', trace_record)
    try:
        desired.test_paid_triggered_ability_rejects_opponent_stormdrake_but_resolves_lawful_target(facts, seat)
    finally:
        with (original.OUT / f'{original.PHASE}-target-kind-trace-{seat}.json').open('x') as out:
            import json
            json.dump(observed, out, indent=2, sort_keys=True)
