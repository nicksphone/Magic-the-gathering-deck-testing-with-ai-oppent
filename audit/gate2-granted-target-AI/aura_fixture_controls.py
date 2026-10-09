"""Selected pure Aura assertion/fixture extraction; original mixed module NOT qualified."""
import json
from pathlib import Path
from ai.agent import AIAgent
from ai.mana_resource_policy import resource_change_plan
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from tests.test_variable_mana import clean
from tests.test_ai_recurring_engines import add as add_card
FIXTURES = Path(__file__).resolve().parents[2]/'backend/tests/fixtures'
CARDS = {}
for name in ('land_types', 'ward', 'attached_scaling', 'aura_costs', 'variable_mana', 'public_foretell', 'quoted_entry'):
    CARDS.update({card['name']: card for card in json.loads((FIXTURES/(name+'.json')).read_text())})
def add(state, name, seat, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, seat, zone, cards=CARDS)
    card.summoning_sick = False
    return card

def setup(case, seat):
    state = clean()
    state.active_player = state.priority_player = seat
    state.turn = 4
    for _ in range(2):
        add(state, 'Hallowed Fountain', seat)
    source = add(state, 'Blood Moon' if case == 'harmful' else 'Prismatic Omen', seat, Zone.HAND)
    held = add(state, 'Lightning Bolt' if case == 'useful' else 'Counterspell', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 2, 'G': 1}
    if case == 'harmful':
        state.players[seat].mana_pool['R'] = 1
    return state, source, held

def test_aura_targets_are_selected_by_actual_resource_gain(seat):
    state = clean()
    state.active_player = state.priority_player = seat
    friendly = add(state, 'Hallowed Fountain', seat)
    enemy = add(state, 'Hallowed Fountain', 3-seat)
    add(state, 'Lightning Bolt', seat, Zone.HAND)
    source = add(state, 'Lush Growth', seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1}
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == source.id)
    agent = AIAgent()
    plan = resource_change_plan(agent, state, move, seat)
    assert plan and not plan['defer']
    assert plan['action']['targets']['target_card_id'] == friendly.id
    before = serialize_match_snapshot(state)
    action = agent.choose_action(state, rules.legal_moves(state, seat), seat).action
    assert action['card_id'] == source.id and action['targets']['target_card_id'] == friendly.id
    assert serialize_match_snapshot(state) == before
    assert not enemy.tapped

def test_draw_aura_keeps_resource_outcome_unknown(seat):
    state, source, held = setup('harmful', seat)
    aura = add(state, 'Spreading Seas', seat, Zone.HAND)
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == aura.id)
    assert resource_change_plan(AIAgent(), state, move, seat) is None
