"""Bounded fixed source-counter costs; canonical episodes and labelled pure seams."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine import costs
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_batch_graveyard_publication_audit import client, assert_private
from tests.generic_import_fixtures import client as base_client
from tests.test_builtin_metadata_refresh import repo, seed_cache
from tests.test_counter_activation_admission_audit import board, literal_cost
from tests.test_self_graveyard_replacement_audit import act, snap, restart
from tests.test_spell_admission_safety_http import sql_facts


@pytest.mark.parametrize('quantity,amount', [('a', 1), ('one', 1), ('two', 2), ('10', 10)])
def test_fixed_quantity_parser_and_exact_resource_payment(quantity, amount):
    # Pure cost grammar/resource seam, NOT invented Oracle on a gameplay card.
    state, source, _ = board(1, counters=10)
    text = f'Remove {quantity} +1/+1 counters from this creature'
    parsed = costs.parse_activated_cost(text)
    assert parsed.supported and parsed.remove_source_counters == amount
    assert parsed.remove_counter_kind == '+1/+1'
    before = snap(state)
    assert costs.activated_cost_available(state, 1, source, text)
    assert snap(state) == before
    assert costs.apply_activated_costs(state, 1, source, text)
    expected = deepcopy(before)
    expected['cards'][source]['counters']['+1/+1'] -= amount
    assert snap(state) == expected


@pytest.mark.parametrize('text', [
    'Remove zero +1/+1 counters from this creature',
    'Remove 0 +1/+1 counters from this creature',
    'Remove -1 +1/+1 counters from this creature',
    'Remove X +1/+1 counters from this creature',
    'Remove eleven +1/+1 counters from this creature',
    'Remove a +1/+1 counter from another creature',
    'Remove a loyalty counter from this permanent',
    '{T}, Remove a +1/+1 counter from this creature',
    'Remove a +1/+1 counter from this creature, pay 2 life',
    'Pay 2 life and remove a +1/+1 counter from this creature',
    'Remove a +1/+1 counter from this creature and sacrifice this creature',
    'Remove a +1/+1 counter from this creature then draw a card',
])
def test_unsupported_whole_counter_cost_rejects_without_partial_payment(text):
    state, source, _ = board(1, funded=True)
    if text == '{T}, Remove a +1/+1 counter from this creature':
        # Now supported grammar; this retained creature must first be ready to tap.
        assert costs.parse_activated_cost(text) == costs.ActivatedCost(
            tap_source=True, remove_source_counters=1, remove_counter_kind='+1/+1')
        before = snap(state)
        assert not costs.activated_cost_available(state, 1, source, text)
        assert not costs.apply_activated_costs(state, 1, source, text)
        assert snap(state) == before
        state.cards[source].summoning_sick = False
        before = snap(state)
        assert costs.activated_cost_available(state, 1, source, text)
        assert snap(state) == before
        assert costs.apply_activated_costs(state, 1, source, text)
        assert state.cards[source].tapped and state.cards[source].counters['+1/+1'] == 2
        assert state.players[1].mana_pool == {'C': 4}
        assert not state.stack
        paid = snap(state)
        assert not costs.apply_activated_costs(state, 1, source, text)
        assert snap(state) == paid
        return
    before = snap(state)
    assert not costs.parse_activated_cost(text).supported
    assert not costs.activated_cost_available(state, 1, source, text)
    assert not costs.apply_activated_costs(state, 1, source, text)
    assert snap(state) == before


def test_numeric_conversion_failure_never_falls_back_to_one_counter():
    # Pure hostile parser input, not card Oracle or a claimed supported quantity.
    import sys
    limit = sys.get_int_max_str_digits()
    if limit:
        text = 'Remove ' + '9' * (limit+1) + ' +1/+1 counters from this creature'
        assert not costs.parse_activated_cost(text).supported


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('problem', ['reserved', 'foreign', 'missing_membership', 'boolean', 'float', 'negative'])
def test_source_resource_validation_is_typed_reserved_and_query_pure(seat, problem):
    state, source, _ = board(seat)
    reserved = ()
    if problem == 'reserved':
        reserved = (source,)
    elif problem == 'foreign':
        state.cards[source].controller = 3-seat
    elif problem == 'missing_membership':
        state.players[seat].battlefield.remove(source)
    else:
        state.cards[source].counters['+1/+1'] = {'boolean': True, 'float': 3.0, 'negative': -1}[problem]
    # Malformed resources are controlled validation seams, not lawful priority positions.
    before = snap(state)
    assert not costs.activated_cost_available(state, seat, source, literal_cost(state, source),
                                              unavailable_resources=reserved)
    assert not costs.apply_activated_costs(state, seat, source, literal_cost(state, source),
                                         unavailable_resources=reserved)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mutation', ['sequence', 'counters', 'controller'])
def test_checked_copy_revalidates_counter_resource_after_payment_callback(seat, mutation, monkeypatch):
    state, source, _ = board(seat)
    def controlled_callback(candidate, *args, **kwargs):
        # Fault-injected internal payment seam, NOT a canonical mana ability episode.
        card = candidate.cards[source]
        if mutation == 'sequence':
            card.zone_change_sequence += 1
        elif mutation == 'counters':
            card.counters['+1/+1'] = 0
        else:
            card.controller = 3-seat
        return True
    monkeypatch.setattr(costs, '_pay_activated_mana', controlled_callback)
    before = snap(state)
    with pytest.raises(ActionRejected, match='Source counter payment changed'):
        act(state, seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 1,
                         'targets': {'target_player': 3-seat}})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [1, 3])
def test_actual_announcement_pays_counter_and_retains_true_stack_source(seat, count, tmp_path):
    state, source, _ = board(seat, counters=count)
    reference = object_incarnation(state.cards[source])
    sequence = state.cards[source].zone_change_sequence
    before = snap(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert any(move.get('card_id') == source and move.get('ability_index') == 1 for move in moves)
    assert snap(state) == before
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 1,
                             'targets': {'target_player': 3-seat}})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == source
    assert state.stack[0].controller == seat and state.stack[0].effect_key == 'deal_damage'
    assert state.stack[0].payload['amount'] == 1
    assert state.players[3-seat].life == 20
    if count == 1:
        assert state.cards[source].zone == Zone.GRAVEYARD
        assert state.cards[source].zone_change_sequence == sequence+1
        assert state.players[seat].graveyard.count(source) == 1
        receipt = state.stack[0].payload['__source_lki']
        assert receipt['battlefield_incarnation'] == reference
        assert receipt['color_names'] == [] and receipt['counters']['+1/+1'] == 0
    else:
        assert state.cards[source].zone == Zone.BATTLEFIELD
        assert state.cards[source].zone_change_sequence == sequence
        assert state.cards[source].counters['+1/+1'] == count-1
    assert_private(restart(state, tmp_path, 'actual-cost-and-stack-only'))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_repeated_announcements_each_pay_once_before_resolution(seat, tmp_path):
    state, source, _ = board(seat, counters=3)
    action = {'type': 'activate_ability', 'card_id': source, 'ability_index': 1,
              'targets': {'target_player': 3-seat}}
    for count in (2, 1, 0):
        state = act(state, seat, action)
        assert len(state.stack) == 3-count
        assert state.players[3-seat].life == 20
        if count:
            assert state.cards[source].zone == Zone.BATTLEFIELD
            assert state.cards[source].counters['+1/+1'] == count
        else:
            assert state.cards[source].zone == Zone.GRAVEYARD
        state = restart(state, tmp_path, f'actual-announced-{count}')
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, action)
    assert snap(state) == before
    while state.stack:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.players[3-seat].life == 17
    assert_private(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [1, 3])
def test_actual_http_counter_payment_restart_private_and_atomic_root(repo, client, seat, count, tmp_path):
    import main
    seed_cache(repo, [{'card_name': 'Island'}])
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
        'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 160})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state, source, target = board(seat, counters=count)
    state.id = controller.state.id
    controller.state = state  # Explicit controlled canonical retained board, NOT cast/entry proof.
    controller.engine = RulesEngine()
    old_reference = object_incarnation(state.cards[source])
    old_sequence = state.cards[source].zone_change_sequence
    main._persist_active_match(repo, controller)
    path = '/matches/' + state.id
    moves = client.get(path + f'/legal-moves?player_id={seat}')
    assert moves.status_code == 200, moves.text
    assert any(move.get('card_id') == source and move.get('ability_index') == 1
               for move in moves.json()['moves'])
    action = {'type': 'activate_ability', 'card_id': source, 'ability_index': 1,
              'targets': {'target_player': 3-seat} if count == 1 else {'target_card_id': target}}
    invalids = [(3-seat, action), (seat, {**action, 'ability_index': 99}),
                (seat, {**action, 'targets': {'target_card_id': 'absent'}}),
                (seat, {**action, 'payment_choices': {'counter_amount': 0}})]
    for actor, invalid in invalids:
        before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
        rejected = client.post(path + '/action', json={'player_id': actor, 'action': invalid})
        assert rejected.status_code in (403, 422), rejected.text
        assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    paid = client.post(path + '/action', json={'player_id': seat, 'action': action})
    assert paid.status_code == 200, paid.text
    controller = main.ACTIVE_MATCHES[state.id]
    state = controller.state
    assert len(state.stack) == 1 and state.stack[0].effect_key == 'deal_damage'
    assert state.players[3-seat].life == 20
    if count == 1:
        assert state.cards[source].zone == Zone.GRAVEYARD
        assert state.cards[source].zone_change_sequence == old_sequence+1
        assert state.players[seat].graveyard.count(source) == 1
        assert state.stack[0].payload['__source_lki']['battlefield_incarnation'] == old_reference
    else:
        assert state.cards[source].counters['+1/+1'] == count-1
        assert state.cards[target].counters.get('__damage_marked', 0) == 0
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    main.ACTIVE_MATCHES.pop(state.id)
    main._restore_active_matches(repo, state.id)
    controller = main.ACTIVE_MATCHES[state.id]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    restart(controller.state, tmp_path, 'http-paid-fresh-process-snapshot')
    assert_private(controller.state)
    database = repo.session.get_bind().url.database
    if database:
        expected = tmp_path / 'http-restart-expected.json'
        expected.write_text(json.dumps({'match_id': state.id, 'root': before[0],
                                      'controller': before[1], 'sql': before[2]}))
        worker = Path(__file__).with_name('source_counter_http_restart_worker.py')
        process = subprocess.run([sys.executable, str(worker), database, str(expected)],
                                 capture_output=True, text=True, timeout=60,
                                 env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        (tmp_path / 'actual-http-fresh-process.log').write_text(process.stdout+process.stderr)
        assert process.returncode == 0, process.stdout+process.stderr
    while controller.state.stack:
        result = client.post(path + '/action', json={'player_id': controller.state.priority_player,
                                                     'action': {'type': 'pass_priority'}})
        assert result.status_code == 200, result.text
        controller = main.ACTIVE_MATCHES[state.id]
    if count == 1:
        assert controller.state.players[3-seat].life == 19
    else:
        assert controller.state.cards[target].counters['__damage_marked'] == 1
    before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    main.ACTIVE_MATCHES.pop(state.id)
    main._restore_active_matches(repo, state.id)
    assert (snap(main.ACTIVE_MATCHES[state.id].state),
            main._controller_snapshot(main.ACTIVE_MATCHES[state.id]), sql_facts(repo)) == before
    assert_private(main.ACTIVE_MATCHES[state.id].state)
    (tmp_path / 'actual-http-resolved.json').write_text(json.dumps(before[0], sort_keys=True))
