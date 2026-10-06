"""Public-schema consumer guard, preserving canonical whole-view chosen actions."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from training.environment import TrainingEnvironment, decode_action
from tests.test_nonmana_intent_audit import scenario, trusted_execution
from tests.test_nonmana_null_intent_audit import execute_http
from tests.test_training_selected_mana import mana_position
from tests.test_training_choice_coverage import card, cast
from tests.test_training_environment import resolve
from tests.test_linked_damage_targets import raw_card
from tests.test_selected_mana_http import game, retain, rejected, forbid_external_network


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
@pytest.mark.parametrize('choice', ['target', 'cost', 'zone', 'face'])
@pytest.mark.parametrize('is_null', [False, True])
def test_requested_extras_reject_before_normalization(game, monkeypatch, seat, family, choice, is_null):
    env, action, hint, target, _ = scenario(seat, family)
    field, value = {
        'target': ('target_card_id', target),
        'cost': ('payment_choices', {'discard_card_ids': [action['card_id']]}) if family == 'spell' else
                ('cost_choice', {'id': 'unoffered-cost'}),
        'zone': ('source_zone', 'graveyard'), 'face': ('face_index', 19),
    }[choice]
    request = {**hint, **action, field: None if is_null else value}
    before = env.snapshot()
    client, match = game
    retain(match, env)
    rejected(client, match, {**action, field: request[field]}, seat)
    with pytest.raises(ActionRejected):
        env.lookup({**action, field: request[field]})
    def normalization_must_not_run(_):
        pytest.fail('Unsupported requested key reached complete_action')
    monkeypatch.setattr('ai.action_contract.complete_action', normalization_must_not_run)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['bolt_player', 'bolt_creature', 'officer', 'dreams', 'warrens'])
def test_actual_whole_legal_view_retains_chosen_fields_and_executes(game, seat, kind):
    if kind in {'bolt_player', 'bolt_creature', 'officer'}:
        family = 'ability' if kind == 'officer' else 'spell'
        env, action, hint, creature, top = scenario(seat, family)
        if kind == 'bolt_creature':
            action['targets'] = {'target_card_id': creature}
    else:
        env = mana_position(seat)
        env._state.players[seat].mana_pool = {color: 20 for color in 'WUBRGC'}
        if kind == 'dreams':
            source = card(env, 'Sickening Dreams', seat)
            selected = card(env, 'Opt', seat)
            untouched = card(env, 'Savannah Lions', seat)
            action = cast(env, source, {'x_value': 1})
            action['cost_choice']['discard_card_ids'] = [selected]
        else:
            rows = json.loads((Path(__file__).parent / 'fixtures/qualified_spell_costs.json').read_text())
            row = next(row for row in rows if row['name'] == 'Goblin Warrens')
            source = raw_card(env._state, row, seat, Zone.BATTLEFIELD).id
            row = next(row for row in rows if row['name'] == 'Goblin Instigator')
            resources = [raw_card(env._state, row, seat, Zone.BATTLEFIELD).id for _ in range(3)]
            action = {'type': 'activate_ability', 'card_id': source, 'ability_index': 0,
                      'targets': {}, 'payment_choices': {'sacrifice_card_ids': resources[:2]}}
        hint = next(move for move in env._rules.legal_moves(deepcopy(env._state), seat)
                    if move['type'] == action['type'] and move['card_id'] == action['card_id']
                    and move.get('ability_index') == action.get('ability_index'))
    display = ({'card_name', 'mana_cost', 'cost_options', 'target_hints'} if action['type'] == 'cast_spell' else
               {'card_name', 'mana_cost', 'ability_label', 'payment_options', 'activation_costs',
                'hybrid_symbols', 'target_hints'})
    assert display.issubset(hint)
    intent = {**hint, **deepcopy(action)}
    untouched_intent = deepcopy(intent)
    before = env.snapshot()
    normalized = decode_action(env.lookup_intent(intent)['id'])
    assert env.lookup_intent(intent) == env.lookup(action)
    assert normalized['targets'] == action['targets']
    if 'cost_choice' in action:
        assert normalized['cost_choice'] == action['cost_choice']
    if 'ability_index' in action:
        assert normalized['ability_index'] == action['ability_index']
    if 'payment_choices' in action:
        assert normalized['payment_choices'] == action['payment_choices']
    assert normalized == decode_action(env.lookup(action)['id'])
    assert intent == untouched_intent and env.snapshot() == before
    if kind == 'officer':
        trusted_execution(env, normalized, family, creature, top)
    fork = TrainingEnvironment()
    fork.restore(before)
    fork.step(normalized)
    resolve(fork)
    client, match = game
    state = execute_http(client, match, env, normalized)
    for executed in (fork._state, state):
        if kind == 'bolt_player':
            assert executed.players[3-seat].life == 17
            assert creature in executed.players[3-seat].battlefield
        elif kind == 'bolt_creature':
            assert executed.players[3-seat].life == 20
            assert creature in executed.players[3-seat].graveyard
        elif kind == 'dreams':
            assert selected in executed.players[seat].graveyard
            assert untouched in executed.players[seat].hand
            assert [executed.players[p].life for p in (1, 2)] == [19, 19]
        elif kind == 'warrens':
            assert set(resources[:2]).issubset(executed.players[seat].graveyard)
            assert resources[2] in executed.players[seat].battlefield
            tokens = [executed.cards[cid] for cid in executed.players[seat].battlefield
                      if executed.cards[cid].is_token]
            assert len(tokens) == 3 and all('Goblin' in token.type_line for token in tokens)
        else:
            assert executed.pending_mechanic_choice
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
@pytest.mark.parametrize('field', ['outputs', 'required_choices', 'unknown_choice', 'cast_variant'])
def test_only_family_qualified_display_metadata_is_allowed(seat, family, field):
    env, action, hint, _, _ = scenario(seat, family)
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent({**hint, **action, field: None})
    assert env.snapshot() == before
