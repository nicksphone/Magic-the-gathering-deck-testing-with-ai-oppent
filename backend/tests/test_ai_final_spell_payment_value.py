"""Independent canonical poses; no closed diagnostic roots, suffixes or model."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from ai.action_contract import complete_action
from ai.information import decision_view
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.costs import collect_cost_options, check_cost_option_available
from rules_engine.engine import RulesEngine
from tests.test_ai_joint_cast_resources import ROWS, snapshot
from tests.test_linked_damage_targets import raw_card

FIXTURES = Path(__file__).parent/'fixtures'
PROVENANCE = json.loads((FIXTURES/'final_spell_payment_value/PROVENANCE.json').read_bytes())
for filename, pin in PROVENANCE['sources'].items():
    assert hashlib.sha256((FIXTURES/filename).read_bytes()).hexdigest() == pin
SER = json.loads((FIXTURES/'activated_top_selection/serra-angel.json').read_bytes())
OPT = json.loads((FIXTURES/'activated_top_selection/opt.json').read_bytes())
ARTIST_LINE = (FIXTURES/'knowledge_profiles/seed155-scryfall.jsonl').read_bytes().splitlines(keepends=True)[7]
assert hashlib.sha256(ARTIST_LINE).hexdigest() == 'f23dc31f51a20c485ef1c26edbb3986c38797cc33a7268e3993cc55e017059ec'
ARTIST = json.loads(ARTIST_LINE)
CARDS = {**ROWS, 'Serra Angel': SER, 'Opt': OPT, 'Blood Artist': ARTIST}
RULES = RulesEngine()


def position(seat, lands=1, spells=('Deadly Dispute',), artist=False):
    quantities = {'Island': 16, 'Forest': 12, 'Swamp': 8, 'Raging Goblin': 4,
                  'Serra Angel': 3, 'Opt': 4, 'Deadly Dispute': 4, 'Blood Artist': 2}
    deck = []
    for name, count in quantities.items():
        row = CARDS[name]
        assert row['object'] == 'card' and row['id'] and row['oracle_id'] and row['uri']
        deck.append({**deepcopy(row), 'quantity': count, 'card_name': name,
                     'image_uri': row.get('image_uris', {}).get('normal')})
    state = MatchFactory.from_decks(deck, deck, seed=821953)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 8
    state.step = Step.END_STEP
    state.active_player, state.priority_player = 3-seat, seat
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.lands_played_this_turn = 1
        player.life = 20
    def place(name, zone, actor=seat):
        p = state.players[actor]
        cid = next(cid for cid in p.library if state.cards[cid].name == name)
        p.library.remove(cid)
        getattr(p, zone.value).append(cid)
        state.cards[cid].move_to_zone(zone)
        state.cards[cid].tapped = state.cards[cid].summoning_sick = False
        return cid
    ids = {name: place(name, Zone.HAND) for name in spells}
    ids['Serra Angel'] = place('Serra Angel', Zone.BATTLEFIELD)
    for _ in range(lands):
        place('Swamp', Zone.BATTLEFIELD)
    if 'Opt' in spells:
        place('Island', Zone.BATTLEFIELD)
    token = raw_card(state, ROWS['Treasure'], seat, Zone.BATTLEFIELD)
    token.is_token = True
    token.tapped = False
    ids['Treasure'] = token.id
    enemy = place('Raging Goblin', Zone.BATTLEFIELD, 3-seat)
    state.cards[enemy].tapped = True
    if artist:
        ids['Blood Artist'] = place('Blood Artist', Zone.BATTLEFIELD)
        state.players[3-seat].life = 1
    return state, ids


def move_for(state, seat, cid):
    return next(m for m in RULES.legal_moves(state, seat)
                if m.get('type') == 'cast_spell' and m.get('card_id') == cid)


def choose_pure(ai, state, seat, moves=None):
    moves = RULES.legal_moves(state, seat) if moves is None else moves
    old, before = deepcopy(moves), snapshot(state)
    global_rng, local = random.getstate(), state.rng.getstate()
    result = ai.choose_action(state, moves, seat).action
    assert moves == old and snapshot(state) == before
    assert random.getstate() == global_rng and state.rng.getstate() == local
    return result


def settle(state):
    for _ in range(40):
        if state.winner is not None or not (state.stack or state.pending_mechanic_choice
                or state.pending_replacement_choice or state.pending_trigger_order):
            return state
        pending = state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order
        actor = pending.get('player_id', pending.get('current_controller')) if pending else state.priority_player
        action = choose_pure(AIAgent('master', 'Control'), state, actor) if pending else {'type': 'pass_priority'}
        state = checked_action(state, RULES, actor, complete_action(action))
    raise AssertionError('Bounded native settlement')


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_master_does_not_force_expensive_repaired_draw(seat):
    state, ids = position(seat)
    ai = AIAgent('master', 'Control')
    move = move_for(state, seat, ids['Deadly Dispute'])
    option = next(o for o in collect_cost_options(state, seat, state.cards[ids['Deadly Dispute']]) if o.id == 'base')
    assert not check_cost_option_available(state, seat, state.cards[ids['Deadly Dispute']], option,
        cost_choice={'id': 'base', 'sacrifice_card_ids': [ids['Treasure']]})
    action = ai._materialize_action(state, move, seat)
    assert action['cost_choice']['sacrifice_card_ids'] == [ids['Serra Angel']]
    paid = checked_action(state, RULES, seat, complete_action(action))
    assert paid.stack[-1].payload['mana_spent'] == 2
    assert paid.cards[ids['Serra Angel']].zone == Zone.GRAVEYARD
    selected = choose_pure(ai, state, seat)
    swapped = deepcopy(state)
    for player in swapped.players.values():
        player.library.reverse()
    assert choose_pure(ai, swapped, seat) == selected
    assert selected['type'] == 'pass_priority'


@pytest.mark.parametrize('seat', [1, 2])
def test_payable_cheap_token_draw_is_still_cast_and_resolves(seat):
    state, ids = position(seat, lands=2)
    action = choose_pure(AIAgent('master', 'Control'), state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == ids['Deadly Dispute']
    assert action['cost_choice']['sacrifice_card_ids'] == [ids['Treasure']]
    after = settle(checked_action(state, RULES, seat, complete_action(action)))
    assert after.cards[ids['Serra Angel']].zone == Zone.BATTLEFIELD
    assert len(after.players[seat].hand) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_no_additional_cost_cantrip_still_uses_endstep(seat):
    state, ids = position(seat, spells=('Opt',))
    action = choose_pure(AIAgent('master', 'Control'), state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == ids['Opt']
    after = settle(checked_action(state, RULES, seat, complete_action(action)))
    assert len(after.players[seat].hand) == 1
    assert after.cards[ids['Serra Angel']].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_cost_orders_endstep_choices_not_offered_resource_minimum(seat):
    state, ids = position(seat, spells=('Deadly Dispute', 'Opt'))
    moves = RULES.legal_moves(state, seat)
    moves.sort(key=lambda m: m.get('card_id') != ids['Deadly Dispute'])
    action = choose_pure(AIAgent('master', 'Control'), state, seat, moves)
    assert action['type'] == 'cast_spell' and action['card_id'] == ids['Opt']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', ['Serra Angel', 'Treasure'])
def test_shared_payment_loss_uses_selected_ids_once_without_mutating_option(seat, selected):
    state, ids = position(seat, lands=2)
    ai = AIAgent('master', 'Control')
    option = move_for(state, seat, ids['Deadly Dispute'])['cost_options'][0]
    old = deepcopy(option)
    choice = {'id': option['id'], 'sacrifice_card_ids': [ids[selected]]}
    actual = ai._spell_payment_loss(state, seat, option, cost_choice=choice)
    assert actual == ai._sacrifice_loss(state, ids[selected], seat)
    assert option == old and choice['sacrifice_card_ids'] == [ids[selected]]
    assert ai._spell_payment_loss(state, seat, option) == ai._sacrifice_loss(state, ids['Treasure'], seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_selected_variable_discard_prices_actual_native_count(seat):
    from tests.test_ai_joint_cast_resource_budget import large_position
    state, action, hand, mana = large_position(seat)
    ai = AIAgent('master', 'Control')
    option = move_for(state, seat, action['card_id'])['cost_options'][0]
    actual = ai._spell_payment_loss(state, seat, option,
                                   cost_choice=action['cost_choice'], x_value=15)
    assert actual == sum(ai._hand_retention_value(state, cid, seat) for cid in hand[:15])
    checked_action(state, RULES, seat, complete_action(action))


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_expensive_selection_stays_native_legal_not_replaced(seat):
    state, ids = position(seat, lands=2)
    ai = AIAgent('master', 'Control')
    move = move_for(state, seat, ids['Deadly Dispute'])
    choice = {'id': 'base', 'sacrifice_card_ids': [ids['Serra Angel']]}
    offered = {**move, 'cost_choice': deepcopy(choice)}
    action = ai._materialize_action(state, offered, seat)
    assert action['cost_choice'] == choice and not action.get('_invalid_ai_choice')
    assert ai._forced_endstep_card_advantage(state, [offered], seat) is None
    paid = checked_action(state, RULES, seat, complete_action(action))
    assert paid.cards[ids['Serra Angel']].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_expensive_draw_with_immediate_native_winning_trigger_is_not_banned(seat):
    state, ids = position(seat, lands=2, artist=True)
    moves = RULES.legal_moves(state, seat)
    for move in moves:
        if move.get('type') == 'cast_spell':
            move['cost_choice'] = {'id': 'base', 'sacrifice_card_ids': [ids['Serra Angel']]}
    action = choose_pure(AIAgent('master', 'Control'), state, seat, moves)
    assert action['type'] == 'cast_spell' and action['cost_choice']['sacrifice_card_ids'] == [ids['Serra Angel']]
    after = settle(checked_action(state, RULES, seat, complete_action(action)))
    assert after.winner == seat and after.players[3-seat].life == 0
