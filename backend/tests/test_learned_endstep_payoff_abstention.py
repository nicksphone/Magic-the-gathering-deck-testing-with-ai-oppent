"""Canonical ability text and explicitly synthetic keyword-only abstention controls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai import learned_policy
from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view
from game_state.state import CardInstance, Zone
from rules_engine.continuous import effective_keywords
from tests.test_ai_final_spell_payment_value import position
from tests.test_learned_endstep_payment_preference import offered, route
from tests.test_linked_damage_targets import raw_card


FIXTURES = Path(__file__).parent / 'fixtures'
CANONICAL = [
    ('canonical_magecraft_audit/clever-lumimancer.json',
     '4eb541dfdb2444d20e198181392a5d240336b1e419cac2ab0a84beafff2c66cc'),
    ('empty_hand_attack_witness/monastery-swiftspear.json',
     'e2ddcfca826391839b3956c426ee85516e0959fc09f0c23d473207f564cda10a'),
]


def must_not_price(*args, **kwargs):
    pytest.fail('Potential public payoff must abstain before the economic comparison')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('owner_is_actor', [True, False])
@pytest.mark.parametrize('fixture,sha256', CANONICAL)
def test_full_canonical_prefixed_payoff_keeps_q_and_explicit_cost(
        monkeypatch, seat, owner_is_actor, fixture, sha256):
    data = (FIXTURES / fixture).read_bytes()
    assert hashlib.sha256(data).hexdigest() == sha256
    raw = json.loads(data)
    original = deepcopy(raw)
    state, ids = position(seat, lands=2)
    card = raw_card(state, raw, seat if owner_is_actor else 3-seat, Zone.BATTLEFIELD)
    assert card.oracle_text == raw['oracle_text'] and raw == original
    moves = offered(state, seat, ids['Serra Angel'])
    cast = next(m for m in moves if m['type'] == 'cast_spell')
    action = complete_action(AIAgent()._materialize_action(state, cast, seat))
    view, _ = decision_view(state, seat, moves)
    monkeypatch.setattr(AIAgent, '_endstep_draw_payment_preference', must_not_price)
    assert learned_policy._prefer_pass_to_paid_draw(
        AIAgent('master', 'Control'), view, action, seat, cast['cost_options'][0]) is False
    chosen, _ = route(monkeypatch, state, seat, moves)
    assert chosen['type'] == 'cast_spell'
    assert chosen['cost_choice'] == {'id': 'base', 'sacrifice_card_ids': [ids['Serra Angel']]}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keyword', ['Prowess', 'Undying', 'Decayed', 'Exalted',
                                     'Bushido 1', 'Rampage 2', 'Flanking', 'Training'])
def test_synthetic_bare_native_trigger_keyword_abstains(monkeypatch, seat, keyword):
    # This is a synthetic metadata protocol, NOT a shortened canonical printing.
    state, ids = position(seat, lands=2)
    card = CardInstance(id=state.allocate_object_id(), name='SYNTHETIC keyword protocol',
                        owner=seat, controller=seat, zone=Zone.BATTLEFIELD,
                        types=['Creature'], power=1, toughness=1,
                        keywords=[keyword], oracle_text='')
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    moves = offered(state, seat, ids['Serra Angel'])
    cast = next(m for m in moves if m['type'] == 'cast_spell')
    action = complete_action(AIAgent()._materialize_action(state, cast, seat))
    view, _ = decision_view(state, seat, moves)
    assert keyword.lower() in effective_keywords(view, card.id)
    assert view.cards[card.id].oracle_text == ''
    monkeypatch.setattr(AIAgent, '_endstep_draw_payment_preference', must_not_price)
    assert learned_policy._prefer_pass_to_paid_draw(
        AIAgent('master', 'Control'), view, action, seat, cast['cost_options'][0]) is False
