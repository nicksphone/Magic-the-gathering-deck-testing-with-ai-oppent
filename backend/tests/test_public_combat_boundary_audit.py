"""Response-safe public resource candidates versus actual crackback/response vetoes."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_empty_hand_attack_witness import ROWS, finish_combat, position
from tests.test_linked_damage_targets import raw_card
from tests.test_public_block_leaf_audit import STYLES


FIXTURES = Path(__file__).parent / 'fixtures/public_combat_boundary'
LANDS = {}
for entry in json.loads((FIXTURES / 'provenance.json').read_text())['cards']:
    data = (FIXTURES / entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    raw = json.loads(data)
    assert raw['name'] == entry['name'] and raw['oracle_id'] == entry['oracle_id']
    LANDS[raw['name']] = raw

FAMILIES = ['Sheoldred, the Apocalypse', 'Torrential Gearhulk']


class BoundaryAgent(AIAgent):
    def __init__(self, style):
        super().__init__(difficulty='master', archetype=style, opponent_archetype='Aggro')
        self.lines = []

    def _strategic_line_score(self, state, move, player_id, depth):
        score = super()._strategic_line_score(state, move, player_id, depth)
        self.lines.append({'move': deepcopy(move), 'depth': depth, 'score': score})
        return score


def record(name, value):
    root = Path(os.environ['MTG_BOUNDARY_AUDIT_EVIDENCE'])
    root.mkdir(parents=True, exist_ok=True)
    with (root / (name + '.json')).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def response_window(state, seat, source):
    engine = RulesEngine()
    announced = checked_action(state, engine, seat, {'type': 'attack', 'attackers': [source]})
    reply = checked_action(announced, engine, seat, {'type': 'pass_priority'})
    return announced, reply, engine.legal_moves(reply, 3-seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('boundary', ['Underground Sea', 'Tropical Island', 'inert-graveyard'])
def test_response_safe_resource_candidates_take_profitable_damage(seat, family, style, boundary):
    state, source = position(seat, family, counter=True)
    dual = None
    if boundary == 'inert-graveyard':
        raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    else:
        dual = raw_card(state, LANDS[boundary], 3-seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    engine = RulesEngine()
    legal = engine.legal_moves(state, seat)
    announced, reply, responses = response_window(state, seat, source)
    assert {move['type'] for move in responses} <= {'pass_priority', 'activate_mana_ability', 'block'}
    assert not reply.players[3-seat].hand
    if dual is not None:
        option = next(move for move in responses if move['type'] == 'activate_mana_ability'
                      and move['card_id'] == dual.id)
        color = next(iter(option['outputs']))
        paid_mana = checked_action(reply, engine, 3-seat, {'type': 'activate_mana_ability',
            'card_id': dual.id, 'ability_index': option['ability_index'], 'color': color})
        assert paid_mana.cards[dual.id].tapped and paid_mana.players[3-seat].mana_pool[color] == option['outputs'][color]
        assert not paid_mana.stack
    attacked = finish_combat(announced)
    passed = finish_combat(checked_action(state, engine, seat, {'type': 'attack', 'attackers': []}))
    assert attacked.players[3-seat].life == state.players[3-seat].life - int(ROWS[family]['power'])
    assert attacked.players[seat].life == passed.players[seat].life == state.players[seat].life
    assert attacked.winner is None and attacked.cards[source].zone == Zone.BATTLEFIELD
    assert attacked.players[seat].hand == state.players[seat].hand
    for cid in state.players[seat].battlefield:
        if 'Land' in state.cards[cid].types:
            assert attacked.cards[cid].tapped == state.cards[cid].tapped
    agent = BoundaryAgent(style)
    leaf = agent._complete_strategic_combat_leaf(announced, seat)
    if boundary == 'inert-graveyard':
        assert leaf is None
    else:
        assert leaf is not None
    decision = agent.choose_action(state, legal, seat)
    chosen = finish_combat(checked_action(state, engine, seat, decision.action))
    actor, visible = decision_view(state, seat, legal)
    assert serialize_match_snapshot(state) == before
    record(f'candidate-{seat}-{family}-{style}-{boundary}', {'seed': 1972639901,
        'scope': 'funded canonical retained state; checked declarations; not a natural snapshot',
        'seat': seat, 'family': family, 'style': style, 'boundary': boundary, 'snapshot': before,
        'actor_view': serialize_match_snapshot(actor), 'legal': legal, 'actor_legal': visible,
        'responses': responses, 'decision': decision.action, 'reasoning': decision.reasoning,
        'scores': agent.lines, 'checked_attack': serialize_match_snapshot(attacked),
        'checked_pass': serialize_match_snapshot(passed), 'checked_chosen': serialize_match_snapshot(chosen)})
    assert decision.action['type'] == 'attack' and source in decision.action['attackers'], (
        f'Public response-safe resource boundary still holds profitable damage: {decision.action}; {decision.reasoning}')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('response', ['flashback', 'held-bolt'])
def test_actual_paid_effectful_response_is_not_an_inert_resource(seat, family, response):
    state, source = position(seat, family)
    name = 'Memory Deluge' if response == 'flashback' else 'Lightning Bolt'
    card = raw_card(state, ROWS[name], 3-seat, Zone.GRAVEYARD if response == 'flashback' else Zone.HAND)
    if response == 'flashback':
        for _ in range(2):
            raw_card(state, ROWS['Island'], 3-seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    engine = RulesEngine()
    announced, reply, responses = response_window(state, seat, source)
    option = next(move for move in responses if move['type'] == 'cast_spell' and move['card_id'] == card.id)
    action = (AIAgent(difficulty='master')._materialize_action(reply, option, 3-seat)
              if response == 'flashback' else {'type': 'cast_spell', 'card_id': card.id,
                  'targets': {'target_card_id': source}})
    paid = checked_action(reply, engine, 3-seat, action)
    assert paid.stack and paid.cards[card.id].zone == Zone.STACK
    assert sum(paid.cards[cid].tapped for cid in paid.players[3-seat].battlefield) == (7 if response == 'flashback' else 1)
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is None
    assert AIAgent()._complete_strategic_combat_leaf(paid, seat) is None
    assert serialize_match_snapshot(state) == before
    record(f'response-{seat}-{family}-{response}', {'snapshot': before, 'responses': responses,
        'paid_action': action, 'paid_snapshot': serialize_match_snapshot(paid)})


def checked_next_combat(state, seat, attacker, retained_blocker=None):
    engine = RulesEngine()
    for _ in range(100):
        if state.winner is not None:
            return state
        if state.active_player == seat and state.step == Step.DECLARE_ATTACKERS:
            state = checked_action(state, engine, seat, {'type': 'attack', 'attackers': [attacker]})
            for _ in range(30):
                if state.winner is not None or state.step == Step.POSTCOMBAT_MAIN:
                    return state
                if any(move['type'] == 'block' for move in engine.legal_moves(state, 3-seat)):
                    blocks = {attacker: [retained_blocker]} if retained_blocker else {}
                    return finish_combat(checked_action(state, engine, 3-seat, {'type': 'block', 'blocks': blocks}))
                state = checked_action(state, engine, state.priority_player, {'type': 'pass_priority'})
            pytest.fail('Checked next attack did not resolve or reach blocker window')
        state = checked_action(state, engine, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Checked next turn did not reach opposing attack')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_tapped_public_creature_is_not_certified_safe_from_crackback(seat, family):
    state, source = position(seat, family)
    threat_name = 'Torrential Gearhulk' if family == 'Sheoldred, the Apocalypse' else 'Sheoldred, the Apocalypse'
    threat = raw_card(state, ROWS[threat_name], 3-seat, Zone.BATTLEFIELD)
    threat.summoning_sick = False
    threat.tapped = True
    state.players[seat].life = 1
    before = serialize_match_snapshot(state)
    engine = RulesEngine()
    announced, reply, responses = response_window(state, seat, source)
    assert {move['type'] for move in responses} <= {'pass_priority', 'activate_mana_ability', 'block'}
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is None
    attacked = checked_next_combat(finish_combat(announced), 3-seat, threat.id)
    held = checked_next_combat(finish_combat(checked_action(state, engine, seat,
        {'type': 'attack', 'attackers': []})), 3-seat, threat.id, source)
    assert attacked.winner == 3-seat and held.winner != 3-seat
    assert serialize_match_snapshot(state) == before
    decision = BoundaryAgent('Control').choose_action(state, engine.legal_moves(state, seat), seat)
    record(f'crackback-{seat}-{family}', {'snapshot': before, 'responses': responses,
        'decision': decision.action, 'reasoning': decision.reasoning,
        'attack_followup': serialize_match_snapshot(attacked), 'hold_followup': serialize_match_snapshot(held),
        'classification': 'actual no-intervening-play counterexample; response-free current combat does not certify future safety'})
