"""Canonical joint fixed-cost witnesses, exact fixtures and immutable roots."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import check_cost_option_available, collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.spell_cost_witness import fixed_cost_selections
from tests.test_ai_recurring_engines import add as canonical_add
from tests.test_spell_cost_overlap_investigation import ROWS as OVERLAP_ROWS, position, unchanged_root


FIXTURES = Path(__file__).parent / 'fixtures'
ROWS = dict(OVERLAP_ROWS)
for filename in ('mana_resources.json', 'spell_additional_costs.json', 'additive_mana.json'):
    for raw in json.loads((FIXTURES / filename).read_text()):
        if raw['name'] not in ROWS:
            ROWS[raw['name']] = raw


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    raw = ROWS[name]
    # Existing helper requires nullable stat keys; absence stays unknown and
    # the canonical source record itself is never rewritten.
    card = canonical_add(state, name, seat, zone, cards={name: {
        **raw, 'power': raw.get('power'), 'toughness': raw.get('toughness')}})
    card.summoning_sick = False
    return card


def setup(seat, family, has_fuel):
    state = position(seat)
    if family == 'tower':
        add(state, 'Phyrexian Tower', seat)
        victim = add(state, 'Raging Goblin', seat)
        fuel = add(state, 'Ornithopter', seat) if has_fuel else None
        name, key = 'Village Rites', 'sacrifice_card_ids'
    elif family == 'prospector':
        victim = add(state, 'Skirk Prospector', seat)
        fuel = add(state, 'Raging Goblin', seat) if has_fuel else None
        name, key = 'Goblin Grenade', 'sacrifice_card_ids'
    else:
        add(state, 'Skirge Familiar', seat)
        victim = add(state, 'Island', seat, Zone.HAND)
        fuel = add(state, 'Swamp', seat, Zone.HAND) if has_fuel else None
        state.players[seat].mana_pool['R'] = 1
        name, key = 'Tormenting Voice', 'discard_card_ids'
    spell = add(state, name, seat, Zone.HAND)
    option = next(o for o in collect_cost_options(state, seat, spell) if o.id == 'base')
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'cost_choice': {'id': 'base', key: [victim.id]}}
    if family == 'prospector':
        action['targets'] = {'target_player': 3-seat}
    return state, spell, option, victim, fuel, action


def physical_witness(state, seat, spell, option, selection):
    return can_pay_with_pool_and_lands(state, seat, option.mana_cost,
        card_name=spell.name, spell_types=set(spell.types), oracle_text=spell.oracle_text,
        source_card_id=spell.id, cast_resource_card=spell,
        reserved_card_ids={spell.id, *selection['discard_card_ids'], *selection['sacrifice_card_ids']})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['tower', 'prospector', 'familiar'])
@pytest.mark.parametrize('has_fuel', [False, True])
def test_joint_fixed_cost_existence_and_explicit_execution(seat, family, has_fuel):
    state, spell, option, victim, fuel, action = setup(seat, family, has_fuel)
    before = serialize_match_snapshot(state)
    replay = deserialize_match_snapshot(before)
    with unchanged_root(state), unchanged_root(replay):
        for root in (state, replay):
            assert check_cost_option_available(root, seat, root.cards[spell.id], option) == has_fuel
            assert check_cost_option_available(root, seat, root.cards[spell.id], option) == has_fuel
        if not has_fuel:
            with pytest.raises(ActionRejected):
                checked_action(state, RulesEngine(), seat, action)
            return
        result = checked_action(state, RulesEngine(), seat, action)
        restored_result = checked_action(replay, RulesEngine(), seat, action)
    assert serialize_match_snapshot(result) == serialize_match_snapshot(restored_result)
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.cards[victim.id].zone == result.cards[fuel.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_search_reaches_payable_selection_after_unpayable_first_candidate(seat):
    state = position(seat)
    pet = add(state, 'Blood Pet', seat)
    victim = add(state, 'Ornithopter', seat)
    spell = add(state, 'Village Rites', seat, Zone.HAND)
    option = next(o for o in collect_cost_options(state, seat, spell) if o.id == 'base')
    with unchanged_root(state):
        selections = list(fixed_cost_selections(state, seat, spell.id, option))
        assert selections[0]['sacrifice_card_ids'] == [pet.id]
        assert not physical_witness(state, seat, spell, option, selections[0])
        assert selections[1]['sacrifice_card_ids'] == [victim.id]
        assert physical_witness(state, seat, spell, option, selections[1])
        assert check_cost_option_available(state, seat, spell, option)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, {
                'type': 'cast_spell', 'card_id': spell.id,
                'cost_choice': {'id': 'base', 'sacrifice_card_ids': [pet.id]}})
        result = checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': spell.id,
            'cost_choice': {'id': 'base', 'sacrifice_card_ids': [victim.id]}})
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.cards[pet.id].zone == result.cards[victim.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_exhaustive_selections_are_not_frozen_or_reserved_before_mana(seat):
    state = position(seat)
    add(state, 'Skirge Familiar', seat)
    for _ in range(3):
        add(state, 'Island', seat, Zone.HAND)
    spell = add(state, "Kaervek's Spite", seat, Zone.HAND)
    option, = collect_cost_options(state, seat, spell)
    assert option.discard_all and option.sacrifice_all
    with unchanged_root(state):
        assert list(fixed_cost_selections(state, seat, spell.id, option)) == [
            {'discard_card_ids': [], 'sacrifice_card_ids': []}]
        assert check_cost_option_available(state, seat, spell, option)
        result = checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': spell.id,
            'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat}})
    assert result.cards[spell.id].zone == Zone.STACK
    assert not result.players[seat].hand and not result.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_fixed_sacrifice_retains_legal_tap_then_sacrifice_payment(seat):
    state = position(seat)
    land = add(state, 'Forest', seat)
    spell = add(state, 'Crop Rotation', seat, Zone.HAND)
    option, = collect_cost_options(state, seat, spell)
    with unchanged_root(state):
        assert check_cost_option_available(state, seat, spell, option)
        result = checked_action(state, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': spell.id,
            'cost_choice': {'id': 'base', 'sacrifice_card_ids': [land.id]}})
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.cards[land.id].zone == Zone.GRAVEYARD


def test_existing_canonical_fixture_bytes_are_pinned():
    ledger = json.loads((FIXTURES / 'cost_reservation_overlap/provenance.json').read_text())
    assert hashlib.sha256((FIXTURES / 'cost_reservation_overlap/canonical.json').read_bytes()).hexdigest() == ledger['canonical_json_sha256']
    for filename, digest in {
        'mana_resources.json': '5441cd897c0090e14b458979a157c5c54aa75b1558a3d1db8dddf24ec10efe9f',
        'spell_additional_costs.json': '713a82dbf8e001d697d781baf6e9fd2e023d408cbfe39497a06b0c52d52c0c4b',
        'additive_mana.json': '007c02feda85d778b3114e4e349ae1cad771b8436897c900975149623e7216b3',
    }.items():
        assert hashlib.sha256((FIXTURES / filename).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('has_fuel', [False, True])
def test_all_fixed_discards_are_reserved_together(seat, has_fuel):
    state = position(seat)
    add(state, 'Skirge Familiar', seat)
    for name in ('Island', 'Forest', *(['Swamp'] if has_fuel else [])):
        add(state, name, seat, Zone.HAND)
    spell = add(state, 'Cathartic Reunion', seat, Zone.HAND)
    state.players[seat].mana_pool['R'] = 1
    option, = collect_cost_options(state, seat, spell)
    assert option.discard_cards == 2
    with unchanged_root(state):
        selections = list(fixed_cost_selections(state, seat, spell.id, option))
        assert len(selections) == (3 if has_fuel else 1)
        assert all(len(s['discard_card_ids']) == 2 for s in selections)
        assert check_cost_option_available(state, seat, spell, option) == has_fuel
