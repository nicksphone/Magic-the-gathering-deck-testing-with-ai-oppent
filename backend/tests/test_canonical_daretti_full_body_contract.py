"""Public canonical Daretti contracts; no reduced Oracle or named-card recipes."""
import json
import random
from copy import deepcopy
from pathlib import Path

import pytest

from effects.handlers import destroy_permanent, sacrifice
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import (
    CardInstance, MatchState, PlayerState, Step, Zone,
    assign_static_order_on_battlefield_entry,
)
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.closed_loyalty import compile_body
from rules_engine.engine import RulesEngine
from rules_engine.linked_discard import linked_discard_effect
from rules_engine.oracle_effects import extract_loyalty_abilities
from rules_engine.printed_body import printed_body_gaps
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.type_effects import add_type_effect
from rules_engine.zone_actions import discard_selected


NAME = 'Daretti, Scrap Savant'
RUMMAGE = 'Discard up to two cards, then draw that many cards.'
RECYCLE = ('Sacrifice an artifact. If you do, return target artifact card '
           'from your graveyard to the battlefield.')
EMBLEM = ('Whenever an artifact is put into your graveyard from the battlefield, '
          'return that card to the battlefield at the beginning of the next end step.')
ULTIMATE = 'You get an emblem with "' + EMBLEM + '"'
RAW_BODY = ('+2: ' + RUMMAGE + '\n\u22122: ' + RECYCLE
            + '\n\u221210: ' + ULTIMATE + '\n' + NAME + ' can be your commander.')
ROW = next(row for row in json.loads(
    (Path(__file__).parent / 'fixtures/discard_history.json').read_text())
    if row['name'] == NAME)


def put(state, cid, zone, *, owner=1, controller=None, types=('Artifact',), text=''):
    controller = owner if controller is None else controller
    card = CardInstance(cid, cid, owner, controller, zone, list(types),
                        oracle_text=text, type_line=' '.join(types),
                        power=2 if 'Creature' in types else None,
                        toughness=2 if 'Creature' in types else None)
    state.cards[cid] = card
    holder = controller if zone == Zone.BATTLEFIELD else owner
    getattr(state.players[holder], zone.value).append(cid)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, cid)
    return card


def board(seat=1, *, loyalty=3):
    state = MatchState('public-daretti', {pid: PlayerState(pid, 'P' + str(pid))
                                        for pid in (1, 2)}, {}, [], rng=random.Random(44))
    state.pregame_pending = False
    state.turn = 5
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    source = put(state, 'daretti', Zone.BATTLEFIELD, owner=seat,
                 types=('Planeswalker',), text=ROW['oracle_text'])
    source.name, source.type_line, source.mana_cost = NAME, ROW['type_line'], ROW['mana_cost']
    source.colors, source.loyalty = list(ROW['colors']), loyalty
    for pid in (1, 2):
        for index in range(8):
            put(state, f'library-{pid}-{index}', Zone.LIBRARY, owner=pid, types=('Land',))
    return state


def restored(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def activate(state, seat, index, targets=None):
    return checked_action(state, RulesEngine(), seat, {
        'type': 'activate_loyalty', 'card_id': 'daretti',
        'ability_index': index, 'targets': targets or {},
    })


def resolve_once(state):
    from dataclasses import asdict
    assert not state.pending_mechanic_choice and not state.pending_replacement_choice
    item = state.stack[-1]
    result = resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice or state.pending_replacement_choice
    if pending:
        assert result is False
        assert pending.get('resolving_item') == asdict(item)
    else:
        assert result is True
    return state


def choose(state, seat, ids):
    return checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ids})


def get_emblem():
    state = board(loyalty=10)
    state = resolve_once(activate(state, 1, 2))
    assert len(state.emblems) == 1
    emblem_id = state.emblems[0]
    assert state.cards[emblem_id].zone == Zone.COMMAND
    assert state.cards[emblem_id].oracle_text == EMBLEM
    return restored(state), emblem_id


def advance_to_end(state, turn):
    for _ in range(20):
        if state.step == Step.END_STEP and state.turn == turn:
            return
        assert not state.stack and not state.pending_mechanic_choice
        RulesEngine().next_step(state)
    pytest.fail('Native step progression did not reach the next end step')


def test_complete_raw_body_admits_all_three_without_erasing_commander_clause():
    state = board()
    source = state.cards['daretti']
    assert ROW['oracle_text'] == RAW_BODY
    before = serialize_match_snapshot(state)
    program = compile_body(source.oracle_text, source.name)
    assert program is not None
    assert [ability['delta'] for ability in program['abilities']] == [2, -2, -10]
    assert [ability['text'] for ability in program['abilities']] == [RUMMAGE, RECYCLE, ULTIMATE]
    assert program['companions'] == [NAME + ' can be your commander.']
    assert printed_body_gaps(source) == ()
    assert serialize_match_snapshot(state) == before


def test_same_full_program_is_not_a_named_card_recipe():
    state = board()
    source = state.cards['daretti']
    source.name = 'Public Scrap Walker'
    source.oracle_text = RAW_BODY.replace(NAME + ' can be your commander.',
                                         source.name + ' can be your commander.')
    abilities = extract_loyalty_abilities(source)
    assert [ability['delta'] for ability in abilities] == [2, -2, -10]
    assert [ability['text'] for ability in abilities] == [RUMMAGE, RECYCLE, ULTIMATE]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 2])
def test_full_body_plus_two_uses_bounded_native_discard_and_actual_draw(seat, count):
    state = board(seat)
    hand = [put(state, f'hand-{index}', Zone.HAND, owner=seat, types=('Land',)).id
            for index in range(3)]
    state = resolve_once(activate(state, seat, 0))
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'discard'
    assert (pending['min_count'], pending['count']) == (0, 2)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choose(state, seat, hand)
    assert serialize_match_snapshot(state) == before
    state = choose(restored(state), seat, hand[:count])
    assert state.cards['daretti'].loyalty == 5
    assert state.cards['daretti'].oracle_text == RAW_BODY
    assert state.discards_this_turn[seat] == count
    assert state.draws_this_turn[seat] == count
    assert len(state.players[seat].hand) == 3
    assert all(cid in state.players[seat].graveyard for cid in hand[:count])
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_minus_two_announces_graveyard_target_then_mandatory_artifact_choice(seat):
    state = board(seat)
    put(state, 'return-me', Zone.GRAVEYARD, owner=seat)
    put(state, 'sacrifice-me', Zone.BATTLEFIELD, owner=seat)
    put(state, 'nonartifact', Zone.BATTLEFIELD, owner=seat, types=('Land',))
    put(state, 'opponent-artifact', Zone.BATTLEFIELD, owner=3-seat)
    state = activate(state, seat, 1, {'target_card_id': 'return-me'})
    assert state.cards['daretti'].loyalty == 1
    assert state.cards['sacrifice-me'].zone == Zone.BATTLEFIELD
    assert not state.pending_mechanic_choice
    state = resolve_once(state)
    assert set(state.pending_mechanic_choice['options']) == {'sacrifice-me'}
    assert state.pending_mechanic_choice['count'] == 1
    for ids in ([], ['nonartifact'], ['opponent-artifact'], ['sacrifice-me'] * 2):
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            choose(state, seat, ids)
        assert serialize_match_snapshot(state) == before
    state = choose(restored(state), seat, ['sacrifice-me'])
    assert state.cards['sacrifice-me'].zone == Zone.GRAVEYARD
    assert state.cards['return-me'].zone == Zone.BATTLEFIELD
    assert state.cards['return-me'].controller == seat
    assert not state.pending_mechanic_choice and not state.stack


def test_minus_two_without_an_artifact_cannot_pay_resolution_cost_or_return_target():
    state = board()
    put(state, 'return-me', Zone.GRAVEYARD)
    state = resolve_once(activate(state, 1, 1, {'target_card_id': 'return-me'}))
    assert state.cards['daretti'].loyalty == 1
    assert state.cards['return-me'].zone == Zone.GRAVEYARD
    assert not state.pending_mechanic_choice and not state.stack


def test_minus_two_same_id_graveyard_reentry_fizzles_before_sacrificing():
    state = board()
    put(state, 'return-me', Zone.GRAVEYARD)
    put(state, 'sacrifice-me', Zone.BATTLEFIELD)
    state = activate(state, 1, 1, {'target_card_id': 'return-me'})
    resolve_effect(state, 1, 'return_from_graveyard', {'target_card_id': 'return-me'})
    assert discard_selected(state, 1, ['return-me'])
    state = resolve_once(restored(state))
    assert state.cards['return-me'].zone == Zone.GRAVEYARD
    assert state.cards['sacrifice-me'].zone == Zone.BATTLEFIELD
    assert not state.pending_mechanic_choice and not state.stack


def test_minus_ten_emblem_survives_its_planeswalker_leaving_at_zero_loyalty():
    state, emblem_id = get_emblem()
    assert state.cards['daretti'].zone == Zone.GRAVEYARD
    assert state.cards['daretti'].oracle_text == RAW_BODY
    assert state.cards[emblem_id].owner == state.cards[emblem_id].controller == 1
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('owner,controller,want', [(1, 1, 1), (1, 2, 1), (2, 1, 0)])
def test_emblem_matches_your_graveyard_not_former_artifact_controller(owner, controller, want):
    state, emblem_id = get_emblem()
    put(state, 'artifact', Zone.BATTLEFIELD, owner=owner, controller=controller)
    sacrifice(state, controller, {'target_card_id': 'artifact'})
    assert state.cards['artifact'].zone == Zone.GRAVEYARD
    triggers = [item for item in state.stack if item.source_card_id == emblem_id]
    assert len(triggers) == want
    assert not state.delayed_triggers


@pytest.mark.parametrize('death_step', [Step.POSTCOMBAT_MAIN, Step.END_STEP])
def test_emblem_creates_counterable_death_then_next_end_step_return(death_step):
    state, emblem_id = get_emblem()
    state.step = death_step
    put(state, 'artifact', Zone.BATTLEFIELD)
    destroy_permanent(state, 2, {'target_card_id': 'artifact'})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == emblem_id
    assert state.cards['artifact'].zone == Zone.GRAVEYARD
    assert not state.delayed_triggers
    state = resolve_once(restored(state))
    assert not state.stack and len(state.delayed_triggers) == 1
    due_turn = 5 if death_step == Step.POSTCOMBAT_MAIN else 6
    if death_step == Step.END_STEP:
        RulesEngine().next_step(state)
        assert not state.stack and len(state.delayed_triggers) == 1
    advance_to_end(state, due_turn)
    assert not state.delayed_triggers and len(state.stack) == 1
    assert state.stack[0].source_card_id == emblem_id
    assert state.cards['artifact'].zone == Zone.GRAVEYARD
    state = resolve_once(restored(state))
    assert state.cards['artifact'].zone == Zone.BATTLEFIELD
    assert state.cards['artifact'].controller == 1
    assert not state.stack and not state.delayed_triggers


@pytest.mark.parametrize('reentry_stage', ['before-death-trigger', 'after-delay-created'])
def test_emblem_delayed_return_never_follows_same_id_graveyard_reentry(reentry_stage):
    state, _ = get_emblem()
    put(state, 'artifact', Zone.BATTLEFIELD)
    sacrifice(state, 1, {'target_card_id': 'artifact'})
    if reentry_stage == 'after-delay-created':
        state = resolve_once(state)
    resolve_effect(state, 1, 'return_from_graveyard', {'target_card_id': 'artifact'})
    assert discard_selected(state, 1, ['artifact'])
    if reentry_stage == 'before-death-trigger':
        state = resolve_once(state)
    state.step = Step.POSTCOMBAT_MAIN
    advance_to_end(state, 5)
    assert len(state.stack) == 1
    state = resolve_once(restored(state))
    assert state.cards['artifact'].zone == Zone.GRAVEYARD
    assert not state.stack and not state.delayed_triggers


def test_emblem_uses_pre_lki_artifact_type_and_does_not_require_artifact_on_return():
    state, emblem_id = get_emblem()
    put(state, 'temporary-artifact', Zone.BATTLEFIELD, types=('Creature',))
    add_type_effect(state, 'temporary-artifact', ['Artifact'])
    sacrifice(state, 1, {'target_card_id': 'temporary-artifact'})
    assert 'Artifact' not in state.cards['temporary-artifact'].types
    assert len(state.stack) == 1 and state.stack[0].source_card_id == emblem_id
    state = resolve_once(state)
    state.step = Step.POSTCOMBAT_MAIN
    advance_to_end(state, 5)
    state = resolve_once(restored(state))
    assert state.cards['temporary-artifact'].zone == Zone.BATTLEFIELD
    assert state.cards['temporary-artifact'].types == ['Creature']


@pytest.mark.parametrize('mutation', ['new-line', 'plus-two-tail', 'minus-two-tail',
                                      'emblem-tail', 'wrong-commander-source'])
def test_unknown_suffix_or_unbound_companion_closes_entire_card_atomically(mutation):
    state = board(loyalty=10)
    put(state, 'return-me', Zone.GRAVEYARD)
    source = state.cards['daretti']
    if mutation == 'new-line':
        source.oracle_text += '\nWhenever you draw a card, venture into the dungeon.'
    elif mutation == 'plus-two-tail':
        source.oracle_text = RAW_BODY.replace(RUMMAGE, RUMMAGE + ' Venture into the dungeon.')
    elif mutation == 'minus-two-tail':
        source.oracle_text = RAW_BODY.replace(RECYCLE, RECYCLE + ' Venture into the dungeon.')
    elif mutation == 'emblem-tail':
        source.oracle_text = RAW_BODY.replace(EMBLEM, EMBLEM + ' Venture into the dungeon.')
    else:
        source.oracle_text = RAW_BODY.replace(NAME + ' can be your commander.',
                                             'Some other walker can be your commander.')
    before = serialize_match_snapshot(state)
    assert compile_body(source.oracle_text, source.name) is None
    assert extract_loyalty_abilities(source) == []
    assert printed_body_gaps(source)
    assert not [move for move in RulesEngine().legal_moves(state, 1)
                if move['type'] == 'activate_loyalty']
    for index in range(3):
        with pytest.raises(ActionRejected):
            activate(state, 1, index, {'target_card_id': 'return-me'} if index == 1 else {})
        assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('count', [0, 1, 2])
def test_existing_native_linked_rummage_primitive_is_reusable_without_card_admission(count):
    state = board()
    hand = [put(state, f'hand-{index}', Zone.HAND, types=('Land',)).id for index in range(3)]
    data = linked_discard_effect(RUMMAGE)
    assert data == {'up_to': True, 'amount': 2, 'followup_effect': {
        'effect_key': 'draw_cards', 'payload': {}, 'count_field': 'amount'}}
    resolve_effect(state, 1, 'discard_cards', {'self_discard': True, **deepcopy(data)})
    state = choose(restored(state), 1, hand[:count])
    assert state.discards_this_turn[1] == state.draws_this_turn[1] == count
    assert len(state.players[1].hand) == 3
    assert state.cards['daretti'].oracle_text == RAW_BODY
