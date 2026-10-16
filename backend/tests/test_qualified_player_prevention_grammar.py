"""Invalid/legacy grammar PROTOCOLS, not pristine canonical card records."""
from copy import deepcopy

import pytest

from effects.handlers import deal_damage
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.replacement import replacement_options
from tests.damage_life_printed_79 import canonical_base_state, canonical_card, raw_card


PLAYER = 'If a source an opponent controls would deal damage to you, prevent 1 of that damage'
INVALID_QUALIFIED = (
    ('creature-only', PLAYER.replace('to you,', 'to a creature you control,') + '.'),
    ('permanent-only', PLAYER.replace('to you,', 'to a permanent you control,') + '.'),
    ('activated-prefix', '{W}: ' + PLAYER + '.'),
    ('conditional-prefix', 'If you control a Plains, ' + PLAYER + '.'),
    ('quoted-prefix', 'It has "' + PLAYER + '."'),
    ('unknown-unless-suffix', PLAYER + ' unless you pay {1}.'),
)


def protocol_state(seat, text):
    state = canonical_base_state()
    # Deliberately invalid or compatibility grammar inputs, not fabricated
    # official Oracle data or a claimed legal effect producer.
    ward = CardInstance(id='grammar-protocol', name='PREVENTION GRAMMAR PROTOCOL',
        owner=seat, controller=seat, zone=Zone.BATTLEFIELD,
        types=['Enchantment'], oracle_text=text)
    state.cards[ward.id] = ward
    state.players[seat].battlefield.append(ward.id)
    source = canonical_card('Lightning Bolt', id='genuine-source', owner=3-seat,
                            controller=3-seat, zone=Zone.STACK)
    state.cards[source.id] = source
    return state, ward, source


def exercise(seat, text, route, eligible):
    state, ward, source = protocol_state(seat, text)
    before = serialize_match_snapshot(state)
    raw_before = deepcopy(raw_card('Lightning Bolt'))
    if route == 'query':
        rows = replacement_options(state, 'damage_to_player', target_player=seat,
                                   source_card_id=source.id, amount=3)
        assert [row['source_id'] for row in rows] == ([ward.id] if eligible else [])
        assert serialize_match_snapshot(state) == before
    else:
        dealt = deal_damage(state, 3-seat, {'target_player': seat, 'amount': 3,
                                          '__source_card_id': source.id})
        assert dealt == (2 if eligible else 3)
        assert state.players[seat].life == 20-dealt
    assert state.cards[ward.id].oracle_text == text
    assert raw_card('Lightning Bolt') == raw_before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['query', 'application'])
@pytest.mark.parametrize('label,text', INVALID_QUALIFIED, ids=[p[0] for p in INVALID_QUALIFIED])
def test_invalid_qualified_protocol_does_not_prevent_player_damage(seat, route, label, text):
    exercise(seat, text, route, False)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['query', 'application'])
@pytest.mark.parametrize('label,text', INVALID_QUALIFIED, ids=[p[0] for p in INVALID_QUALIFIED])
def test_existing_unqualified_protocol_behavior_is_not_cleaned_up(seat, route, label, text):
    # This intentionally characterizes legacy overmatching, not correct Oracle.
    exercise(seat, text.replace('a source an opponent controls', 'a source'), route, True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['query', 'application'])
@pytest.mark.parametrize('recipient', ['you or a permanent you control', 'you or a creature you control'])
def test_complete_qualified_you_or_permanent_protocol_still_includes_player(seat, route, recipient):
    text = PLAYER.replace('to you,', 'to ' + recipient + ',') + '.'
    exercise(seat, text, route, True)
