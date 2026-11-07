"""Independent canonical timing regressions, not recorded evaluation labels."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.continuous import effective_power
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import position, settle


RULES = RulesEngine()


def _position(seat, step, life=20):
    state, cards, _, _ = position(
        seat, ['Monastery Swiftspear', 'Lightning Bolt'], ['Mountain', 'Mountain'])
    state.step = step
    if step in {Step.UPKEEP, Step.DRAW}:
        state.players[seat].lands_played_this_turn = 0
        state.players[seat].land_plays_recorded_on_turn = state.turn
        state.players[seat].last_land_play_turn = state.turn - 1
    state.players[3 - seat].life = life
    return state, cards


def _choose(state, seat, *, binding=None):
    before = serialize_match_snapshot(state)
    global_rng = random.getstate()
    moves = RULES.legal_moves(deepcopy(state), seat)
    old_moves = deepcopy(moves)
    agent = AIAgent(difficulty='master', archetype='Burn',
                    opponent_archetype='Control', learned_binding=binding)
    action = agent.choose_action(state, moves, seat).action
    assert serialize_match_snapshot(state) == before and moves == old_moves
    checked_action(state, RULES, seat, action)
    assert serialize_match_snapshot(state) == before
    assert random.getstate() == global_rng
    return action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('step', [Step.UPKEEP, Step.DRAW])
def test_reserve_nonlethal_burn_for_known_prowess_development(seat, step):
    state, _ = _position(seat, step)
    assert _choose(state, seat)['type'] == 'pass_priority'


@pytest.mark.parametrize('seat', [1, 2])
def test_preserve_checked_early_burn_lethal(seat):
    state, cards = _position(seat, Step.UPKEEP, life=3)
    action = _choose(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == cards['Lightning Bolt']
    state = settle(checked_action(state, RULES, seat, action), seat, 'Burn', 'master')
    assert state.winner == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_main_phase_prowess_development_is_retained(seat):
    state, cards = _position(seat, Step.PRECOMBAT_MAIN)
    action = _choose(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == cards['Monastery Swiftspear']


@pytest.mark.parametrize('seat', [1, 2])
def test_known_land_first_makes_both_spells_jointly_affordable(seat):
    state, _, _, _ = position(seat, ['Monastery Swiftspear', 'Lightning Bolt', 'Mountain'], ['Mountain'])
    state.step = Step.UPKEEP
    state.players[seat].lands_played_this_turn = 0
    assert _choose(state, seat)['type'] == 'pass_priority'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('floating', [False, True])
def test_do_not_invent_mana_to_defer_burn(seat, floating):
    state, cards, _, _ = position(seat, ['Monastery Swiftspear', 'Lightning Bolt'], ['Mountain'])
    state.step = Step.UPKEEP
    if floating:
        state.players[seat].mana_pool = {'R': 1}
    action = _choose(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == cards['Lightning Bolt']


@pytest.mark.parametrize('seat', [1, 2])
def test_do_not_invent_an_additional_land_play(seat):
    state, cards, _, _ = position(seat, ['Monastery Swiftspear', 'Lightning Bolt', 'Mountain'], ['Mountain'])
    state.step = Step.UPKEEP
    state.players[seat].land_plays_recorded_on_turn = state.turn
    state.players[seat].last_land_play_turn = state.turn
    assert state.players[seat].lands_played_this_turn == 1
    main = deepcopy(state)
    main.step = Step.PRECOMBAT_MAIN
    assert not any(m['type'] == 'play_land' for m in RULES.legal_moves(main, seat))
    action = _choose(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == cards['Lightning Bolt']


def _face_action(cid, seat):
    return {'type': 'cast_spell', 'card_id': cid, 'targets': {'target_player': 3-seat}}


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_creature_removal_is_not_deferred(seat):
    state, cards, enemies, _ = position(seat,
        ['Monastery Swiftspear', 'Lightning Bolt'], ['Mountain', 'Mountain'], ['Grizzly Bears'])
    state.step = Step.UPKEEP
    action = {'type': 'cast_spell', 'card_id': cards['Lightning Bolt'],
              'targets': {'target_card_id': enemies['Grizzly Bears']}}
    checked_action(state, RULES, seat, action)
    before = serialize_match_snapshot(state)
    agent = AIAgent(difficulty='master', archetype='Burn')
    assert agent._early_prowess_burn_action(state, action, seat) is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_stack_response_is_not_deferred(seat):
    state, cards, _, move = position(seat,
        ['Monastery Swiftspear', 'Lightning Bolt'], ['Mountain', 'Mountain'], reserve=['Lightning Bolt'])
    state.step = Step.UPKEEP
    opposing_bolt = move('Lightning Bolt', 3-seat, Zone.HAND)
    move('Mountain', 3-seat, Zone.BATTLEFIELD)
    state = checked_action(state, RULES, seat, {'type': 'pass_priority'})
    state = checked_action(state, RULES, 3-seat, _face_action(opposing_bolt, 3-seat))
    state = checked_action(state, RULES, 3-seat, {'type': 'pass_priority'})
    assert state.stack and state.priority_player == seat
    action = _face_action(cards['Lightning Bolt'], seat)
    checked_action(state, RULES, seat, action)
    before = serialize_match_snapshot(state)
    assert AIAgent(archetype='Burn')._early_prowess_burn_action(state, action, seat) is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_native_continuation_develops_then_burns_for_extra_combat_damage(seat, tmp_path):
    state, cards = _position(seat, Step.UPKEEP)
    trace = []
    for _ in range(64):
        if state.step == Step.END_COMBAT:
            break
        actor = state.priority_player
        if state.step == Step.DECLARE_BLOCKERS and not state.blockers_declared:
            actor, action = 3-seat, {'type': 'block', 'blocks': {}}
        else:
            action = _choose(state, seat) if actor == seat else {'type': 'pass_priority'}
        trace.append((state.step.value, actor, deepcopy(action)))
        state = checked_action(state, RULES, actor, action)
    (tmp_path / 'native-sequence.json').write_text(json.dumps(trace, sort_keys=True))
    assert state.step == Step.END_COMBAT, trace
    assert state.players[3-seat].life == 15, trace
    assert cards['Monastery Swiftspear'] in state.players[seat].battlefield
    assert effective_power(state, cards['Monastery Swiftspear']) == 2
    assert state.cards[cards['Lightning Bolt']].zone == Zone.GRAVEYARD
    assert [action['card_id'] for _, actor, action in trace
            if actor == seat and action['type'] == 'cast_spell'] == [
                cards['Monastery Swiftspear'], cards['Lightning Bolt']]


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_hand_and_library_identity_do_not_change_deferral(seat):
    state, _, _, move = position(seat, ['Monastery Swiftspear', 'Lightning Bolt'],
        ['Mountain', 'Mountain'], reserve=['Grizzly Bears', 'Lava Spike'])
    state.step = Step.UPKEEP
    old = move('Grizzly Bears', 3-seat, Zone.HAND)
    hidden = deepcopy(state)
    player = hidden.players[3-seat]
    new = next(cid for cid in player.library if hidden.cards[cid].name == 'Lava Spike')
    player.library.remove(new)
    player.hand.remove(old)
    player.library.append(old)
    player.hand.append(new)
    hidden.cards[old].move_to_zone(Zone.LIBRARY)
    hidden.cards[new].move_to_zone(Zone.HAND)
    for player in hidden.players.values():
        player.library.reverse()
    assert _choose(state, seat) == _choose(hidden, seat) == {'type': 'pass_priority'}


@pytest.mark.parametrize('seat', [1, 2])
def test_synthetic_learned_face_score_also_uses_checked_timing(monkeypatch, seat):
    # Protocol score double, not fitted weights or playing-strength evidence.
    state, _ = _position(seat, Step.UPKEEP)
    scored = []
    assert _choose(state, seat, binding=_synthetic_binding(monkeypatch, scored)) == {'type': 'pass_priority'}
    assert 'cast_spell' in scored


def _synthetic_binding(monkeypatch, scored):
    from ai import learned_policy, learned_qv
    from tests.test_live_learned_policy import _binding
    from tests.test_training_reference_context import _expanded, _field

    class Scores:
        def predict(self, pack):
            kind = _field(_expanded(pack), 'type')['value']
            scored.append(kind)
            return {'q': .9 if kind == 'cast_spell' else -.9, 'v': 0.0}

    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', lambda *_: Scores())
    return _binding(learned_policy)


def _pending_creature(seat, life=20):
    state, cards = _position(seat, Step.PRECOMBAT_MAIN, life=life)
    state = checked_action(state, RULES, seat,
                           {'type': 'cast_spell', 'card_id': cards['Monastery Swiftspear']})
    assert len(state.stack) == 1 and state.priority_player == seat
    assert state.cards[cards['Monastery Swiftspear']].zone == Zone.STACK
    return state, cards


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [3, 20])
def test_pending_own_creature_waits_only_for_nonlethal_burn(seat, life):
    state, cards = _pending_creature(seat, life=life)
    action = _choose(state, seat)
    if life == 20:
        assert action == {'type': 'pass_priority'}
    else:
        lethal = _face_action(cards['Lightning Bolt'], seat)
        checked_action(state, RULES, seat, lethal)
        assert AIAgent(archetype='Burn')._early_prowess_burn_action(state, lethal, seat) is None
        initial_turn = state.turn
        for _ in range(16):
            if state.winner is not None:
                break
            actor = state.priority_player
            action = _choose(state, seat) if actor == seat else {'type': 'pass_priority'}
            state = checked_action(state, RULES, actor, action)
        assert state.winner == seat and state.turn == initial_turn


@pytest.mark.parametrize('seat', [1, 2])
def test_synthetic_learned_score_waits_for_the_real_creature_entry(monkeypatch, seat):
    state, _ = _pending_creature(seat)
    scored = []
    assert _choose(state, seat, binding=_synthetic_binding(monkeypatch, scored)) == {'type': 'pass_priority'}
    assert 'cast_spell' in scored


@pytest.mark.parametrize('seat', [1, 2])
def test_synthetic_learned_selected_pending_lethal_is_not_replaced(monkeypatch, seat):
    # Unchanged heuristic may finish its own creature first; the timing guard
    # must not override a learned route that already selected the lethal Bolt.
    state, cards = _pending_creature(seat, life=3)
    scored = []
    action = _choose(state, seat, binding=_synthetic_binding(monkeypatch, scored))
    assert action['type'] == 'cast_spell' and action['card_id'] == cards['Lightning Bolt']
    assert 'cast_spell' in scored


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_counterspell_response_does_not_assume_creature_will_enter(seat):
    state, cards, _, move = position(seat, ['Monastery Swiftspear', 'Lightning Bolt'],
        ['Mountain', 'Mountain'], reserve=['Counterspell', 'Island', 'Island'])
    counter = move('Counterspell', 3-seat, Zone.HAND)
    move('Island', 3-seat, Zone.BATTLEFIELD)
    move('Island', 3-seat, Zone.BATTLEFIELD)
    state = checked_action(state, RULES, seat,
        {'type': 'cast_spell', 'card_id': cards['Monastery Swiftspear']})
    target = state.stack[-1].id
    state = checked_action(state, RULES, seat, {'type': 'pass_priority'})
    state = checked_action(state, RULES, 3-seat,
        {'type': 'cast_spell', 'card_id': counter, 'targets': {'target_stack_id': target}})
    state = checked_action(state, RULES, 3-seat, {'type': 'pass_priority'})
    assert len(state.stack) == 2 and state.priority_player == seat
    action = _face_action(cards['Lightning Bolt'], seat)
    checked_action(state, RULES, seat, action)
    before = serialize_match_snapshot(state)
    assert AIAgent(archetype='Burn')._early_prowess_burn_action(state, action, seat) is None
    assert serialize_match_snapshot(state) == before


def _add_printed(state, raw, seat, zone=Zone.BATTLEFIELD):
    from tests.test_ai_recurring_engines import add
    return add(state, raw['name'], seat, zone, cards={raw['name']: raw})


@pytest.mark.parametrize('seat', [1, 2])
def test_opponent_optional_effect_stays_unknown_without_default_acceptance(seat):
    from ai.pending_effects import _projection_copy, _settle_announced_stack
    from tests.pending_permanent_fullraw import raw_card
    state, _ = _position(3-seat, Step.PRECOMBAT_MAIN)
    state.players[3-seat].mana_pool['G'] = 1
    sage = _add_printed(state, raw_card('Reclamation Sage'), 3-seat, Zone.HAND)
    ring = _add_printed(state, raw_card('Sol Ring'), seat)
    state = checked_action(state, RULES, 3-seat, {'type': 'cast_spell', 'card_id': sage.id})
    state = checked_action(state, RULES, 3-seat, {'type': 'pass_priority'})
    before, rng = serialize_match_snapshot(state), random.getstate()
    projected = _projection_copy(state)
    assert not _settle_announced_stack(projected, player_id=seat)
    assert projected.pending_trigger_order['phase'] == 'targets'
    target = next(move for move in RULES.legal_moves(projected, 3-seat)
                  if move.get('target_card_id') == ring.id)
    projected = checked_action(projected, RULES, 3-seat, target)
    assert not _settle_announced_stack(projected, player_id=seat)
    assert projected.pending_trigger_order['phase'] == 'optional'
    assert projected.pending_trigger_order['current_controller'] == 3-seat
    assert {move['accept'] for move in RULES.legal_moves(projected, 3-seat)
            if move['type'] == 'choose_optional_effect'} == {True, False}
    assert projected.cards[ring.id].zone == Zone.BATTLEFIELD
    assert serialize_match_snapshot(state) == before and random.getstate() == rng


@pytest.mark.parametrize('seat', [1, 2])
def test_future_opponent_trigger_order_is_not_automatically_chosen(seat):
    from ai.pending_effects import _projection_copy, _settle_announced_stack
    from tests.pending_permanent_fullraw import raw_card
    state, cards = _position(seat, Step.PRECOMBAT_MAIN)
    for _ in range(2):
        _add_printed(state, raw_card('Soul Warden'), 3-seat)
    state.trigger_order_choice_players = set()
    state.mechanic_choice_players = state.replacement_choice_players = set()
    assert not state.trigger_order_choice_required
    before, rng = serialize_match_snapshot(state), random.getstate()
    projected = checked_action(_projection_copy(state), RULES, seat,
                              {'type': 'cast_spell', 'card_id': cards['Monastery Swiftspear']})
    assert not _settle_announced_stack(projected, player_id=seat)
    assert projected.pending_trigger_order['current_controller'] == 3-seat
    assert all(move['type'] == 'choose_trigger_order' for move in RULES.legal_moves(projected, 3-seat))
    assert AIAgent(archetype='Burn')._early_prowess_burn_action(
        state, _face_action(cards['Lightning Bolt'], seat), seat) is None
    assert serialize_match_snapshot(state) == before and random.getstate() == rng


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_and_new_prowess_creatures_gain_actual_extra_combat_damage(seat):
    state, cards, _, move = position(seat, ['Monastery Swiftspear', 'Lightning Bolt'],
                                    ['Mountain', 'Mountain'], reserve=['Monastery Swiftspear'])
    existing = move('Monastery Swiftspear', seat, Zone.BATTLEFIELD)
    state.mechanic_choice_players = state.replacement_choice_players = {1, 2}
    state.trigger_order_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    for _ in range(64):
        if state.step == Step.END_COMBAT:
            break
        choice = state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order
        actor = choice.get('player_id', choice.get('current_controller')) if choice else state.priority_player
        if state.step == Step.DECLARE_BLOCKERS and not state.blockers_declared:
            actor, action = 3-seat, {'type': 'block', 'blocks': {}}
        else:
            action = _choose(state, seat) if actor == seat else {'type': 'pass_priority'}
        state = checked_action(state, RULES, actor, action)
    assert state.step == Step.END_COMBAT
    assert state.players[3-seat].life == 13
    assert effective_power(state, existing) == effective_power(state, cards['Monastery Swiftspear']) == 2
    assert state.cards[cards['Lightning Bolt']].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mountains', [5, 6])
def test_preserve_selected_kicker_payment_in_the_future_burn(seat, mountains):
    from ai.action_contract import complete_action
    from rules_engine.action_validation import ActionRejected
    state, cards, _, _ = position(seat, ['Monastery Swiftspear'], ['Mountain'] * mountains)
    raw = next(row for row in json.loads((Path(__file__).parent / 'fixtures/kicker.json').read_bytes())
               if row['name'] == 'Burst Lightning')
    spell = _add_printed(state, raw, seat, Zone.HAND)
    action = complete_action({'type': 'cast_spell', 'card_id': spell.id,
                             'cost_choice': {'id': 'kicker'}, 'targets': {'target_player': 3-seat}})
    before, original, rng = serialize_match_snapshot(state), deepcopy(action), random.getstate()
    announced = checked_action(state, RULES, seat, action)
    assert announced.stack[-1].payload['__kicked'] is True
    assert sum(announced.cards[cid].tapped for cid in state.players[seat].battlefield) == 5
    developed = settle(checked_action(state, RULES, seat,
        {'type': 'cast_spell', 'card_id': cards['Monastery Swiftspear']}), seat, 'Burn', 'master')
    base = {**action, 'cost_choice': {'id': 'base'}}
    base_cast = checked_action(developed, RULES, seat, base)
    assert next(item for item in base_cast.stack if item.source_card_id == spell.id).payload['__kicked'] is False
    if mountains == 5:
        with pytest.raises(ActionRejected):
            checked_action(developed, RULES, seat, action)
    else:
        kicked = settle(checked_action(developed, RULES, seat, action), seat, 'Burn', 'master')
        assert kicked.players[3-seat].life == 16 and effective_power(kicked, cards['Monastery Swiftspear']) == 2
    replacement = AIAgent(archetype='Burn')._early_prowess_burn_action(state, action, seat)
    if mountains == 5:
        assert replacement is None
    else:
        assert replacement['type'] == 'cast_spell' and replacement['card_id'] == cards['Monastery Swiftspear']
    assert action == original and serialize_match_snapshot(state) == before and random.getstate() == rng
