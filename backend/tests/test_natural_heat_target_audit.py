"""Canonical controls for the private sealed play. PYTEST_DONT_REWRITE

Keep the assertions, but never expand private snapshot values into public CI logs.
"""
import json
import os
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai import pending_effects
from ai.action_contract import complete_action
from ai.information import decision_view
from ai.pending_effects import friendly_destruction_profit
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.continuous import effective_granted_target_abilities
from rules_engine.type_effects import effective_types
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.natural_heat_diagnostic_support import (
    advance_until, canonical, canonical_control, exact_state, private_cards,
    rank_diagnostic, receipts, removal_delta, replay_receipt,
)


DEFAULT_LEGACY_SCHEDULER = {
    'version': 1, 'extra_turns': [], 'next_phase_visit': 1,
    'next_schedule_ordinal': 1, 'normal_turn_successor': None,
    'phase_cursor': 0, 'phase_plan': [],
}


def _current_legacy_snapshot(snapshot):
    normalized = serialize_match_snapshot(deserialize_match_snapshot(snapshot))
    assert normalized['scheduler'] == DEFAULT_LEGACY_SCHEDULER
    return normalized


def _assert_legacy_snapshot_parity(actual, historical, original, history, history_known,
                                   source_id, binding, departed_lki):
    expected = _current_legacy_snapshot(historical)
    assert actual['scheduler'] == DEFAULT_LEGACY_SCHEDULER
    actual = deepcopy(actual)
    # The raw receipt predates these fields; validate their complete current values
    # before projecting only metadata absent from that immutable receipt.
    assert actual['spell_color_history'] == history
    assert actual['spell_color_history_known'] is history_known
    if 'spell_color_history' not in original:
        assert 'spell_color_history_known' not in original
        expected['spell_color_history'] = deepcopy(history)
        expected['spell_color_history_known'] = history_known
    assert len(actual['stack']) == len(expected['stack']) == len(original['stack'])
    for current, old, raw in zip(actual['stack'], expected['stack'], original['stack']):
        if current['source_card_id'] != source_id:
            continue
        for key, value in binding.items():
            assert canonical(current['payload'][key]) == canonical(value)
            if key == '__granted_target_revision':
                assert type(current['payload'][key]) is int
            if key not in raw['payload']:
                assert key not in old['payload']
                current['payload'].pop(key)
    for cid, lki in departed_lki.items():
        for current, raw in [(actual['cards'][cid], original['cards'][cid]), *[
                (actual['card_observations'][seat][cid],
                 original['card_observations'][seat][cid]) for seat in ('1', '2')]]:
            assert current['last_known_battlefield']['loyalty'] == lki['descriptor']['loyalty']
            assert canonical(current['last_known_battlefield']['__copiable_lki']) == canonical(lki)
            for key in ('loyalty', '__copiable_lki'):
                if key not in raw['last_known_battlefield']:
                    current['last_known_battlefield'].pop(key)
    for seat, observations in actual['card_observations'].items():
        for cid, current in observations.items():
            raw = original['card_observations'].get(seat, {}).get(cid)
            # The source's new public entry was independently checked above.
            if raw is None:
                assert cid == source_id
                raw = {}
            if cid in departed_lki or not raw:
                assert all(key in current for key in ('control_effect_base', 'control_effects', 'kicker_count'))
            for key, value in {'control_effect_base': None, 'control_effects': [],
                               'kicker_count': None}.items():
                if key not in raw and key in current:
                    assert current[key] == value
                    current.pop(key)
    # Only the original collector's historical AI TRACE log is excluded.
    assert canonical({k: v for k, v in actual.items() if k != 'log'}) == canonical(
        {k: v for k, v in expected.items() if k != 'log'})


def _legacy_snapshot_with_public_entry(snapshot, card_id):
    expected = _current_legacy_snapshot(snapshot)
    card = expected['cards'][card_id]
    assert card['zone'] == 'graveyard'
    assert card_id in expected['players'][str(card['owner'])]['graveyard']
    for seat in ('1', '2'):
        observations = expected['card_observations'].setdefault(seat, {})
        assert card_id not in observations
        observations[card_id] = deepcopy(card)
    return expected


def _legacy_snapshot_with_committed_death(snapshot, card_id, previous_sequence):
    expected = _current_legacy_snapshot(snapshot)
    card = expected['cards'][card_id]
    assert card['zone'] == 'graveyard'
    assert card_id in expected['players'][str(card['owner'])]['graveyard']
    assert card['zone_change_sequence'] == previous_sequence
    card['zone_change_sequence'] = previous_sequence + 1
    for seat in ('1', '2'):
        observation = expected['card_observations'][seat][card_id]
        assert observation['zone'] == 'graveyard'
        assert observation['zone_change_sequence'] == previous_sequence
        observation['zone_change_sequence'] = previous_sequence + 1
    return expected


def _legacy_replay_context(row, state):
    """Derive the five expectations solely from the independent PRE position."""
    source_id = row['action']['card_id']
    victim_id = row['action']['targets']['target_card_id']
    victim = state.cards[victim_id]
    target_ref = {'card_id': victim_id, 'incarnation': object_incarnation(victim),
                  'zone_change_sequence': victim.zone_change_sequence}
    capture = {'status': 'captured', 'captured': True,
               'target_refs': [target_ref], 'receipts': []}
    binding = {'__announced_stack_kind': 'spell',
               '__announced_target_references': {'version': 1, 'targets': {'target_card_id': target_ref}},
               '__granted_target_capture': capture, '__granted_target_membership': [target_ref],
               '__granted_target_published_capture': capture, '__granted_target_revision': 0}
    assert 'spell_color_history' not in row['snapshot']
    assert 'spell_color_history_known' not in row['snapshot']
    assert any(row['snapshot']['spells_cast_this_turn'].values())
    history = {'1': [], '2': []}
    history_known = False
    assert state.spell_color_history == {1: set(), 2: set()}
    assert state.spell_color_history_known is False
    return {'history': history, 'history_known': history_known, 'source_id': source_id,
            'binding': binding, 'departed_lki': {}}


def _capture_legacy_pre_step(state, receipt, victim_id, context):
    """Copy cast colors and victim LKI before checked_action can change either."""
    source_id = context['source_id']
    history = context['history']
    source_before = state.cards[source_id]
    victim_before = state.cards[victim_id]
    if receipt['action']['type'] == 'cast_spell':
        assert receipt['action']['card_id'] == source_id
        assert isinstance(source_before.colors, list) and source_before.colors
        assert not source_before.card_faces and not source_before.type_effects
        assert source_before.type_effect_base is None
        assert set(source_before.colors) <= set('WUBRG')
        history[str(receipt['pid'])] = sorted(set(history[str(receipt['pid'])])
                                              | set(source_before.colors))
    if victim_before.zone == Zone.BATTLEFIELD:
        assert victim_before.type_effect_base is None and not victim_before.type_effects
        assert not any(victim_before.counters.get('__crew_added_' + kind.lower())
                       for kind in victim_before.types)
        assert list(effective_types(state, victim_before)) == victim_before.types
        descriptor = {key: deepcopy(getattr(victim_before, key)) for key in (
            'name', 'mana_cost', 'type_line', 'power', 'toughness', 'printed_power',
            'printed_toughness', 'oracle_text', 'keywords', 'colors', 'image_uri', 'loyalty')}
        descriptor['types'] = list(dict.fromkeys([*victim_before.types, 'Token']))
        descriptor['colors'] = deepcopy(victim_before.colors or [])
        if victim_before.layout in {'transform', 'modal_dfc', 'double_faced_token'}:
            face = victim_before.selected_face_index if victim_before.selected_face_index is not None else 0
            assert len(victim_before.card_faces) == 2 and type(face) is int and face in (0, 1)
            descriptor.update(card_faces=deepcopy(victim_before.card_faces),
                              layout='double_faced_token', selected_face_index=face)
        return {'reference': [object_incarnation(victim_before), victim_before.zone_change_sequence],
                'controller': victim_before.controller, 'types': list(victim_before.types),
                'descriptor': descriptor}
    return None


def _replay_legacy_receipts(row, state, replay_receipts):
    context = _legacy_replay_context(row, state)
    source_id = context['source_id']
    victim_id = row['action']['targets']['target_card_id']
    for receipt in replay_receipts:
        if receipt['event'] != 'applied' or not 303 <= receipt['tick'] <= 305:
            continue
        source_before = state.cards[source_id]
        victim_before = state.cards[victim_id]
        lki = _capture_legacy_pre_step(state, receipt, victim_id, context)
        state = checked_action(state, RulesEngine(), receipt['pid'], receipt['action'])
        actual = serialize_match_snapshot(state)
        expected = receipt['snapshot']
        if victim_before.zone == Zone.BATTLEFIELD and state.cards[victim_id].zone == Zone.GRAVEYARD:
            context['departed_lki'][victim_id] = lki
            assert state.cards[victim_id].zone_change_sequence == victim_before.zone_change_sequence + 1
            expected = _legacy_snapshot_with_committed_death(
                expected, victim_id, victim_before.zone_change_sequence)
        if source_before.zone == Zone.STACK and state.cards[source_id].zone == Zone.GRAVEYARD:
            assert state.cards[source_id].zone_change_sequence == source_before.zone_change_sequence + 1
            expected = _legacy_snapshot_with_public_entry(expected, source_id)
        _assert_legacy_snapshot_parity(actual, expected, receipt['snapshot'], **context)
    return state, context


def test_exact_captured_resolution_preserves_original_trace_and_proves_loss():
    row, state = exact_state()
    before = canonical(serialize_match_snapshot(state))
    assert canonical(RulesEngine().legal_moves(state, row['pid'])) == canonical(row['legal_moves'])
    victim_id = row['action']['targets']['target_card_id']
    assert not effective_granted_target_abilities(state, victim_id)
    state, _ = _replay_legacy_receipts(row, state, receipts())
    victim = row['action']['targets']['target_card_id']
    assert state.cards[victim].zone == Zone.GRAVEYARD
    assert row['action']['card_id'] in state.players[row['pid']].graveyard
    assert [item.label for item in state.stack] == ['Memory Deluge']
    assert state.players[row['pid']].life == row['snapshot']['players'][str(row['pid'])]['life']
    assert canonical(_current_legacy_snapshot(row['snapshot'])) == before


@pytest.mark.parametrize('corruption', ['colors', 'descriptor', 'observation',
                                      'binding-version', 'binding-captured', 'lki-reference'])
def test_private_legacy_adapter_rejects_independent_protocol_corruption(monkeypatch, corruption):
    if corruption == 'colors':
        monkeypatch.setattr('rules_engine.turn_spell_protection.card_color_symbols', lambda *args: set())
    elif corruption == 'descriptor':
        from effects import handlers
        original = handlers.token_copy_descriptor
        monkeypatch.setattr(handlers, 'token_copy_descriptor',
                            lambda card: {**original(card), 'mana_cost': 'incorrect'})
    elif corruption == 'observation':
        original = serialize_match_snapshot
        def missing_default(state):
            snapshot = original(state)
            for observations in snapshot['card_observations'].values():
                for card in observations.values():
                    if card['zone'] == 'graveyard':
                        card.pop('kicker_count', None)
            return snapshot
        monkeypatch.setattr(__name__ + '.serialize_match_snapshot', missing_default)
    else:
        original = serialize_match_snapshot
        def wrong_protocol_type(state):
            snapshot = original(state)
            if corruption == 'lki-reference':
                for card in snapshot['cards'].values():
                    lki = card['last_known_battlefield'].get('__copiable_lki')
                    if lki:
                        lki['reference'][0] = float(lki['reference'][0])
            else:
                for item in snapshot['stack']:
                    payload = item['payload']
                    if '__granted_target_capture' in payload:
                        if corruption == 'binding-version':
                            payload['__announced_target_references']['version'] = True
                        else:
                            payload['__granted_target_capture']['captured'] = 1
            return snapshot
        monkeypatch.setattr(__name__ + '.serialize_match_snapshot', wrong_protocol_type)
    with pytest.raises(AssertionError):
        test_exact_captured_resolution_preserves_original_trace_and_proves_loss()


def test_rank_materialization_and_profit_diagnostics_are_root_pure_and_private():
    result = rank_diagnostic()
    assert result['actual_root_scores'], 'Must record real existing ranker scores, not guessed constants'
    assert all(result['privacy'].values())
    path = Path(os.environ['MTG_HEAT_REPORT'])
    path.write_text(json.dumps(result, sort_keys=True, indent=2))


def test_original_natural_decision_must_not_spend_heat_to_kill_own_delver():
    row, state, decision, profit_calls = replay_receipt()
    candidate, delta = removal_delta(state, row['action'], row['action']['targets']['target_card_id'])
    assert delta < 0, 'This regression is limited to the demonstrated losing trade'
    path = Path(os.environ['MTG_HEAT_REPORT']).with_name('actual-replay.json')
    path.write_text(json.dumps({'actual_action': decision.action, 'reasoning': decision.reasoning,
                               'exact_checked_declaration_parity': complete_action(decision.action)
                               == complete_action(row['action']),
                               'sealed_action': row['action'], 'friendly_profit_calls': profit_calls,
                               'resolved_board_delta': delta,
                               'opponent_deluge_remains': [item.label for item in candidate.stack]},
                              sort_keys=True, indent=2))
    assert not (decision.action.get('card_id') == row['action']['card_id']
                and decision.action.get('targets', {}).get('target_card_id')
                == row['action']['targets']['target_card_id']), 'AI selected the sealed losing friendly trade'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('window', ['response', 'proactive'])
@pytest.mark.parametrize('style', ['Tempo', 'Aristocrats'])
@pytest.mark.parametrize('payoff', ['Bastion of Remembrance', 'Blood Artist'])
def test_beneficial_friendly_burn_stays_legal_and_wins(seat, window, style, payoff):
    state, heat, victim = canonical_control(seat, window, payoff=payoff)
    before = canonical(serialize_match_snapshot(state))
    legal = RulesEngine().legal_moves(state, seat)
    view, private_legal = decision_view(state, seat, legal)
    assert all(private_cards(view, seat).values())
    ai = AIAgent(archetype=style, opponent_archetype='Control', difficulty='master')
    declared = {'type': 'cast_spell', 'card_id': heat, 'targets': {'target_card_id': victim}}
    assert friendly_destruction_profit(view, seat, declared,
        own_choice_action=lambda s, moves, pid: ai.choose_action(s, moves, pid).action) is True
    decision = ai.choose_action(state, legal, seat)
    move = next(move for move in private_legal if move.get('card_id') == heat)
    materialized = ai._materialize_action(view, {**move, 'targets': declared['targets']}, seat)
    assert materialized.get('targets', {}).get('target_card_id') == victim
    assert not materialized.get('_invalid_ai_choice'), 'Beneficial friendly burn was rejected'
    assert canonical(serialize_match_snapshot(state)) == before
    candidate = checked_action(state, RulesEngine(), seat, materialized)
    candidate = advance_until(candidate, lambda s: s.winner is not None, ai)
    assert candidate.winner == seat
    with Path(os.environ['MTG_HEAT_REPORT']).with_name('beneficial-controls.jsonl').open('a') as log:
        log.write(json.dumps({'seat': seat, 'window': window, 'style': style, 'payoff': payoff,
                              'actual_choice': decision.action, 'reasoning': decision.reasoning,
                              'materialized_beneficial_action': materialized,
                              'checked_winner': candidate.winner}, sort_keys=True) + '\n')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('window', ['response', 'proactive'])
def test_opponent_removal_materializes_opponent_and_resolves_exact_damage(seat, window):
    state, heat, victim = canonical_control(seat, window, opponent_target=True)
    before = canonical(serialize_match_snapshot(state))
    legal = RulesEngine().legal_moves(state, seat)
    move = next(move for move in legal if move.get('card_id') == heat)
    view, moves = decision_view(state, seat, [move])
    ai = AIAgent(archetype='Tempo', opponent_archetype='Control', difficulty='master')
    action = ai._materialize_action(view, moves[0], seat)
    assert action.get('targets', {}).get('target_card_id') == victim
    assert not action.get('_invalid_ai_choice')
    candidate, delta = removal_delta(state, action, victim)
    assert candidate.cards[victim].zone == Zone.GRAVEYARD
    assert delta > 0
    assert canonical(serialize_match_snapshot(state)) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('window', ['response', 'proactive'])
def test_response_and_proactive_boundaries_record_actual_decision_and_known_loss(seat, window):
    state, heat, victim = canonical_control(seat, window)
    before = canonical(serialize_match_snapshot(state))
    legal = RulesEngine().legal_moves(state, seat)
    view, moves = decision_view(state, seat, legal)
    assert all(private_cards(view, seat).values())
    ai = AIAgent(archetype='Tempo', opponent_archetype='Control', difficulty='master')
    with patch.object(pending_effects, 'friendly_destruction_profit',
                      wraps=pending_effects.friendly_destruction_profit) as profit:
        decision = ai.choose_action(state, legal, seat)
        profit_calls = profit.call_count
    declared = {'type': 'cast_spell', 'card_id': heat, 'targets': {'target_card_id': victim}}
    candidate, delta = removal_delta(state, declared, victim)
    assert delta < 0
    assert candidate.cards[victim].zone == Zone.GRAVEYARD
    assert canonical(serialize_match_snapshot(state)) == before
    with Path(os.environ['MTG_HEAT_REPORT']).with_name('window-boundaries.jsonl').open('a') as log:
        log.write(json.dumps({'seat': seat, 'window': window, 'actual_action': decision.action,
                              'reasoning': decision.reasoning, 'declared_trade_delta': delta,
                              'actual_friendly_profit_calls': profit_calls,
                              'forced_response': ai._forced_stack_interaction(view, moves, seat),
                              'friendly_profit': friendly_destruction_profit(view, seat, declared)},
                             sort_keys=True) + '\n')
