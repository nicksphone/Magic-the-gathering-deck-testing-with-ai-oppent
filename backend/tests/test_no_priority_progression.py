"""Internal turn progression is not a legal player pass; API runs in a local copy."""
import json
from pathlib import Path

import pytest

import main
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add
from tests.test_api_input_contracts import game, persist, snapshot
from tests.test_human_auto_progress import match_at
from tests.test_named_counters import CARDS as COUNTER_CARDS


CARDS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/pending_removal.json').read_text())}
for row in json.loads((Path(__file__).parent / 'fixtures/regression_agent/cards.json').read_text()):
    raw = row['card']
    if raw['name'] == 'Think Twice':
        CARDS[raw['name']] = {**raw, 'power': None, 'toughness': None}


@pytest.fixture(autouse=True)
def disposable_source_only():
    assert not (Path(main.__file__).resolve().parents[1] / '.git').exists(), 'Use a disposable source copy, never tracked/live SQLite'


def prepare(controller, seat, step=Step.UNTAP):
    state = controller.state
    controller.mode = 'player_vs_ai'
    controller.controllers = {1: 'human', 2: 'human'}
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.turn = 3
    state.step = step
    state.passed_priority = set()
    for player in state.players.values():
        while player.hand:
            cid = player.hand.pop()
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
    return state


@pytest.mark.parametrize('seat', [1, 2])
def test_untap_hook_preserves_entered_step_stun_and_snapshot(seat):
    state = match_at(Step.UNTAP, seat).state
    bear = add(state, 'Grizzly Bears', seat, cards=COUNTER_CARDS)
    bear.tapped = True
    bear.counters['stun'] = 2
    rules = RulesEngine()
    rules._apply_step_start_actions(state)
    assert bear.tapped and bear.counters['stun'] == 1
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    before_hand = list(restored.players[seat].hand)
    before_library = list(restored.players[seat].library)
    assert rules.legal_moves(restored, seat) == []
    with pytest.raises(ActionRejected):
        checked_action(restored, rules, seat, {'type': 'pass_priority'})
    assert rules.advance_no_priority_step(restored)
    assert restored.step == Step.UPKEEP and restored.priority_player == seat
    assert restored.passed_priority == set()
    assert restored.players[seat].hand == before_hand
    assert restored.players[seat].library == before_library
    assert restored.cards[bear.id].tapped and restored.cards[bear.id].counters['stun'] == 1
    after = serialize_match_snapshot(restored)
    assert not rules.advance_no_priority_step(restored)
    assert serialize_match_snapshot(restored) == after


@pytest.mark.parametrize('guard', ['pregame', 'winner', 'mechanic', 'replacement', 'trigger_order', 'stack', 'upkeep', 'draw', 'cleanup'])
def test_no_priority_hook_refuses_other_windows_and_continuations(guard):
    state = match_at(Step.UNTAP).state
    if guard == 'pregame':
        state.pregame_pending = True
    elif guard == 'winner':
        state.winner = 0
    elif guard in ('upkeep', 'draw', 'cleanup'):
        state.step = Step(guard)
    elif guard == 'stack':
        state.step = Step.PRECOMBAT_MAIN
        spell = add(state, 'Think Twice', zone=Zone.HAND, cards=CARDS)
        state.players[1].mana_pool = {'U': 2}
        state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': spell.id, 'targets': {}})
        assert state.stack
        state.step = Step.UNTAP  # Invalid restored stack: never resolve it as a turn action.
    else:
        field = {'mechanic': 'pending_mechanic_choice', 'replacement': 'pending_replacement_choice',
                 'trigger_order': 'pending_trigger_order'}[guard]
        setattr(state, field, {'player_id': 1, 'current_controller': 1})
    before = serialize_match_snapshot(state), state.rng.getstate()
    assert not RulesEngine().advance_no_priority_step(state)
    assert (serialize_match_snapshot(state), state.rng.getstate()) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_natural_turn_untaps_once_then_opens_upkeep(seat):
    state = match_at(Step.CLEANUP, 3-seat).state
    bear = add(state, 'Grizzly Bears', seat, cards=COUNTER_CARDS)
    bear.tapped = True
    bear.counters['stun'] = 2
    rules = RulesEngine()
    for _ in range(2):
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.UPKEEP and state.active_player == state.priority_player == seat
    assert state.cards[bear.id].tapped and state.cards[bear.id].counters['stun'] == 1
    assert not rules.advance_no_priority_step(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('control', ['human', 'ai'])
def test_api_untap_is_internal_but_manual_pass_stays_rejected(game, monkeypatch, seat, control):
    client, controller = game
    state = prepare(controller, seat)
    controller.controllers[seat] = control
    persist(controller)
    before = snapshot(controller)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': {'type': 'pass_priority'}})
    assert response.status_code == (422 if control == 'human' else 403)
    assert snapshot(controller) == before
    # One turn-action tick must not query AI or send any checked player action.
    def not_a_player_action(*args, **kwargs):
        raise AssertionError('Untap has no player action')
    monkeypatch.setattr(main, 'checked_action', not_a_player_action)
    monkeypatch.setattr(controller.ai[seat], 'choose_action', not_a_player_action)
    key = f'{seat}{0 if control == "human" else 1}' + 'a' * 30
    headers = {'Idempotency-Key': key, 'X-Match-Revision': str(controller.revision)}
    response = client.post(f'/matches/{state.id}/autoplay?ticks=1', headers=headers)
    assert response.status_code == 200, response.text
    assert controller.state.step == Step.UPKEEP and controller.state.priority_player == seat
    assert not controller.state.passed_priority
    assert not controller.state.players[seat].hand
    assert not any('passes priority' in line for line in controller.state.log)
    after = snapshot(controller)
    retry = client.post(f'/matches/{state.id}/autoplay?ticks=1', headers=headers)
    assert retry.status_code == 200 and snapshot(controller) == after


@pytest.mark.parametrize('seat', [1, 2])
def test_api_upkeep_trigger_and_response_are_not_skipped(game, seat):
    client, controller = game
    state = prepare(controller, seat)
    arena = add(state, 'Phyrexian Arena', seat, cards=CARDS)
    add(state, 'Think Twice', seat, Zone.HAND, cards=CARDS)
    for _ in range(2):
        cid = state.players[seat].library.pop()
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
        state.players[seat].battlefield.append(cid)
    RulesEngine()._apply_step_start_actions(state)
    persist(controller)
    hand = list(state.players[seat].hand)
    library = list(state.players[seat].library)
    life = state.players[seat].life
    response = client.post(f'/matches/{state.id}/autoplay?ticks=100')
    assert response.status_code == 200, response.text
    state = controller.state
    assert state.step == Step.UPKEEP and state.priority_player == seat
    assert len(state.stack) == 1 and state.stack[0].source_card_id == arena.id
    assert state.players[seat].hand == hand and state.players[seat].library == library
    assert state.players[seat].life == life
    assert any(move['type'] == 'cast_spell' for move in controller.rules.legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
def test_api_empty_windows_draw_once_and_stop_for_land(game, seat):
    client, controller = game
    state = prepare(controller, seat)
    persist(controller)
    library = len(state.players[seat].library)
    response = client.post(f'/matches/{state.id}/autoplay?ticks=100')
    assert response.status_code == 200, response.text
    assert controller.state.step == Step.PRECOMBAT_MAIN
    assert len(controller.state.players[seat].library) == library - 1
    assert len(controller.state.players[seat].hand) == 1
    before = serialize_match_snapshot(controller.state)
    assert client.post(f'/matches/{state.id}/autoplay?ticks=100').status_code == 200
    assert serialize_match_snapshot(controller.state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_api_draw_response_window_does_not_draw_again_or_advance(game, seat):
    client, controller = game
    state = prepare(controller, seat, Step.DRAW)
    state.active_player = 3-seat
    RulesEngine()._apply_step_start_actions(state)
    add(state, 'Think Twice', seat, Zone.HAND, cards=CARDS)
    state.players[seat].mana_pool = {'U': 2}
    persist(controller)
    assert state.draws_in_current_draw_step[3-seat] == 1
    before = serialize_match_snapshot(state)
    assert client.post(f'/matches/{state.id}/autoplay?ticks=100').status_code == 200
    assert serialize_match_snapshot(controller.state) == before
