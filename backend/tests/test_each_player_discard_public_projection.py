"""Paid public canonical sibling controls; no injected pending choices or SQL."""
import ast
from copy import deepcopy
from dataclasses import asdict
import json

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.optional_reveal import public_choice
from rules_engine.printed_body import printed_body_gaps
from rules_engine.stack_engine import resolve_top_of_stack
from training.environment import TrainingEnvironment
from test_discard_continuation_projection import BACKEND, CANONICAL, CONTROLLER, main_prompt


def delirium_printed_surface():
    # Literal full printed surface already retained in the immutable original test.
    tree = ast.parse((BACKEND / 'tests/test_each_player_discard.py').read_text())
    setup = next(node for node in tree.body if getattr(node, 'name', None) == '_state')
    fields = {}
    for node in setup.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Attribute) and ast.unparse(target.value) == 'spell':
                fields[target.attr] = ast.literal_eval(node.value)
    assert fields == {'name': 'Delirium Skeins', 'mana_cost': '{2}{B}',
                      'type_line': 'Sorcery', 'types': ['Sorcery'],
                      'oracle_text': 'Each player discards three cards.'}
    return fields


DELIRIUM = delirium_printed_surface()
WHEEL = next(row for row in json.loads((BACKEND / 'tests/fixtures/wheel_draw.json').read_text())
             if row['name'] == 'Wheel of Fortune')
PUBLIC_KEYS = {'kind', 'player_id', 'label', 'count'}
ACTOR_KEYS = PUBLIC_KEYS | {'type', 'options', 'option_labels', 'option_type_lines'}


def paid_state(seat, row, sizes=(4, 5)):
    state = CANONICAL.board(seat)
    state.id = 'generated-public-sibling'
    state.players[seat].battlefield.remove('daretti')
    del state.cards['daretti']
    spell = CANONICAL.put(state, 'generated-paid-spell', Zone.HAND, owner=seat,
                          types=('Sorcery',), text=row['oracle_text'])
    spell.name, spell.type_line, spell.mana_cost = row['name'], row['type_line'], row['mana_cost']
    spell.colors = ['B'] if row['name'] == 'Delirium Skeins' else list(row['colors'])
    assert printed_body_gaps(spell) == ()
    hands = {pid: [CANONICAL.put(state, f'generated-hidden-{pid}-{i}', Zone.HAND,
                                  owner=pid, types=('Land',)).id for i in range(size)]
             for pid, size in ((seat, sizes[0]), (3-seat, sizes[1]))}
    state.players[seat].mana_pool = {'B' if row['name'] == 'Delirium Skeins' else 'R': 1, 'C': 2}
    before = deepcopy(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id})
    assert state.cards[spell.id].oracle_text == row['oracle_text']
    assert state.cards[spell.id].zone == Zone.STACK
    assert not any(state.players[seat].mana_pool.values())
    assert before['cards'][spell.id]['oracle_text'] == row['oracle_text']
    return state, spell.id, hands


def choose(state, actor, ids):
    return checked_action(state, RulesEngine(), actor,
                          {'type': 'choose_mechanic', 'card_ids': list(ids)})


def chosen(hands, pid):
    return list(reversed(hands[pid][-min(3, len(hands[pid])):]))


def paused(seat, stage, restore, sizes=(4, 5)):
    state, spell, hands = paid_state(seat, DELIRIUM, sizes)
    popped = state.stack[-1]
    assert resolve_top_of_stack(state) is False
    frame = asdict(popped)
    if stage == 'second':
        state = choose(state, seat, chosen(hands, seat))
    if restore:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    actor = seat if stage == 'first' else 3-seat
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'each_player_discard'
    assert pending['player_id'] == actor and pending['effect_controller'] == seat
    assert pending['options'] == hands[actor]
    assert pending['resolving_item'] == frame
    assert pending['effect_payload']['selected_cards'] == (
        {} if stage == 'first' else {str(seat): chosen(hands, seat)})
    assert {pid: state.players[pid].hand for pid in (1, 2)} == hands
    assert state.discards_this_turn == {1: 0, 2: 0}
    assert not any(state.players[pid].graveyard for pid in (1, 2))
    assert state.cards[spell].zone == Zone.STACK
    return state, spell, hands, actor


def prompt(state):
    pending = state.pending_mechanic_choice
    return {'kind': 'each_player_discard', 'player_id': pending['player_id'],
            'label': 'Choose cards to discard', 'count': pending['count']}


def projection(state, boundary):
    if boundary == 'public-choice':
        return public_choice(state.pending_mechanic_choice)
    if boundary == 'spectator-serializer':
        # look_players does not redact ordinary hands in the local-match codec.
        view = serialize_match(state, look_players=())
        assert all(view['players'][pid]['hand_count'] == len(state.players[pid].hand) for pid in (1, 2))
        return view['pending_mechanic_choice']
    return main_prompt(state)


def finish(state, seat, hands, spell):
    while state.pending_mechanic_choice:
        before = deepcopy(serialize_match_snapshot(state))
        actor = state.pending_mechanic_choice['player_id']
        previous = state
        state = choose(state, actor, chosen(hands, actor))
        assert serialize_match_snapshot(previous) == before
    assert not state.stack
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.cards[spell].oracle_text == DELIRIUM['oracle_text']
    assert state.draws_this_turn == {1: 0, 2: 0}
    for pid in (1, 2):
        ids = chosen(hands, pid)
        assert state.players[pid].graveyard == ids + ([spell] if pid == seat else [])
        assert state.players[pid].hand == [cid for cid in hands[pid] if cid not in ids]
        assert state.discards_this_turn[pid] == len(ids)
    assert sum(line == 'Delirium Skeins resolves.' for line in state.log) == 1
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stage', ['first', 'second'])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('boundary', ['public-choice', 'spectator-serializer', 'main-controller'])
def test_paid_each_player_public_prompt_hides_both_private_selections_and_frame(
        seat, stage, restore, boundary):
    state, spell, hands, _ = paused(seat, stage, restore)
    before = deepcopy(serialize_match_snapshot(state))
    pending, options = state.pending_mechanic_choice, state.pending_mechanic_choice['options']
    payload, frame = pending['effect_payload'], pending['resolving_item']
    view = projection(state, boundary)
    assert serialize_match_snapshot(state) == before
    assert state.pending_mechanic_choice is pending and pending['options'] is options
    assert pending['effect_payload'] is payload and pending['resolving_item'] is frame
    assert set(view) == PUBLIC_KEYS and view == prompt(state)
    assert all(cid not in json.dumps(view) for ids in hands.values() for cid in ids)
    finish(state, seat, hands, spell)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stage', ['first', 'second'])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('boundary', ['public-choice', 'spectator-serializer', 'main-controller'])
def test_each_player_public_view_writes_cannot_change_owned_pending_root(
        seat, stage, restore, boundary):
    state, spell, hands, _ = paused(seat, stage, restore)
    before = deepcopy(serialize_match_snapshot(state))
    pending = state.pending_mechanic_choice
    view = projection(state, boundary)
    view['label'], view['count'], view['generated_display_extension'] = 'Generated alternate prompt', 0, True
    assert serialize_match_snapshot(state) == before
    assert state.pending_mechanic_choice is pending
    finish(state, seat, hands, spell)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stage', ['first', 'second'])
@pytest.mark.parametrize('restore', [False, True])
def test_existing_each_player_actor_allowlist_options_and_write_isolation_are_preserved(
        seat, stage, restore):
    state, spell, hands, actor = paused(seat, stage, restore)
    before = deepcopy(serialize_match_snapshot(state))
    assert RulesEngine().legal_moves(state, 3-actor) == []
    move, = RulesEngine().legal_moves(state, actor)
    assert set(move) == ACTOR_KEYS
    assert move == {**prompt(state), 'type': 'choose_mechanic', 'options': hands[actor],
                    'option_labels': {cid: cid for cid in hands[actor]},
                    'option_type_lines': {cid: 'Land' for cid in hands[actor]}}
    move['options'].append('generated-not-an-authorized-choice')
    move['option_labels'][hands[actor][0]] = 'Generated alternate label'
    move['option_type_lines'].clear()
    assert serialize_match_snapshot(state) == before
    finish(state, seat, hands, spell)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('sizes', [(1, 2), (4, 5)])
def test_native_simultaneous_discard_commits_only_after_both_actual_choices(seat, restore, sizes):
    state, spell, hands, actor = paused(seat, 'first', restore, sizes)
    before = deepcopy(serialize_match_snapshot(state))
    with pytest.raises(ActionRejected):
        choose(state, 3-actor, chosen(hands, 3-actor))
    with pytest.raises(ActionRejected):
        choose(state, actor, [])
    assert serialize_match_snapshot(state) == before
    state = choose(state, actor, chosen(hands, actor))
    assert all(state.players[pid].hand == hands[pid] for pid in (1, 2))
    assert state.discards_this_turn == {1: 0, 2: 0}
    assert state.pending_mechanic_choice['player_id'] == 3-seat
    assert state.pending_mechanic_choice['effect_payload']['selected_cards'] == {str(seat): chosen(hands, seat)}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    finish(state, seat, hands, spell)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stage', ['first', 'second'])
@pytest.mark.parametrize('restore', [False, True])
def test_whole_each_player_actor_intent_is_explicit_pure_and_replayable(seat, stage, restore):
    state, spell, hands, actor = paused(seat, stage, restore)
    env = TrainingEnvironment()
    env._state = state
    before = deepcopy(env.snapshot())
    hint, = RulesEngine().legal_moves(state, actor)
    action = {'type': 'choose_mechanic', 'card_ids': chosen(hands, actor)}
    intent = {**deepcopy(hint), **deepcopy(action)}
    unchanged = deepcopy(intent)
    normalized = env.lookup_intent(intent, actor)
    assert normalized == env.lookup(action, actor)
    assert normalized['action'] == action and intent == unchanged
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint, actor)
    with pytest.raises(ActionRejected):
        env.lookup_intent(intent, 3-actor)
    assert env.snapshot() == before
    fork, replay = TrainingEnvironment(), TrainingEnvironment()
    fork._state = deserialize_match_snapshot(before['state'])
    replay._state = deserialize_match_snapshot(before['state'])
    assert fork.step(normalized['action'], actor) == replay.step(action, actor)
    assert fork.snapshot() == replay.snapshot()
    finish(fork._state, seat, hands, spell)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('sizes', [(1, 2), (4, 5)])
def test_paid_complete_wheel_all_hand_rule_does_not_fabricate_a_discard_prompt(seat, restore, sizes):
    assert WHEEL['oracle_text'] == 'Each player discards their hand, then draws seven cards.'
    state, spell, hands = paid_state(seat, WHEEL, sizes)
    item = state.stack[-1]
    assert item.effect_key == 'each_player_discard' and item.payload['all_hand'] is True
    assert item.payload['draw_followup'] == {'kind': 'fixed', 'amount': 7}
    if restore:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state) is True
    assert not state.pending_mechanic_choice and not state.stack
    assert public_choice(state.pending_mechanic_choice) is None
    assert serialize_match(state, look_players=())['pending_mechanic_choice'] is None
    match = CONTROLLER.MatchController(
        state=state, rules=RulesEngine(), controllers={1: 'human', 2: 'human'}, ai={}, mode='local',
        deck_ids=(None, None), mainboards={1: [], 2: []}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=1)
    assert CONTROLLER._serialize_match_controller(match)['pending_mechanic_choice'] is None
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.cards[spell].oracle_text == WHEEL['oracle_text']
    for pid in (1, 2):
        assert len(state.players[pid].hand) == 7 and len(state.players[pid].library) == 1
        assert state.discards_this_turn[pid] == len(hands[pid]) and state.draws_this_turn[pid] == 7
        assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in hands[pid])
    assert sum(line == 'Wheel of Fortune resolves.' for line in state.log) == 1
