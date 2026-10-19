"""Canonical positive episodes; grammar query regressions are not card claims."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine import casting_resources
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.colors import card_color_symbols
from rules_engine.continuous import effective_power, effective_toughness, has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.static_conditions import evaluate_static_condition
from tests.test_canonical_land_animation_audit import FAMILIES, ROWS, action, position, resolve, snapshot
from tests.test_canonical_global_flash_audit import ROWS as FLASH_ROWS
from tests.test_basic_land_layer_goldens import CARDS
from tests.test_linked_damage_targets import raw_card


DIRECTORY = Path(__file__).parent / 'fixtures/color_state_forwarding'
CANONICAL = {}
for entry in json.loads((DIRECTORY / 'provenance.json').read_text())['cards']:
    raw = (DIRECTORY / entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    row = json.loads(raw)
    assert row['oracle_id'] == entry['oracle_id']
    CANONICAL[row['name']] = row


def animated(seat, name='Celestial Colonnade'):
    state, land = position(seat, name)
    result = resolve(checked_action(state, RulesEngine(), seat, action(land)))
    return result, result.cards[land.id]


def song_after_animation(seat):
    state, land = animated(seat)
    permission = raw_card(state, FLASH_ROWS['Leyline of Anticipation'], seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, permission.id)
    song = raw_card(state, CARDS['Song of the Dryads'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 2, 'G': 1}
    result = resolve(checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': song.id, 'targets': {'target_card_id': land.id},
    }))
    assert result.cards[song.id].attached_to == land.id
    return result, result.cards[song.id], result.cards[land.id]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('color', ['white', 'blue'])
def test_grammar_query_uses_state_after_canonical_song_colorless_replacement(seat, color):
    state, source, land = song_after_animation(seat)
    before = snapshot(state)
    assert card_color_symbols(land, state) == set()
    # Query string only: NOT the Oracle text of a fictional conditional Aura.
    assert evaluate_static_condition(state, source, land, 'enchanted land is ' + color) is False
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_resource_color_query_receives_exact_readonly_state(monkeypatch, seat):
    state, land = animated(seat)
    spell = raw_card(state, CANONICAL['Ephemeral Shields'], seat, Zone.HAND)
    before = snapshot(state)
    calls = []
    native = casting_resources.card_color_symbols
    def observe(card, state_arg=None):
        calls.append((card.id, state_arg))
        return native(card, state_arg)
    monkeypatch.setattr(casting_resources, 'card_color_symbols', observe)
    candidates = casting_resources.resource_candidates(state, seat, spell)
    assert candidates['convoke'] == [{'card_id': land.id, 'pay_as': ['generic', 'W', 'U']}]
    assert snapshot(state) == before
    assert calls == [(land.id, state)]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_full_canonical_favor_conditional_aura_checked_episode(seat, name):
    state, land = animated(seat, name)
    aura = raw_card(state, CANONICAL['Favor of the Overbeing'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'G': 1}
    before = snapshot(state)
    result = resolve(checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': aura.id, 'targets': {'target_card_id': land.id},
    }))
    assert result.cards[aura.id].attached_to == land.id
    expected = 5 if name == 'Celestial Colonnade' else 2
    assert (effective_power(result, land.id), effective_toughness(result, land.id)) == (expected, expected)
    assert result.cards[land.id].colors == ROWS[name]['colors']
    assert sum(result.players[seat].mana_pool.values()) == 0
    assert snapshot(state) == before
    after = snapshot(result)
    assert snapshot(deserialize_match_snapshot(after)) == after


@pytest.mark.parametrize('seat', [1, 2])
def test_full_canonical_shields_real_colored_convoke_and_invalid_color_rollback(seat):
    state, land = animated(seat)
    spell = raw_card(state, CANONICAL['Ephemeral Shields'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1}
    before = snapshot(state)
    def cast(color):
        return {'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': land.id},
                'resource_payment': {'convoke': [{'card_id': land.id, 'pay_as': color}]}}
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, cast('G'))
    assert snapshot(state) == before
    result = resolve(checked_action(state, RulesEngine(), seat, cast('W')))
    assert result.cards[land.id].tapped
    assert has_keyword(result, land.id, 'indestructible')
    assert sum(result.players[seat].mana_pool.values()) == 0
    assert result.cards[land.id].colors == ROWS['Celestial Colonnade']['colors']
    assert snapshot(state) == before
    after = snapshot(result)
    assert snapshot(deserialize_match_snapshot(after)) == after


@pytest.mark.parametrize('seat', [1, 2])
def test_unsupported_grammar_condition_remains_unknown(seat):
    state, source, land = song_after_animation(seat)
    before = snapshot(state)
    assert evaluate_static_condition(state, source, land, 'enchanted land is purple') is None
    assert snapshot(state) == before
