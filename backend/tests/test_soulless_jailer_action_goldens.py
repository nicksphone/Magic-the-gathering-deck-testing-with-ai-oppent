"""Paid canonical action goldens; seeded boards, no native storage or AI."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.costs import casting_method
from rules_engine.engine import RulesEngine
from rules_engine.loyalty_instructions import card_reference
from rules_engine.targeting import capture_announced_target_references
from test_soulless_jailer_query_contract import add, position, rows
from test_soulless_jailer_typed_query import extra_rows
from test_soulless_jailer_cost_method_admission import permissions_rows


@pytest.fixture(scope='module')
def history():
    raw = (Path(__file__).parent / 'fixtures/discard_history.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        '2f5c15ddc8a718546985d9893b7f806d88caf772fc2a5080799cd8cb694d40c5')
    data = {row['name']: row for row in json.loads(raw)}
    spells = (Path(__file__).parent / 'fixtures/surveil_mill.json').read_bytes()
    assert hashlib.sha256(spells).hexdigest() == (
        '21494138a89fdc03a399af13b1ca5112e4565f24da08ca29dd15bfb691422a70')
    data.update({row['name']: row for row in json.loads(spells)})
    return data


def board(seat):
    state = position(seat)
    state.turn = 5
    state.kept_hands = {1, 2}
    state.mechanic_choice_players = {1, 2}
    state.players[seat].mana_pool = {'W': 8, 'U': 0, 'B': 8, 'R': 4, 'G': 12, 'C': 20}
    return state


def seed(state, row, seat, zone):
    # Fixture-only board/resources; all subsequent frames and payments are engine-made.
    card = add(state, row, seat, zone)
    card.keywords = deepcopy(row.get('keywords', []))
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def root(state):
    return pickle.dumps(state, protocol=5)


def act(state, seat, action):
    before = root(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert root(state) == before
    assert result.winner is None
    return result


def rejected(state, seat, action):
    before = root(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert root(state) == before


def offer(state, seat, cid, method='base'):
    before = root(state)
    moves = [move for move in RulesEngine().legal_moves(state, seat)
             if move['type'] == 'cast_spell' and move.get('card_id') == cid
             and (move.get('cast_variant') == 'bestow') == (method == 'bestow')]
    assert root(state) == before
    assert moves
    return next(option['id'] for option in moves[0]['cost_options']
                if casting_method(option['id']) == method)


def cast(state, seat, cid, *, targets=None, method='base', option=None):
    action = {'type': 'cast_spell', 'card_id': cid,
              'cost_choice': {'id': option or offer(state, seat, cid, method)},
              'targets': targets or {}}
    if state.cards[cid].zone == Zone.GRAVEYARD:
        action['from_graveyard'] = True
    announced = dict(action['targets'])
    if method == 'bestow':
        # A single-face request omits a selector; the projected native frame defaults to 0.
        assert not state.cards[cid].card_faces
        announced['selected_face_index'] = 0
    before_targets = capture_announced_target_references(state, announced)
    mana_before = sum(state.players[seat].mana_pool.values())
    result = act(state, seat, action)
    frame = result.stack[-1]
    assert frame.source_card_id == cid and frame.controller == seat
    assert result.cards[cid].zone == Zone.STACK
    assert frame.payload['__announced_targets'] == announced
    assert frame.payload['__announced_target_references'] == before_targets
    assert frame.payload['mana_spent'] == mana_before - sum(result.players[seat].mana_pool.values())
    assert frame.payload['mana_spent'] > 0
    return result


def resolve_top(state):
    assert state.stack and not state.pending_mechanic_choice
    frame_id = state.stack[-1].id
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert all(item.id != frame_id for item in state.stack)
    return state


def remove_above(state, seat, cid, removal, retained=None):
    old_frame = asdict(state.stack[-1]) if retained is not None else None
    old_reference = card_reference(state, cid)
    state = cast(state, seat, removal, targets={'target_card_id': cid})
    assert state.stack[-1].payload['mana_spent'] == 3
    if retained is not None:
        assert asdict(state.stack[-2]) == old_frame
    state = resolve_top(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD
    assert cid in state.players[state.cards[cid].owner].graveyard
    assert state.cards[cid].zone_change_sequence == old_reference['sequence'] + 1
    if retained is not None:
        assert asdict(state.stack[-1]) == old_frame == retained
    return state


def suppression(state, seat, humility, jailer):
    assert not printed_abilities_suppressed(state, jailer)
    state = cast(state, seat, humility)
    assert state.stack[-1].payload['mana_spent'] == 4
    state = resolve_top(state)
    assert state.cards[humility].zone == Zone.BATTLEFIELD
    assert state.cards[jailer].zone == Zone.BATTLEFIELD
    assert printed_abilities_suppressed(state, jailer)
    return state


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('mode', ('blocked', 'removed', 'suppressed'))
def test_real_daretti_paid_loyalty_sacrifice_and_retained_return(rows, history, seat, mode):
    state = board(seat)
    jailer = seed(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    target = seed(state, rows['Shuko'], seat, Zone.GRAVEYARD)
    sacrifice = seed(state, rows['Shuko'], seat, Zone.BATTLEFIELD)
    daretti = seed(state, history['Daretti, Scrap Savant'], seat, Zone.HAND)
    removal = seed(state, history['Krosan Grip'], seat, Zone.HAND)
    humility = seed(state, rows['Humility'], seat, Zone.HAND)
    state = cast(state, seat, daretti)
    assert state.stack[-1].payload['mana_spent'] == 4
    state = resolve_top(state)
    assert state.cards[daretti].loyalty == 3
    if mode == 'suppressed':
        state = suppression(state, seat, humility, jailer)
    reference = card_reference(state, target)
    mana = deepcopy(state.players[seat].mana_pool)
    action = {'type': 'activate_loyalty', 'card_id': daretti, 'ability_index': 1,
              'targets': {'target_card_id': target}}
    rejected(state, 3 - seat, action)
    state = act(state, seat, action)
    assert state.cards[daretti].loyalty == 1
    assert state.players[seat].mana_pool == mana
    assert daretti in state.loyalty_activated_this_turn
    frame = asdict(state.stack[-1])
    assert frame['source_card_id'] == daretti and frame['controller'] == seat
    assert frame['payload']['effects'][0]['payload']['target_reference'] == reference
    assert frame['payload']['__announced_targets'] == action['targets']
    if mode == 'removed':
        state = remove_above(state, seat, jailer, removal, frame)
    state = resolve_top(state)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'loyalty_cards' and pending['player_id'] == seat
    assert sacrifice in pending['options']
    # The only authorized raw-frame addition is native ownership of resolution staging.
    owned = deepcopy(frame)
    owned['payload']['__resolution_stage_owned'] = True
    assert pending['resolving_item'] == owned
    assert pending['effect_payload']['__resolving_item'] == owned
    assert pending['option_references'][sacrifice] == card_reference(state, sacrifice)
    assert state.cards[sacrifice].zone == Zone.BATTLEFIELD
    choice = {'type': 'choose_mechanic', 'card_ids': [sacrifice]}
    rejected(state, 3 - seat, choice)
    rejected(state, seat, {'type': 'choose_mechanic', 'card_ids': [sacrifice, sacrifice]})
    mana = deepcopy(state.players[seat].mana_pool)
    state = act(state, seat, choice)
    assert state.players[seat].mana_pool == mana
    assert state.cards[daretti].loyalty == 1
    assert state.cards[sacrifice].zone == Zone.GRAVEYARD
    assert state.players[seat].graveyard.count(sacrifice) == 1
    assert state.cards[sacrifice].zone_change_sequence == 1
    assert state.cards[target].zone == (Zone.GRAVEYARD if mode == 'blocked' else Zone.BATTLEFIELD)
    assert state.cards[target].zone_change_sequence == (0 if mode == 'blocked' else 1)
    assert not state.stack and state.pending_mechanic_choice is None
    assert state.cards[daretti].oracle_text == history['Daretti, Scrap Savant']['oracle_text']
    assert state.cards[jailer].oracle_text == rows['Soulless Jailer']['oracle_text']


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('mode', ('blocked', 'removed', 'suppressed'))
def test_real_reanimate_retained_target_entry_and_actual_life_payment(rows, extra_rows, history, seat, mode):
    state = board(seat)
    jailer = seed(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    target = seed(state, extra_rows['Gravecrawler'], seat, Zone.GRAVEYARD)
    spell = seed(state, history['Reanimate'], seat, Zone.HAND)
    removal = seed(state, history['Krosan Grip'], seat, Zone.HAND)
    humility = seed(state, rows['Humility'], seat, Zone.HAND)
    if mode == 'suppressed':
        state = suppression(state, seat, humility, jailer)
    state = cast(state, seat, spell, targets={'target_card_id': target})
    assert state.stack[-1].payload['mana_spent'] == 1
    retained = asdict(state.stack[-1])
    assert state.players[seat].life == 20
    if mode == 'removed':
        state = remove_above(state, seat, jailer, removal, retained)
    state = resolve_top(state)
    assert state.cards[target].zone == (Zone.GRAVEYARD if mode == 'blocked' else Zone.BATTLEFIELD)
    assert state.cards[target].zone_change_sequence == (0 if mode == 'blocked' else 1)
    assert state.players[seat].life == 19
    assert state.players[3 - seat].life == 20
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert not state.stack and state.pending_mechanic_choice is None
    assert state.cards[target].oracle_text == extra_rows['Gravecrawler']['oracle_text']


@pytest.mark.parametrize('seat', (1, 2))
def test_real_creature_graveyard_cast_enters_through_stack_while_jailer(rows, extra_rows, seat):
    state = board(seat)
    jailer = seed(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    seed(state, extra_rows['Diregraf Ghoul'], seat, Zone.BATTLEFIELD)
    card = seed(state, extra_rows['Gravecrawler'], seat, Zone.GRAVEYARD)
    before_b = state.players[seat].mana_pool['B']
    state = cast(state, seat, card)
    assert state.stack[-1].payload['mana_spent'] == 1
    assert state.players[seat].mana_pool['B'] == before_b - 1
    assert card not in state.players[seat].graveyard
    assert state.cards[card].zone_change_sequence == 1
    state = resolve_top(state)
    assert state.cards[card].zone == Zone.BATTLEFIELD
    # Spell entry assigns a fresh BF incarnation; this route keeps the STACK sequence.
    assert state.cards[card].zone_change_sequence == 1
    assert state.cards[card].battlefield_incarnation > 0
    assert card in state.players[seat].battlefield
    assert state.cards[jailer].zone == Zone.BATTLEFIELD
    assert not printed_abilities_suppressed(state, jailer)
    assert not state.stack and state.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('name,method,spent', (('Shuko', 'base', 1), ('Leafcrown Dryad', 'bestow', 4)))
def test_real_announced_noncreature_method_rejects_before_cost_then_actual_removal_allows(
        rows, extra_rows, permissions_rows, history, seat, name, method, spent):
    state = board(seat)
    seed(state, permissions_rows['Muldrotha, the Gravetide'], seat, Zone.BATTLEFIELD)
    host = seed(state, extra_rows['Diregraf Ghoul'], seat, Zone.BATTLEFIELD)
    raw = rows[name] if name in rows else extra_rows[name]
    card = seed(state, raw, seat, Zone.GRAVEYARD)
    jailer = seed(state, rows['Soulless Jailer'], seat, Zone.HAND)
    removal = seed(state, history['Krosan Grip'], seat, Zone.HAND)
    retained_cost = offer(state, seat, card, method)
    action = {'type': 'cast_spell', 'card_id': card, 'from_graveyard': True,
              'cost_choice': {'id': retained_cost},
              'targets': {'target_card_id': host} if method == 'bestow' else {}}
    state = cast(state, seat, jailer)
    assert state.stack[-1].payload['mana_spent'] == 2
    state = resolve_top(state)
    before_mana = deepcopy(state.players[seat].mana_pool)
    before_uses = deepcopy(state.graveyard_permission_uses)
    rejected(state, seat, action)
    rejected(state, 3 - seat, action)
    assert state.players[seat].mana_pool == before_mana
    assert state.graveyard_permission_uses == before_uses
    assert state.cards[card].zone == Zone.GRAVEYARD
    assert state.cards[card].oracle_text == raw['oracle_text']
    assert state.cards[card].types == (['Enchantment', 'Creature'] if method == 'bestow' else ['Artifact'])
    state = remove_above(state, seat, jailer, removal)
    assert offer(state, seat, card, method) == retained_cost
    state = cast(state, seat, card, method=method, option=retained_cost, targets=action['targets'])
    assert state.stack[-1].payload['mana_spent'] == spent
    assert state.cards[card].types == (['Enchantment'] if method == 'bestow' else ['Artifact'])
    assert len(state.graveyard_permission_uses) == len(before_uses) + 1
    assert next(iter(state.graveyard_permission_uses)).endswith(
        ':Enchantment' if method == 'bestow' else ':Artifact')
    state = resolve_top(state)
    assert state.cards[card].zone == Zone.BATTLEFIELD
    assert state.cards[card].zone_change_sequence == 1
    assert state.cards[card].battlefield_incarnation > 0
    assert state.cards[card].attached_to == (host if method == 'bestow' else None)
    assert state.cards[card].oracle_text == raw['oracle_text']
    assert not state.stack and state.pending_mechanic_choice is None
