"""Canonical reservation boundaries: controls and strict known-gap reproducers.

Run against the hash-pinned parent-qualified source, not uncomposed d88 HEAD.
No Oracle text/keywords/costs are rewritten to manufacture mechanic overlaps.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, MatchState, PlayerState, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.casting_resources import resource_payment
from rules_engine.card_types import printed_card_types
from rules_engine.costs import collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.mana import _payment_requirements, _spell_payment_plan, auto_pay_cost
from rules_engine.mana_abilities import activate_mana_ability, ability_outputs, mana_ability_specs


FIXTURES = Path(__file__).parent / 'fixtures'
DIRECTORY = FIXTURES / 'cost_reservation_overlap'
ROWS = json.loads((DIRECTORY / 'canonical.json').read_text())
EXISTING = json.loads((FIXTURES / 'mana_abilities.json').read_text())
ROWS.update({row['name']: row for row in EXISTING if row['name'] not in ROWS})


class ReservedResourceContractFailure(AssertionError):
    """Only the reproduced reservation failure may be marked expected."""


def position(seat):
    return MatchState('canonical-cost-overlap',
                      players={p: PlayerState(p, f'Player {p}') for p in (1, 2)},
                      cards={}, stack=[], rng=random.Random(37),
                      active_player=seat, priority_player=seat, step=Step.PRECOMBAT_MAIN,
                      pregame_pending=False, kept_hands={1, 2})


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    raw = ROWS[name]
    cid = f'p{seat}-{len(state.cards) + 1:03d}'

    def numeric(key):
        value = raw.get(key)
        return int(value) if value is not None and str(value).lstrip('-').isdigit() else None

    card = CardInstance(cid, name, seat, seat, zone,
                        printed_card_types(raw.get('type_line') or ''),
                        mana_cost=raw.get('mana_cost') or '',
                        oracle_text=raw.get('oracle_text') or '',
                        type_line=raw.get('type_line') or '',
                        power=numeric('power'), toughness=numeric('toughness'),
                        colors=raw.get('colors'), keywords=list(raw.get('keywords') or []),
                        layout=raw.get('layout') or '', summoning_sick=False)
    state.cards[cid] = card
    getattr(state.players[seat], zone.value).append(cid)
    return card


@contextmanager
def unchanged_root(state):
    before = serialize_match_snapshot(state)
    try:
        yield
    finally:
        assert serialize_match_snapshot(state) == before


def cast(spell, **fields):
    return {'type': 'cast_spell', 'card_id': spell.id, **fields}


def source_overlap(seat, name, extra_fuel=False):
    state = position(seat)
    add(state, 'Skirge Familiar', seat)
    spell = add(state, name, seat, Zone.HAND)
    if name == 'Village Rites':
        held = add(state, 'Raging Goblin', seat)
        cost = {'id': 'base', 'sacrifice_card_ids': [held.id]}
    else:
        held = add(state, 'Island', seat, Zone.HAND)
        cost = {'id': 'base', 'discard_card_ids': [held.id]}
        state.players[seat].mana_pool['R'] = 1
    fuel = add(state, 'Swamp', seat, Zone.HAND) if extra_fuel else None
    return state, spell, held, fuel, cast(spell, cost_choice=cost)


def test_canonical_records_and_provenance_are_pinned():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert provenance['source_records_verified'] == 38690
    assert provenance['http_requests'] == 0 and not provenance['facts_modified']
    assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == provenance['canonical_json_sha256']
    for name, pin in provenance['rows'].items():
        raw = ROWS[name]
        assert raw['id'] == pin['id'] and raw['oracle_id'] == pin['oracle_id']
        canonical = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(canonical).hexdigest() == pin['raw_canonical_sha256']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Tormenting Voice'])
def test_casting_source_cannot_fund_its_own_mana_payment(seat, name):
    state, spell, held, _, action = source_overlap(seat, name)
    assert spell.id in state.players[seat].hand
    with unchanged_root(state), pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Tormenting Voice'])
def test_explicit_source_reservation_rejects_impossible_mana_without_mutation(seat, name):
    state, spell, held, _, _ = source_overlap(seat, name)
    with unchanged_root(state):
        assert not auto_pay_cost(state, seat, spell.mana_cost, card_name=spell.name,
                                 spell_types=set(spell.types), oracle_text=spell.oracle_text,
                                 source_card_id=spell.id, cast_resource_card=spell,
                                 reserved_card_ids=[spell.id, held.id])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Tormenting Voice'])
def test_mana_can_consume_other_fuel_while_preserving_exact_cost_and_source(seat, name):
    state, spell, held, fuel, action = source_overlap(seat, name, extra_fuel=True)
    # Source last is a valid hand order and avoids the independently reproduced
    # source-consumption bug; no card's printed facts are changed.
    state.players[seat].hand.remove(spell.id)
    state.players[seat].hand.append(spell.id)
    with unchanged_root(state):
        result = checked_action(state, RulesEngine(), seat, action)
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.cards[held.id].zone == result.cards[fuel.id].zone == Zone.GRAVEYARD
    assert sum('for additional cost' in line for line in result.log) == (name == 'Village Rites')
    assert result.players[seat].mana_pool['B'] == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('explicit', [False, True])
def test_selected_sacrifice_can_tap_for_mana_before_being_sacrificed(seat, explicit):
    state = position(seat)
    forest = add(state, 'Forest', seat)
    spell = add(state, 'Crop Rotation', seat, Zone.HAND)
    cost = {'id': 'base', **({'sacrifice_card_ids': [forest.id]} if explicit else {})}
    with unchanged_root(state):
        result = checked_action(state, RulesEngine(), seat, cast(spell, cost_choice=cost))
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.cards[forest.id].zone == Zone.GRAVEYARD
    assert not result.players[seat].battlefield
    assert result.players[seat].mana_pool['G'] == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source', ['tower', 'discard'])
def test_exhaustive_costs_select_only_remaining_postmana_resources(seat, source):
    state = position(seat)
    if source == 'tower':
        tower = add(state, 'Phyrexian Tower', seat)
        swamp = add(state, 'Swamp', seat)
        fuel = [add(state, 'Raging Goblin', seat)]
        remaining = [tower, swamp]
    else:
        remaining = [add(state, 'Skirge Familiar', seat)]
        fuel = [add(state, 'Island', seat, Zone.HAND) for _ in range(3)]
    leftover = add(state, 'Forest', seat, Zone.HAND)
    spell = add(state, "Kaervek's Spite", seat, Zone.HAND)
    option, = collect_cost_options(state, seat, spell)
    assert option.discard_all and option.sacrifice_all
    action = cast(spell, cost_choice={'id': 'base'}, targets={'target_player': 3-seat})
    with unchanged_root(state):
        result = checked_action(state, RulesEngine(), seat, action)
    assert result.cards[spell.id].zone == Zone.STACK
    assert not result.players[seat].hand and not result.players[seat].battlefield
    assert all(result.cards[c.id].zone == Zone.GRAVEYARD for c in [*fuel, *remaining, leftover])
    assert sum('for additional cost' in line for line in result.log) == len(remaining)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source', ['tower', 'discard'])
def test_exhaustive_payments_cannot_be_narrowed_to_a_selected_subset(seat, source):
    state = position(seat)
    permanent = add(state, 'Swamp', seat)
    card = add(state, 'Forest', seat, Zone.HAND)
    spell = add(state, "Kaervek's Spite", seat, Zone.HAND)
    state.players[seat].mana_pool['B'] = 3
    key, selected = ('sacrifice_card_ids', permanent.id) if source == 'tower' else ('discard_card_ids', card.id)
    with unchanged_root(state), pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, cast(spell,
                       cost_choice={'id': 'base', key: [selected]}, targets={'target_player': 3-seat}))


def escape_position(seat, initial=3):
    state = position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    creature = add(state, 'Raging Goblin', seat)
    spell = add(state, 'Woe Strider', seat, Zone.GRAVEYARD)
    grave = [add(state, 'Island', seat, Zone.GRAVEYARD).id for _ in range(initial)]
    state.players[seat].mana_pool['C'] = 3
    return state, tower, creature, spell, grave


@pytest.mark.parametrize('seat', [1, 2])
def test_native_escape_can_use_card_created_by_mana_payment(seat):
    state, _, creature, spell, grave = escape_position(seat)
    with unchanged_root(state):
        result = checked_action(state, RulesEngine(), seat, cast(spell,
                                from_graveyard=True, cost_choice={'id': 'escape'}))
    assert result.cards[spell.id].zone == Zone.STACK
    assert all(result.cards[cid].zone == Zone.EXILE for cid in [*grave, creature.id])


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_mana_preparation_is_a_real_escape_control(seat):
    state, tower, creature, spell, grave = escape_position(seat)
    spec = next(spec for spec in mana_ability_specs(tower, state) if 'Sacrifice' in spec[1])
    prepared = deepcopy(state)
    with unchanged_root(state):
        assert activate_mana_ability(prepared, seat, tower.id, spec[0], 'B',
                                     payment_choices={'sacrifice_card_ids': [creature.id]})
    assert prepared.cards[creature.id].zone == Zone.GRAVEYARD
    with unchanged_root(prepared):
        result = checked_action(prepared, RulesEngine(), seat, cast(spell,
                                from_graveyard=True, cost_choice={'id': 'escape'},
                                escape_exile_ids=[*grave, creature.id]))
    assert result.cards[spell.id].zone == Zone.STACK
    assert all(result.cards[cid].zone == Zone.EXILE for cid in [*grave, creature.id])


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_escape_fuel_and_mana_sacrifice_have_distinct_destinations(seat):
    state, _, creature, spell, grave = escape_position(seat, initial=4)
    with unchanged_root(state):
        result = checked_action(state, RulesEngine(), seat, cast(spell,
                                from_graveyard=True, cost_choice={'id': 'escape'},
                                escape_exile_ids=grave))
    assert result.cards[creature.id].zone == Zone.GRAVEYARD
    assert all(result.cards[cid].zone == Zone.EXILE for cid in grave)


@pytest.mark.parametrize('seat', [1, 2])
def test_underworld_breach_grant_is_not_an_admitted_escape_delve_reproducer(seat):
    state = position(seat)
    add(state, 'Underworld Breach', seat)
    spell = add(state, 'Treasure Cruise', seat, Zone.GRAVEYARD)
    for _ in range(10):
        add(state, 'Island', seat, Zone.GRAVEYARD)
    state.players[seat].mana_pool['U'] = 1
    with unchanged_root(state):
        assert not collect_cost_options(state, seat, spell)
        assert not any(move.get('card_id') == spell.id for move in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('explicit', [False, True])
def test_resource_substitution_respects_external_reservation_contract(seat, explicit):
    state = position(seat)
    spell = add(state, 'Treasure Cruise', seat, Zone.HAND)
    ids = [add(state, 'Island', seat, Zone.GRAVEYARD).id for _ in range(7)]
    state.players[seat].mana_pool['U'] = 1
    req = _payment_requirements(spell.mana_cost, False, 0, 0, 0)[0]
    choices = {'delve': ids} if explicit else None
    with unchanged_root(state):
        assert resource_payment(state, seat, spell, req, {'delve': ids}, reserved_card_ids=[ids[0]]) is None
        plan = _spell_payment_plan(state, seat, req, payment_context=('spell', {'Sorcery'}),
                                   oracle_text=spell.oracle_text, source_card_id=spell.id,
                                   card=spell, resource_choices=choices, reserved_card_ids=[ids[0]])
        if plan is not None:
            assert ids[0] in plan[1].delve
            raise ReservedResourceContractFailure('Delve consumed an externally reserved card')


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_mana_counts_escape_fuel_but_not_source_after_announcement(seat):
    state = position(seat)
    crypt = add(state, 'Crypt of Agadeem', seat)
    spell = add(state, 'Woe Strider', seat, Zone.GRAVEYARD)
    for name in ('Skirge Familiar', 'Bog Witch', 'Island', 'Island'):
        add(state, name, seat, Zone.GRAVEYARD)
    spec = next(spec for spec in mana_ability_specs(crypt, state) if '{2}' in spec[1])
    with unchanged_root(state):
        assert ability_outputs(state, crypt, spec) == {'B': 3}
    announced = deepcopy(state)
    announced.players[seat].graveyard.remove(spell.id)
    announced.cards[spell.id].move_to_zone(Zone.STACK)
    with unchanged_root(announced):
        assert ability_outputs(announced, announced.cards[crypt.id], spec) == {'B': 2}
    # This is a timing-view boundary, not proof that an auto-cast is illegal:
    # the actor could legally activate Crypt before announcing the spell.


@pytest.mark.parametrize('seat', [1, 2])
def test_targeted_deathrite_instruction_is_not_an_automatic_mana_ability(seat):
    state = position(seat)
    source = add(state, 'Deathrite Shaman', seat)
    with unchanged_root(state):
        assert not mana_ability_specs(source, state)
