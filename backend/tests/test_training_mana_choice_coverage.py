"""Immediate mana boundary qualification, not engine/schema payment expansion."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.mana import auto_pay_cost
from training.environment import _unsupported_mana_choices, encode_action, decode_action
from tests.test_training_environment import resolve
from tests.test_training_choice_coverage import (
    position, replay, card as existing_card, forbid_database_and_network,
)


FILES = ('mana_abilities.json', 'additive_mana.json', 'affinity/permanents.json',
         'joint_activation_payment/phyrexian-tower.json', 'land_types.json')


def card(environment, name, seat):
    fixtures = Path(__file__).parent / 'fixtures'
    for filename in FILES:
        raw = json.loads((fixtures / filename).read_text())
        rows = raw if isinstance(raw, list) else raw.get('data', [raw])
        found = next((row for row in rows if row.get('name') == name), None)
        if found is not None:
            break
    else:
        raise AssertionError('Missing canonical mana fixture: ' + name)
    sample = MatchFactory.from_decks([{**found, 'card_name': name, 'quantity': 1}], [], seed=17)
    instance = deepcopy(next(iter(sample.cards.values())))
    state = environment._state
    instance.id = state.allocate_object_id()
    instance.owner = instance.controller = seat
    instance.move_to_zone(Zone.BATTLEFIELD)
    instance.summoning_sick = False  # Trusted matured retained position, not Oracle editing.
    state.cards[instance.id] = instance
    state.players[seat].battlefield.append(instance.id)
    assign_static_order_on_battlefield_entry(state, instance.id)
    for field in ('name', 'oracle_text', 'mana_cost', 'type_line'):
        assert getattr(instance, field) == found[field]
    return instance.id


def mana(cid, color, index=0):
    return {'type': 'activate_mana_ability', 'card_id': cid, 'ability_index': index, 'color': color}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color,amount', [('Sol Ring', 'C', 2), ('Llanowar Elves', 'G', 1),
                                           ('Basal Thrull', 'B', 2)])
def test_actual_immediate_fixed_and_self_sacrifice_mana_replay(seat, name, color, amount):
    environment = position(seat)
    cid = card(environment, name, seat)
    environment._state.players[seat].mana_pool = {}
    prompt = next(p for p in environment.prompts()
                  if p['hint']['type'] == 'activate_mana_ability' and p['hint']['card_id'] == cid)
    assert prompt['encoding_supported'] and not prompt['unsupported_choices']
    replay(environment, mana(cid, color), mana(cid, 'U'))
    assert environment._state.players[seat].mana_pool[color] == amount
    assert not environment._state.stack  # Not a generic delayed add_mana effect.
    if name == 'Basal Thrull':
        assert cid in environment._state.players[seat].graveyard
    else:
        assert environment._state.cards[cid].tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,index,payment', [('Cabal Coffers', 0, 2), ('Cabal Stronghold', 1, 3)])
def test_actual_paid_counted_land_ability_index_and_color_are_explicit(seat, name, index, payment):
    environment = position(seat)
    cid = card(environment, name, seat)
    for _ in range(3):
        card(environment, 'Swamp', seat)
    environment._state.players[seat].mana_pool = {'C': payment}
    action = mana(cid, 'B', index)
    replay(environment, action, {**action, 'ability_index': 99})
    assert environment._state.players[seat].mana_pool['B'] == 3
    assert environment._state.players[seat].mana_pool['C'] == 0
    assert not environment._state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('color', ['W', 'G'])
def test_chromatic_star_explicit_color_cost_departure_trigger_and_pending_draw_restore(seat, color):
    environment = position(seat)
    cid = card(environment, 'Chromatic Star', seat)
    existing_card(environment, 'Stinkweed Imp', seat, Zone.GRAVEYARD)
    environment._state.players[seat].mana_pool = {'C': 1}
    action = mana(cid, color)
    replay(environment, action, {key: value for key, value in action.items() if key != 'color'})
    assert cid in environment._state.players[seat].graveyard
    assert environment._state.players[seat].mana_pool[color] == 1
    assert len(environment._state.stack) == 1
    assert environment._state.stack[-1].effect_key == 'draw_cards'
    resolve(environment)
    assert environment._state.pending_mechanic_choice['kind'] == 'draw'
    assert 'prompts' not in environment.observe(3-seat)['pending_choice']
    replay(environment, {'type': 'choose_mechanic', 'choice_id': 'draw'},
           {'type': 'choose_mechanic', 'card_ids': []})
    assert not environment._state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_phyrexian_tower_requires_selected_resource_and_cannot_be_filtered_away(seat):
    environment = position(seat)
    cid = card(environment, 'Phyrexian Tower', seat)
    first = existing_card(environment, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    existing_card(environment, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    prompt = next(p for p in environment.prompts() if p['hint']['type'] == 'activate_mana_ability'
                  and p['hint']['card_id'] == cid and p['hint']['ability_index'] == 1)
    assert prompt['encoding_supported'] and not prompt['unsupported_choices']
    assert 'payment_choices.sacrifice_card_ids' in prompt['required_choices']
    action = mana(cid, 'B', 1)
    assert decode_action(encode_action(action)) == action  # Encoding alone is not legality.
    before = environment.snapshot()
    # Public actions must choose resources; internal payment planning may choose fuel.
    legacy = {'type': 'tap_nonland_for_mana', 'card_id': cid, 'color': 'B'}
    with pytest.raises(ActionRejected):
        checked_action(environment._state, environment._rules, seat, legacy)
    automatic = deepcopy(environment._state)
    automatic.players[seat].mana_pool = {}
    assert auto_pay_cost(automatic, seat, '{B}{B}')
    assert len(automatic.players[seat].battlefield) == len(environment._state.players[seat].battlefield) - 1
    assert environment.snapshot() == before
    selected = {**action, 'payment_choices': {'sacrifice_card_ids': [first]}}
    assert environment.lookup_intent(selected)
    proposals = [action, {**action, 'payment_choices': {'sacrifice_card_ids': []}},
                 {'type': 'tap_nonland_for_mana', 'card_id': cid, 'color': 'B'},
                 {'type': 'activate_ability', 'card_id': cid, 'ability_index': 1,
                  'payment_choices': {'sacrifice_card_ids': [first]}}]
    assert environment.action_mask(proposals) == [False] * len(proposals)
    for proposal in proposals:
        with pytest.raises(ActionRejected):
            environment.lookup_intent(proposal)
    assert environment.snapshot() == before
    # The representable intrinsic C ability is not blocked by a different ability's debt.
    replay(environment, mana(cid, 'C', 0))
    assert first in environment._state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_source_bound_payment_cannot_be_redirected_through_generic_stack_route(seat):
    environment = position(seat)
    cid = card(environment, 'Basal Thrull', seat)
    before = environment.snapshot()
    with pytest.raises(ActionRejected, match='current engine hints|generic stack route'):
        environment.lookup({'type': 'activate_ability', 'card_id': cid, 'ability_index': 0})
    assert environment.snapshot() == before
    assert environment.lookup(mana(cid, 'B'))


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_land_type_grant_requires_index_instead_of_legacy_automatic_ability_selection(seat):
    environment = position(seat)
    cid = card(environment, 'Cabal Stronghold', seat)
    card(environment, 'Urborg, Tomb of Yawgmoth', seat)
    card(environment, 'Swamp', seat)
    environment._state.players[seat].mana_pool = {'C': 3}
    hints = [p['hint'] for p in environment.prompts() if p['hint']['type'] == 'activate_mana_ability'
             and p['hint']['card_id'] == cid and 'B' in p['hint']['outputs']]
    assert len(hints) >= 2  # Printed paid B and granted tap-only B.
    before = environment.snapshot()
    with pytest.raises(ActionRejected, match='ability_index'):
        environment.lookup({'type': 'tap_nonland_for_mana', 'card_id': cid, 'color': 'B'})
    assert environment.snapshot() == before
    granted = next(h for h in hints if h['cost_text'] == '{T}')
    replay(environment, mana(cid, 'B', granted['ability_index']))
    assert environment._state.players[seat].mana_pool == {'C': 3, 'B': 1}


@pytest.mark.parametrize('cost,missing', [
    ('{R/G}, {T}', ['hybrid_choices']),
    ('{X}, {T}', ['targets.x_value']),
    ('{T}, Discard a card', ['payment_choices.discard_card_ids']),
    ('{T}, Sacrifice a creature', ['payment_choices.sacrifice_card_ids']),
    ('{1}, {T}, Sacrifice this artifact', []),
])
def test_cost_grammar_capability_probe_does_not_invent_a_game_card(cost, missing):
    assert _unsupported_mana_choices(cost) == missing


@pytest.mark.parametrize('seat', [1, 2])
def test_mana_prompts_and_masks_are_actor_private_and_ignore_opposing_hidden_identity(seat):
    environment = position(seat)
    cid = card(environment, 'Chromatic Star', seat)
    observed, prompts = environment.observe(seat), environment.prompts(seat)
    before = environment.snapshot()
    environment.lookup(mana(cid, 'W'))
    environment.action_mask([mana(cid, 'W'), mana(cid, 'U', 99)])
    assert environment.snapshot() == before
    state = environment._state
    for ids in (state.players[3-seat].hand, state.players[1].library, state.players[2].library):
        a, b = ids[:2]
        one, two = deepcopy(state.cards[a]), deepcopy(state.cards[b])
        one.id, two.id = b, a
        state.cards[a], state.cards[b] = two, one
        ids.reverse()
    state.starting_decks[3-seat] = deepcopy(state.starting_decks[seat])
    state.rng.random(); state.log.append('PRIVATE future opponent identity')
    assert environment.observe(seat) == observed and environment.prompts(seat) == prompts
    assert environment.prompts(3-seat) == []


@pytest.mark.parametrize('field,value', [('payment_choices', {'discard_card_ids': ['missing']}),
                                      ('hybrid_choices', ['R']), ('targets', {'x_value': 2})])
def test_shared_helper_cannot_silently_drop_requested_mana_parameters(field, value):
    environment = position()
    cid = card(environment, 'Sol Ring', 1)
    before = environment.snapshot()
    with pytest.raises(ActionRejected):
        environment.lookup_intent({**mana(cid, 'C'), field: value})
    assert environment.snapshot() == before
    assert environment.lookup_intent({**mana(cid, 'C'), 'card_name': 'Sol Ring'})


@pytest.mark.parametrize('seat', [1, 2])
def test_chosen_mana_source_aliases_roundtrip_without_exporting_private_action_mapping(seat):
    from training.dataset import EpisodeAliases
    environment = position(seat)
    cid = card(environment, 'Chromatic Star', seat)
    aliases = EpisodeAliases()
    aliases.observation(environment.observe(seat))
    action = mana(cid, 'W')
    mapped = aliases.action(action, seat)
    assert mapped['card_id'].startswith('card:') and mapped['card_id'] != cid
    assert aliases.actual_action(mapped, seat) == action
    assert environment.lookup(action)['action'] == action
