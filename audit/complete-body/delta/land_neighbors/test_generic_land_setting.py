"""Full canonical static layer seams; attachments here are trusted positions."""
import json
import hashlib
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.basic_land_layer import permanent_land_replacement
from rules_engine.colors import card_color_symbols
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine.land_types import effective_type_line
from rules_engine.mana import mana_source_outputs
from rules_engine.type_effects import effective_types
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_basic_land_layer_goldens import add, position, setter

FIXTURES = Path(__file__).parent / 'fixtures'
RAW = json.loads((FIXTURES / 'generic_land_setting/canonical.json').read_text())
RAW.update({row['name']: row for row in map(json.loads,
    (FIXTURES / 'builtin_face_colors/canonical.jsonl').read_text().splitlines())})


def test_full_inherited_raw_rows_match_provenance():
    rows = json.loads((FIXTURES / 'generic_land_setting/canonical.json').read_text())
    proof = json.loads((FIXTURES / 'generic_land_setting/provenance.json').read_text())
    for name, item in proof['cards'].items():
        assert hashlib.sha256(json.dumps(rows[name], sort_keys=True,
            separators=(',', ':')).encode()).hexdigest() == item['fullrow_sha256']


def source(state, seat, target):
    row = RAW['Imprisoned in the Moon']
    card = raw_add(state, row['name'], seat, cards={row['name']: {
        **row, 'power': row.get('power'), 'toughness': row.get('toughness')}})
    assign_static_order_on_battlefield_entry(state, card.id)
    card.attached_to = target.id
    return card


def test_complete_canonical_instruction_retains_no_subtype_and_explicit_mana():
    parsed = permanent_land_replacement(RAW['Imprisoned in the Moon']['oracle_text'])
    assert parsed, 'The complete canonical instruction must compile'
    assert parsed.granted_mana == 'C'


@pytest.mark.parametrize('color', list('WUBRGC'))
def test_generic_parameter_not_a_card_name(color):
    # Synthetic grammar parameters, not additional canonical-card certificates.
    text = f'Enchanted permanent is a colorless land with "{{T}}: Add {{{color}}}" and loses all other card types and abilities.'
    parsed = permanent_land_replacement(text)
    assert parsed and parsed.granted_mana == color


@pytest.mark.parametrize('tail', ['\nThen perform an unspecified operation.',
    ' (Then perform an unspecified operation.)', ' and has flying.',
    '\nWhen this permanent enters, draw a card.'])
def test_unknown_whole_body_is_not_erased(tail):
    assert permanent_land_replacement(RAW['Imprisoned in the Moon']['oracle_text'] + tail) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('owner', ['own', 'foreign'])
@pytest.mark.parametrize('kind', ['creature', 'land', 'planeswalker'])
def test_canonical_layer_grant_and_departure_restore(seat, owner, kind):
    state = position(seat)
    target_seat = seat if owner == 'own' else 3-seat
    if kind == 'planeswalker':
        row = RAW['The Wandering Emperor']
        target = raw_add(state, row['name'], target_seat, cards={row['name']: {
            **row, 'power': row.get('power'), 'toughness': row.get('toughness')}})
        assign_static_order_on_battlefield_entry(state, target.id)
    else:
        target = add(state, 'Royal Assassin' if kind == 'creature' else 'Forest', target_seat)
    original_types = list(effective_types(state, target))
    aura = source(state, seat, target)
    before = serialize_match_snapshot(state)
    for current in [state, deserialize_match_snapshot(before)]:
        card = current.cards[target.id]
        assert effective_types(current, card) == ['Land']
        assert effective_type_line(current, card) in {'Land', 'Legendary Land', 'Basic Land'}
        assert card_color_symbols(card, current) == set()
        assert printed_abilities_suppressed(current, card.id)
        assert mana_source_outputs(current, target_seat, card.id) == {'C': 1}
        assert card.oracle_text == target.oracle_text
    assert serialize_match_snapshot(state) == before, 'Queries cannot mutate the position'
    restored = deserialize_match_snapshot(before)
    restored.priority_player = target_seat
    restored.players[target_seat].mana_pool = {}
    paid = checked_action(restored, RulesEngine(), target_seat,
        {'type': 'tap_land_for_mana', 'card_id': target.id, 'color': 'C'})
    assert paid.cards[target.id].tapped
    assert paid.players[target_seat].mana_pool.get('C') == 1
    assert serialize_match_snapshot(deserialize_match_snapshot(serialize_match_snapshot(paid))) == serialize_match_snapshot(paid)
    # Trusted departure seam: no claim that every destruction route is exercised.
    state.players[seat].battlefield.remove(aura.id)
    state.players[seat].graveyard.append(aura.id)
    aura.move_to_zone(Zone.GRAVEYARD)
    assert effective_types(state, target) == original_types


@pytest.mark.parametrize('seat', [1, 2])
def test_later_creature_ability_loss_cannot_suppress_noncreature_land_grant(seat):
    state = position(seat)
    target = add(state, 'Royal Assassin', seat)
    source(state, seat, target)
    add(state, 'Humility', 3-seat)
    assert effective_types(state, target) == ['Land']
    assert mana_source_outputs(state, seat, target.id) == {'C': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_land_setting_source_ability_loss_ends_its_target_effect(seat):
    state = position(seat)
    target = add(state, 'Royal Assassin', seat)
    aura = source(state, seat, target)
    setter(state, 'Song of the Dryads', 3-seat, aura)
    assert effective_types(state, aura) == ['Land']
    assert effective_types(state, target) == ['Creature']
    assert not printed_abilities_suppressed(state, target.id)
    assert mana_source_outputs(state, seat, target.id) == {}
    assert mana_source_outputs(state, seat, aura.id) == {'G': 1}
