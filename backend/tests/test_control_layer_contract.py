"""Internal metadata validation plus genuine paid layer-two interactions."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
from tests.test_static_aura_control_desired import (
    resource_position, raw_card, COMBAT, ROWS, cast, next_main,
    paid_aura, paid_bounce, restart, snap, Zone, assert_pure_queries,
)
from rules_engine.control_effects import control_layer_view, restore_control_effects, compile_attached_control
from rules_engine.continuous import printed_abilities_suppressed, effective_power, effective_toughness
from game_state.serializers import deserialize_match_snapshot
from game_state.state import MatchFactory, object_incarnation

DOMINATE = json.loads((ROOT / 'backend/tests/fixtures/temporary_control_handler_correction/dominate.json').read_bytes())
PLAINS = json.loads((ROOT / 'backend/tests/fixtures/activated_top_selection/plains.json').read_bytes())


def metadata_position(seat):
    deck = [{'card_name': 'Forest', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=151)
    card = raw_card(state, COMBAT['Grizzly Bears'], seat, Zone.BATTLEFIELD)
    return state, card.id


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_humility_does_not_retroactively_remove_layer_two(seat):
    state, _ = resource_position(seat)
    for _ in range(2):
        raw_card(state, PLAINS, seat, Zone.BATTLEFIELD)
    bear = raw_card(state, COMBAT['Grizzly Bears'], seat, Zone.HAND)
    state = cast(state, seat, bear.id)
    state = next_main(state, 3-seat)
    state, aura = paid_aura(state, 3-seat, bear.id)
    state = next_main(state, seat)
    humility = raw_card(state, ROWS['Humility'], seat, Zone.HAND)
    state = cast(state, seat, humility.id)
    assert state.cards[bear.id].controller == 3-seat
    assert state.cards[aura].attached_to == bear.id
    assert printed_abilities_suppressed(state, bear.id)
    assert effective_power(state, bear.id) == effective_toughness(state, bear.id) == 1
    assert_pure_queries(state, bear.id)
    state = paid_bounce(restart(state), seat, aura)
    assert state.cards[bear.id].controller == seat
    assert state.cards[bear.id].owner == seat
    restart(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_indefinite_underlying_control_is_not_guessed_from_owner(seat):
    state, _ = resource_position(seat)
    bear = raw_card(state, COMBAT['Grizzly Bears'], seat, Zone.HAND)
    state = cast(state, seat, bear.id)
    state = next_main(state, 3-seat)
    dominate = raw_card(state, DOMINATE, 3-seat, Zone.HAND)
    state = cast(state, 3-seat, dominate.id, {'target_card_id': bear.id, 'x_value': 2},
                 cost_choice={'id': 'base'})
    assert state.cards[bear.id].controller == 3-seat
    state = next_main(state, seat)
    state, aura = paid_aura(state, seat, bear.id)
    assert state.cards[bear.id].controller == seat
    state = paid_bounce(restart(state), seat, aura)
    assert state.cards[bear.id].controller == 3-seat
    assert state.cards[bear.id].owner == seat
    assert state.cards[bear.id].summoning_sick
    assert_pure_queries(state, bear.id)
    restart(state)


@pytest.mark.parametrize('bad', [None, {}, (), False, ''])
def test_empty_baseline_still_requires_list_metadata(bad):
    state, cid = metadata_position(1)
    with pytest.raises(ValueError):
        restore_control_effects({'control_effect_base': None, 'control_effects': bad},
                                state.cards[cid], state.players)


@pytest.mark.parametrize('field,value', [('controller', True), ('controller', 3),
    ('timestamp', 0), ('incarnation', -1), ('sequence', -1), ('expires_turn', -1)])
def test_invalid_retained_reference_rejected(field, value):
    state, cid = metadata_position(1)
    effect = {'controller': 1, 'timestamp': 1,
              'incarnation': object_incarnation(state.cards[cid]),
              'sequence': state.cards[cid].zone_change_sequence}
    effect[field] = value
    with pytest.raises(ValueError):
        restore_control_effects({'control_effect_base': 1, 'control_effects': [effect]},
                                state.cards[cid], state.players)


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_snapshot_defaults_and_pure_view(seat):
    state, cid = metadata_position(seat)
    before = snap(state)
    assert 'control_effect_base' not in before['cards'][cid]
    restored = deserialize_match_snapshot(deepcopy(before))
    assert snap(restored) == before
    assert restored.cards[cid].control_effect_base is None
    assert restored.cards[cid].control_effects == []
    assert control_layer_view(restored)[cid] == seat
    assert snap(restored) == before


@pytest.mark.parametrize('key', ['control_effect_base', 'control_effects'])
def test_half_present_snapshot_metadata_rejected(key):
    state, cid = metadata_position(1)
    fields = {'control_effect_base': 1, 'control_effects': []}
    fields.pop(key)
    with pytest.raises(ValueError):
        restore_control_effects(fields, state.cards[cid], state.players)


def test_duplicate_timestamps_rejected():
    state, cid = metadata_position(1)
    effect = {'controller': 1, 'timestamp': 1, 'incarnation': object_incarnation(state.cards[cid]),
              'sequence': state.cards[cid].zone_change_sequence}
    with pytest.raises(ValueError):
        restore_control_effects({'control_effect_base': 1, 'control_effects': [effect, deepcopy(effect)]},
                                state.cards[cid], state.players)


@pytest.mark.parametrize('text,accepted', [
    ('Enchant permanent\nYou control enchanted permanent.', True),
    ('Enchant creature\nYou control enchanted creature.', True),
    ('Enchant permanent\nYou control enchanted permanent.\nDraw a card.', False),
    ('Enchant permanent\nYou control enchanted creature.', False),
    ('Enchant permanent\nYou control enchanted permanent. (Unknown condition.)', False),
])
def test_complete_generic_body_only(text, accepted):
    assert compile_attached_control(text) is accepted
