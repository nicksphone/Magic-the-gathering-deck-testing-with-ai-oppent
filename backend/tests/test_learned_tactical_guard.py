"""Canonical checked forecasts plus explicitly synthetic Q-routing protocols.

No fitted checkpoint is admitted/re-pinned here. An unanswered win is not a
forced win against an opponent's unannounced responses or unknown choices.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from ai import learned_policy, learned_qv, pending_effects
from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import inspect_target_hints
from tests.test_ai_strategy_fundamentals import position
from tests.test_live_learned_policy import _binding
from tests.test_training_reference_context import _expanded, _field, _named_values


RULES = RulesEngine()


def _cast(state, cards, seat, name, targets=None):
    offered = next(move for move in RULES.legal_moves(deepcopy(state), seat)
                   if move['type'] == 'cast_spell' and move['card_id'] == cards[name])
    return complete_action({**offered, 'cost_choice': {'id': 'base'},
                            'targets': targets or {}})


def _fixture(seat, spell='Lightning Bolt', *, two_spells=False):
    hand = ['Monastery Swiftspear', spell]
    if two_spells:
        hand.append('Lava Spike')
    state, cards, _, _ = position(seat, hand, ['Mountain'])
    state.players[3-seat].life = 3
    return state, cards


def _salve(state, caster):
    # Full retained RAW enters the real Factory before any physical pose.
    path = Path(__import__('tests.test_ai_burn_efficiency', fromlist=['__file__']).__file__).parent
    data = (path / 'fixtures/soulscar_protection_boundaries/healing-salve.json').read_bytes()
    assert sha256(data).hexdigest() == 'bbb9f8e419f944cdab82ddf9eec451ad0b24d138d3d80554128ddbbfdc0d0325'
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == 'Healing Salve'
    deck = [{**raw, 'quantity': 8, 'card_name': raw['name']}]
    sample = MatchFactory.from_decks(deck, deck, seed=9104)
    card = deepcopy(sample.cards[sample.players[1].hand[0]])
    card.id = state.allocate_object_id()
    card.owner = card.controller = caster
    card.move_to_zone(Zone.HAND)
    state.cards[card.id] = card
    state.players[caster].hand.append(card.id)
    state.players[caster].mana_pool = {'W': 1}  # Declared resource pose, not natural play.
    return card.id


def _announce_salve(state, caster, mode_prefix):
    salve = _salve(state, caster)
    state.active_player = state.priority_player = caster
    modes = inspect_target_hints(state, state.cards[salve], caster)['modes']
    mode = next(text for text in modes if text.startswith(mode_prefix))
    state = checked_action(state, RULES, caster, {'type': 'cast_spell',
        'card_id': salve, 'targets': {'mode_text': mode, 'target_player': caster}})
    assert state.stack[-1].source_card_id == salve
    assert not any(state.players[caster].mana_pool.values())
    return state, salve


def _forecast(state, seat, action):
    before = serialize_match_snapshot(state)
    moves = RULES.legal_moves(deepcopy(state), seat)
    view, _ = decision_view(state, seat, moves)
    result = pending_effects.unanswered_action_wins(view, seat, action)
    assert serialize_match_snapshot(state) == before
    return result


def _route(monkeypatch, state, seat, proposals, scores):
    """Only shortlist/Q are protocol doubles; admission/forecast stay genuine."""
    binding = _binding(learned_policy)
    calls = {'scored': [], 'state_packs': [], 'forecast': []}
    delegate = pending_effects.unanswered_action_wins

    def forecast(view, player_id, action, **kwargs):
        assert view.ai_information_player == player_id == seat
        assert all(is_unknown(view.cards[cid]) for cid in view.players[3-seat].hand)
        result = delegate(view, player_id, action, **kwargs)
        calls['forecast'].append((deepcopy(action), result))
        return result

    class SyntheticScores:
        def predict(self, pack):
            root = _expanded(pack)
            kind = _field(root, 'type')['value']
            if kind == 'cast_spell':
                names = _named_values(_field(root, 'card_id'), 'name')
                assert len(names) == 1
                name = names[0]['value']
            else:
                name = kind
            calls['scored'].append(name)
            value = scores[name]
            return deepcopy(value) if isinstance(value, dict) else {'q': value, 'v': 0.0}

    def prepare(_policy, state_pack):
        calls['state_packs'].append(deepcopy(state_pack))
        return SyntheticScores()

    monkeypatch.setattr(AIAgent, '_strategic_top_actions',
                        lambda _agent, _view, _moves, _seat, _limit: deepcopy(proposals))
    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', prepare)
    monkeypatch.setattr(pending_effects, 'unanswered_action_wins', forecast)
    before = serialize_match_snapshot(state)
    moves = RULES.legal_moves(deepcopy(state), seat)
    old_moves = deepcopy(moves)
    view, supplied = decision_view(state, seat, moves)
    action = learned_policy.choose_learned_action(binding,
        AIAgent(difficulty='master', archetype='Burn'), view, supplied, seat,
        admit=lambda proposed: checked_action(state, RULES, seat, proposed))
    assert serialize_match_snapshot(state) == before and moves == old_moves
    return action, calls


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Lava Spike', 'Lightning Bolt'])
def test_checked_unanswered_lethal_precedes_higher_synthetic_development_q(monkeypatch, seat, spell):
    state, cards = _fixture(seat, spell)
    burn = _cast(state, cards, seat, spell, {'target_player': 3-seat})
    creature = _cast(state, cards, seat, 'Monastery Swiftspear')
    assert _forecast(state, seat, burn) is True
    assert _forecast(state, seat, creature) is False
    action, calls = _route(monkeypatch, state, seat, [creature, burn],
                          {'Monastery Swiftspear': 0.9, spell: -0.9})
    assert len(calls['scored']) == 2
    assert action == burn


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tied', [False, True])
def test_highest_q_and_stable_input_order_among_actual_wins(monkeypatch, seat, tied):
    state, cards = _fixture(seat, two_spells=True)
    bolt = _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})
    lava = _cast(state, cards, seat, 'Lava Spike', {'target_player': 3-seat})
    creature = _cast(state, cards, seat, 'Monastery Swiftspear')
    assert _forecast(state, seat, bolt) is _forecast(state, seat, lava) is True
    action, calls = _route(monkeypatch, state, seat, [bolt, lava, creature],
        {'Lightning Bolt': 0.2, 'Lava Spike': 0.2 if tied else 0.8,
         'Monastery Swiftspear': 0.9})
    assert len(calls['scored']) == 3
    assert action == (bolt if tied else lava)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_prevention_disproves_printed_damage_lethal(monkeypatch, seat):
    state, cards = _fixture(seat)
    state, salve = _announce_salve(state, 3-seat, 'Prevent the next')
    for _ in range(4):
        if not state.stack:
            break
        state = checked_action(state, RULES, state.priority_player, {'type': 'pass_priority'})
    assert not state.stack and state.cards[salve].zone == Zone.GRAVEYARD
    assert state.players[3-seat].prevent_damage_shield == 3
    state.active_player = state.priority_player = seat
    bolt = _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})
    creature = _cast(state, cards, seat, 'Monastery Swiftspear')
    assert _forecast(state, seat, bolt) is False
    assert _forecast(state, seat, creature) is False
    action, _ = _route(monkeypatch, state, seat, [bolt, creature],
                       {'Lightning Bolt': -0.5, 'Monastery Swiftspear': 0.5})
    assert action == creature


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opponent_life', [3, 6])
def test_paid_lifegain_stack_order_not_printed_subtraction(monkeypatch, seat, opponent_life):
    state, cards = _fixture(seat)
    state.players[3-seat].life = opponent_life
    state, salve = _announce_salve(state, 3-seat, 'Target player gains')
    state = checked_action(state, RULES, 3-seat, {'type': 'pass_priority'})
    assert state.priority_player == seat and state.stack[-1].source_card_id == salve
    bolt = _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})
    wait = {'type': 'pass_priority'}
    assert _forecast(state, seat, bolt) is (opponent_life == 3)
    assert _forecast(state, seat, wait) is False
    action, calls = _route(monkeypatch, state, seat, [bolt, wait],
                           {'Lightning Bolt': -0.5, 'pass_priority': 0.5})
    assert len(calls['scored']) == 2
    assert action == (bolt if opponent_life == 3 else wait)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_aegis_excludes_rejected_high_q_player_target(monkeypatch, seat):
    from tests.target_discard_canonical_db4e import canonical_card
    state, cards = _fixture(seat)
    shield = canonical_card('Aegis of the Gods', id=state.allocate_object_id(),
                            owner=3-seat, controller=3-seat, zone=Zone.BATTLEFIELD)
    state.cards[shield.id] = shield
    state.players[3-seat].battlefield.append(shield.id)
    assign_static_order_on_battlefield_entry(state, shield.id)
    invalid = {'type': 'cast_spell', 'card_id': cards['Lightning Bolt'],
               'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat}}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RULES, seat, invalid)
    assert serialize_match_snapshot(state) == before
    creature = _cast(state, cards, seat, 'Monastery Swiftspear')
    action, calls = _route(monkeypatch, state, seat, [invalid, creature],
                          {'Lightning Bolt': 1.0, 'Monastery Swiftspear': -1.0})
    assert calls['scored'] == ['Monastery Swiftspear']
    assert all(a['card_id'] != cards['Lightning Bolt'] for a, _ in calls['forecast'])
    assert action == creature


@pytest.mark.parametrize('seat', [1, 2])
def test_real_opt_continuation_unknown_does_not_override_q(monkeypatch, seat):
    state, cards, _, _ = position(seat, ['Opt', 'Lightning Bolt'], ['Island', 'Mountain'])
    state.players[3-seat].life = 6
    opt = _cast(state, cards, seat, 'Opt')
    state = checked_action(state, RULES, seat, opt)
    assert state.stack[-1].source_card_id == cards['Opt']
    bolt = _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})
    wait = {'type': 'pass_priority'}
    assert _forecast(state, seat, bolt) is None
    assert _forecast(state, seat, wait) is None
    action, _ = _route(monkeypatch, state, seat, [bolt, wait],
                       {'Lightning Bolt': -0.5, 'pass_priority': 0.5})
    assert action == wait


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_opponent_order_and_private_trace_do_not_change_guard(monkeypatch, seat):
    state, cards = _fixture(seat)
    opponent = state.players[3-seat]
    for _ in range(2):
        cid = opponent.library.pop()
        state.cards[cid].move_to_zone(Zone.HAND)
        opponent.hand.append(cid)
    bolt = _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})
    creature = _cast(state, cards, seat, 'Monastery Swiftspear')
    action, calls = _route(monkeypatch, state, seat, [creature, bolt],
                           {'Monastery Swiftspear': 0.9, 'Lightning Bolt': -0.9})
    changed = deepcopy(state)
    changed.players[3-seat].hand.reverse()
    changed.players[3-seat].library.reverse()
    changed.log.append('AI TRACE PRIVATE_TACTICAL_ROUTING_CANARY')
    second, changed_calls = _route(monkeypatch, changed, seat, [creature, bolt],
                                  {'Monastery Swiftspear': 0.9, 'Lightning Bolt': -0.9})
    assert action == second == bolt
    assert calls['state_packs'] == changed_calls['state_packs']
    assert 'PRIVATE_TACTICAL_ROUTING_CANARY' not in json.dumps(calls['state_packs'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [{'q': float('nan'), 'v': 0.0},
                                {'q': 0.0, 'v': float('inf')},
                                {'q': True, 'v': 0.0}], ids=['nan-q', 'infinite-v', 'boolean-q'])
def test_late_invalid_qv_cannot_be_bypassed_by_first_checked_win(monkeypatch, seat, bad):
    state, cards = _fixture(seat)
    bolt = _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})
    creature = _cast(state, cards, seat, 'Monastery Swiftspear')
    assert _forecast(state, seat, bolt) is True
    action, calls = _route(monkeypatch, state, seat, [bolt, creature],
                           {'Lightning Bolt': 0.5, 'Monastery Swiftspear': bad})
    assert calls['scored'] == ['Lightning Bolt', 'Monastery Swiftspear']
    assert action is None


@pytest.mark.parametrize('seat', [1, 2])
def test_protocol_truthy_integer_is_not_an_exact_true_forecast(monkeypatch, seat):
    state, cards = _fixture(seat)
    state.players[3-seat].life = 20
    bolt = _cast(state, cards, seat, 'Lightning Bolt', {'target_player': 3-seat})
    creature = _cast(state, cards, seat, 'Monastery Swiftspear')
    assert _forecast(state, seat, bolt) is False
    assert _forecast(state, seat, creature) is False
    delegate = pending_effects.unanswered_action_wins

    def protocol_result(view, player_id, action, **kwargs):
        assert delegate(view, player_id, action, **kwargs) is False
        # Deliberately invalid classifier metadata, NOT an asserted game win.
        return 1 if action.get('card_id') == cards['Lightning Bolt'] else False

    monkeypatch.setattr(pending_effects, 'unanswered_action_wins', protocol_result)
    action, _ = _route(monkeypatch, state, seat, [bolt, creature],
                       {'Lightning Bolt': -0.5, 'Monastery Swiftspear': 0.5})
    assert action == creature
