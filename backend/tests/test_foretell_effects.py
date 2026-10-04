"""Canonical conditional spells and durable, public game-end reveals."""
import json
import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.state_based_actions import apply_state_based_actions
from tests.test_foretell import setup, CARDS
from tests.test_ai_recurring_engines import add, resolve
from tests.test_api_input_contracts import game, persist


def cast_position(name, seat, foretold):
    state, cid = setup(name, seat)
    if foretold:
        state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
        state.turn += 1
    state.players[seat].mana_pool = {'C': 12, 'W': 4, 'B': 4}
    return state, cid


def cast(state, cid, seat, foretold, targets=None):
    return checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': cid,
                          'from_exile': foretold, 'targets': targets or {},
                          'cost_choice': {'id': 'foretell_0' if foretold else 'base'}})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foretold', [False, True])
@pytest.mark.parametrize('x', [0, 1, 3])
def test_token_replacement_uses_announced_x_only_when_foretold(seat, foretold, x):
    state, cid = cast_position('Starnheim Unleashed', seat, foretold)
    before = serialize_match_snapshot(state)
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move.get('card_id') == cid)
    assert bool(move['target_hints'].get('requires_x_value')) == foretold
    assert serialize_match_snapshot(state) == before
    state = cast(state, cid, seat, foretold, {'x_value': x} if foretold else {})
    assert state.stack[-1].effect_key == 'foretell_spell'
    assert state.cards[cid].oracle_text == CARDS['Starnheim Unleashed']['oracle_text']
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    tokens = [state.cards[t] for t in state.players[seat].battlefield if state.cards[t].is_token]
    assert len(tokens) == (x if foretold else 1)
    assert all(token.power == token.toughness == 4 and set(token.colors) == {'W'}
               and {'flying', 'vigilance'} <= set(token.keywords) for token in tokens)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foretold', [False, True])
@pytest.mark.parametrize('remove_target', [False, True])
def test_additional_scry_is_conditional_and_obeys_all_targets_illegal(seat, foretold, remove_target):
    state, cid = cast_position('Poison the Cup', seat, foretold)
    target = add(state, 'Grizzly Bears', 3-seat)
    state = cast(state, cid, seat, foretold, {'target_card_id': target.id})
    if remove_target:
        state.players[3-seat].battlefield.remove(target.id)
        state.cards[target.id].move_to_zone(Zone.GRAVEYARD)
        state.players[3-seat].graveyard.append(target.id)
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert bool(state.pending_mechanic_choice) == (foretold and not remove_target)
    if state.pending_mechanic_choice:
        assert state.pending_mechanic_choice['kind'] == 'scry'
        state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': []})
        if state.pending_mechanic_choice:
            state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic',
                                  'card_ids': state.pending_mechanic_choice['options']})
    assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('targets', [{}, {'x_value': -1}])
def test_alternative_cost_x_requires_a_nonnegative_explicit_declaration(seat, targets):
    state, cid = cast_position('Starnheim Unleashed', seat, True)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, cid, seat, True, targets)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_retains_announced_x_but_not_a_prior_foretold_card(seat):
    from effects.handlers import copy_spell
    state, cid = cast_position('Starnheim Unleashed', seat, True)
    state = cast(state, cid, seat, True, {'x_value': 3})
    original = state.stack[-1]
    copy_spell(state, seat, {'target_stack_id': original.id})
    assert state.stack[-1].payload['x_value'] == 3
    state = resolve(state)
    assert len(state.players[seat].battlefield) == 4  # Three original Angels, one from the copy.


@pytest.mark.parametrize('winner', [0, 1, 2])
def test_game_end_reveals_are_once_only_ordered_and_snapshot_durable(winner):
    state, cid = setup()
    state = checked_action(state, RulesEngine(), 1, {'type': 'foretell', 'card_id': cid})
    assert not any('reveals foretold' in line for line in state.log)
    state.winner = winner
    apply_state_based_actions(state)
    lines = [line for line in state.log if 'reveals foretold' in line]
    assert lines == ['Player A reveals foretold Behold the Multiverse at game end.']
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    apply_state_based_actions(state)
    assert [line for line in state.log if 'reveals foretold' in line] == lines


@pytest.mark.parametrize('name', ['Poison the Cup', 'Starnheim Unleashed'])
def test_supported_spell_variants_close_only_their_known_conditional_gap(name):
    from rules_engine.coverage import known_unsupported_mechanics
    assert 'foretell-related effect fidelity' not in known_unsupported_mechanics(CARDS[name]['oracle_text'], card_name=name)


@pytest.mark.parametrize('seat', [1, 2])
def test_foretold_spell_copy_retargets_its_normal_branch(seat):
    from effects.handlers import copy_spell
    state, cid = cast_position('Poison the Cup', seat, True)
    original_target = add(state, 'Grizzly Bears', 3-seat)
    new_target = add(state, 'Grizzly Bears', 3-seat)
    state = cast(state, cid, seat, True, {'target_card_id': original_target.id})
    copy_spell(state, seat, {'target_stack_id': state.stack[-1].id, 'may_choose_new_targets': True})
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic',
                          'card_ids': ['target_card_id:' + new_target.id]})
    # Resolve only the copy, then verify the original's target and conditional remain.
    for _ in range(2):
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.cards[new_target.id].zone == Zone.GRAVEYARD
    assert state.cards[original_target.id].zone == Zone.BATTLEFIELD
    assert not state.pending_mechanic_choice and len(state.stack) == 1
    state = resolve(state)
    assert state.pending_mechanic_choice['kind'] == 'scry'


@pytest.mark.parametrize('seat', [1, 2])
def test_foretold_x_cost_pays_each_x_and_rejects_insufficient_mana(seat):
    state, cid = cast_position('Starnheim Unleashed', seat, True)
    state.players[seat].mana_pool = {'C': 3, 'W': 1}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, cid, seat, True, {'x_value': 2})
    assert serialize_match_snapshot(state) == before
    state.players[seat].mana_pool = {'C': 6, 'W': 1}
    state = cast(state, cid, seat, True, {'x_value': 3})
    assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_http_end_reveal_persists_across_bo3_and_public_memory(game, seat):
    import main
    from persistence.db import engine
    from persistence.repository import Repository
    from sqlmodel import Session
    client, controller = game
    state, cid = setup(seat=seat)
    state.id = controller.state.id
    controller.state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    controller.best_of = controller.state.best_of = 3
    controller.state.players[seat].life = 0
    apply_state_based_actions(controller.state)
    with Session(engine) as session:
        repo = Repository(session)
        deck = repo.save_deck('Foretell history fixture', 'fixture',
                             [{'name': 'Behold the Multiverse', 'quantity': 60}], [], 'Control')
        controller.deck_ids = (deck.id, deck.id)
        main._post_step_finalize(controller, repo)
        history_id = repo.list_matches()[0].id
    persist(controller)
    endpoint = f'/matches/{state.id}'
    ended = client.get(endpoint).json()
    reveal = next(line for line in ended['log'] if ' reveals foretold ' in line)
    response = client.post(endpoint + '/next-game', json={'player_id': seat, 'play_first': True})
    assert response.status_code == 200, response.text
    assert response.json()['game_number'] == 2 and reveal in response.json()['log']
    assert 'Instant' in controller.seen_opponent_types[3-seat]
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        repo = Repository(session)
        main._restore_active_matches(repo, state.id)
        history = next(row for row in repo.list_matches() if row.id == history_id)
        assert json.loads(history.log_json).count(reveal) == 1
    assert reveal in client.get(endpoint).json()['log']


def test_bo3_log_trimming_keeps_reveals_outside_the_recent_tail(game):
    import main
    client, controller = game
    state, cid = setup()
    controller.state = checked_action(state, RulesEngine(), 1, {'type': 'foretell', 'card_id': cid})
    controller.state.winner = 2
    apply_state_based_actions(controller.state)
    reveal = next(line for line in controller.state.log if ' reveals foretold ' in line)
    controller.state.log.extend(['A later public event.'] * 100)
    controller.best_of = 3
    controller.current_game_recorded = True
    controller.state.score = {1: 0, 2: 1}
    main._start_next_game_state(controller)
    assert controller.state.log.count(reveal) == 1


def test_unrecognized_foretold_prefix_is_not_hidden_by_supported_scry_suffix():
    from rules_engine.foretell import spell_variants
    # Parser input only, not a fabricated card or a gameplay fixture.
    text = 'If this spell was foretold, unsupported clause. If this spell was foretold, scry 2.'
    assert spell_variants(text) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('archetype', ['Aggro', 'Burn', 'Midrange', 'Control', 'Tempo', 'Ramp',
                                      'Drain', 'Aristocrats', 'Reanimator', 'Tokens', 'Tribal',
                                      'Combo-lite', 'Counter-heavy', 'Removal-heavy'])
def test_ai_materializes_selected_foretold_x_cost_without_mutating_state(seat, difficulty, archetype):
    from ai.agent import AIAgent
    state, cid = cast_position('Starnheim Unleashed', seat, True)
    state.players[seat].mana_pool = {'C': 6, 'W': 1}
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move.get('card_id') == cid)
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty=difficulty, archetype=archetype)._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    assert not action.get('_invalid_ai_choice'), action
    assert action['cost_choice']['id'] == 'foretell_0'
    assert 1 <= action['targets']['x_value'] <= 3
    checked_action(state, RulesEngine(), seat, action)
