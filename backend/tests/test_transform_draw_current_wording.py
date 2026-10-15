"""Current canonical wording and explicit legacy/negative grammar vectors."""
import pytest

from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine
from rules_engine.events import TRANSFORM_DRAW_RE
from rules_engine.stack_engine import resolve_top_of_stack
from tests.canonical_positive_fixtures import raw_card as seed_card
from tests.day_night_apnap_canonical import CATHAR, permanent, raw_card


STYLES = ('current', 'legacy')
CURRENT = 'a permanent you control enters transformed'
LEGACY = 'a permanent enters the battlefield under your control transformed'


def wording(style):
    text = raw_card('Corruption of Towashi')['oracle_text']
    assert CURRENT in text
    return text if style == 'current' else text.replace(CURRENT, LEGACY)


def state_with_observer(seat, style, target_controller=None):
    forest = seed_card('Forest')
    deck = [{**forest, 'quantity': 60, 'card_name': forest['name']}]
    state = MatchFactory.from_decks(deck, deck, seed=77)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    observer = permanent('observer', 'Corruption of Towashi', seat)
    # Only this explicit legacy vector differs from the complete official object.
    observer.oracle_text = wording(style)
    controller = seat if target_controller is None else target_controller
    for card in (observer, permanent('first', CATHAR, controller),
                 permanent('second', CATHAR, controller)):
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)
    return state


def transform(state, card_id):
    card = state.cards[card_id]
    resolve_effect(state, card.controller, 'transform_card',
                   {'target_card_id': card_id, 'face_index': 1})
    assert state.cards[card_id].selected_face_index == 1


@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('seat', (1, 2))
def test_actual_transform_has_optional_controller_draw_for_both_wordings(style, seat):
    state = state_with_observer(seat, style)
    transform(state, 'first')
    assert len(state.stack) == 1
    trigger = state.stack[0]
    assert trigger.source_card_id == 'observer' and trigger.controller == seat
    assert trigger.effect_key == 'draw_cards'
    assert trigger.payload['target_player'] == seat and trigger.payload['amount'] == 1
    assert trigger.payload['__may'] is True and trigger.payload['__may_choose'] is True
    assert '__once_on_accept' in trigger.payload


@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('seat', (1, 2))
def test_opposing_transform_does_not_trigger_observer(style, seat):
    state = state_with_observer(seat, style, target_controller=3-seat)
    transform(state, 'first')
    assert not state.stack and state.pending_trigger_order is None


@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('accept', (False, True))
def test_once_per_turn_is_consumed_only_by_accepted_draw_after_restore(style, seat, accept):
    state = state_with_observer(seat, style)
    before = len(state.players[seat].hand)
    transform(state, 'first')
    assert len(state.stack) == 1
    resolve_top_of_stack(state)
    assert state.pending_trigger_order['phase'] == 'optional'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    rules = RulesEngine()
    choice = next(move for move in rules.legal_moves(state, seat)
                  if move['type'] == 'choose_optional_effect' and move['accept'] is accept)
    rules.take_action(state, seat, choice, reject_invalid=True)
    assert len(state.players[seat].hand) == before + int(accept)
    assert state.pending_trigger_order is None and not state.stack
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    transform(state, 'second')
    assert len(state.stack) == (0 if accept else 1)


@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('old,new', (
    ('a permanent you control transforms', 'a permanent an opponent controls transforms'),
    ('you may draw a card.', 'you may draw two cards.'),
    ('Do this only once each turn', 'Do this only once each game'),
    ('transforms or', 'attacks or'),
))
def test_wording_fix_does_not_admit_different_selector_reward_or_limit(style, old, new):
    text = wording(style)
    assert old in text
    assert not TRANSFORM_DRAW_RE.search(text.replace(old, new))
