"""Typed cost units and full public canonical paid Oven/Familiar episodes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import (
    CardInstance, MatchFactory, MatchState, PlayerState, Step, Zone,
    assign_static_order_on_battlefield_entry, object_incarnation,
)
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import (
    CostOption, activated_cost_available, activated_cost_candidates,
    additional_cost_candidates, apply_activated_costs, parse_activated_cost,
)
from rules_engine.engine import RulesEngine
from rules_engine.move_generator import legal_moves
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.spell_cost_clauses import fixed_cost_component, spell_additional_costs


SEED = Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json'
RAW = SEED.read_bytes()
assert hashlib.sha256(RAW).hexdigest() == '9296ec1b24654374aaca985b92dc4c3b62a93e6fd024afcd6b4acd61a6007037'
ROWS = json.loads(RAW)['cards']
PINS = {
    'Cauldron Familiar': '7015a6475b9007046e1942f8d627e7bb4b353ae627799ed98e582848902e4cba',
    "Witch's Oven": '941928318afadf06019ac88e58d8a767003641f88efcb78a6660538841500cd2',
}
for name, digest in PINS.items():
    assert hashlib.sha256(json.dumps(ROWS[name], sort_keys=True, separators=(',', ':')).encode()).hexdigest() == digest


def facts(state):
    fields = deepcopy(vars(state))
    fields.pop('rng')
    return fields, serialize_match_snapshot(state), state.rng.getstate(), random.getstate()


def act(state, seat, action):
    before = facts(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert facts(state) == before
    return result


def resolve(state):
    for _ in range(12):
        if not state.stack:
            assert not state.pending_mechanic_choice and not state.pending_trigger_order
            return state
        assert not state.pending_mechanic_choice and not state.pending_replacement_choice
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Native stack did not drain within twelve actual priority passes')


def board(seat, victim_counters=0):
    # Only ordinary initial zones/counters/mana are seeded; no stack/token/choice.
    names = ["Witch's Oven", 'Elvish Mystic', 'Cauldron Familiar']
    deck = [dict(deepcopy(ROWS[name]), card_name=ROWS[name]['name'], quantity=1) for name in names]
    deck.append(dict(deepcopy(ROWS['Forest']), card_name='Forest', quantity=20))
    state = MatchFactory.from_decks(deck, deck, seed=512)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        player.hand.clear()
        player.library.clear()
    for cid, card in state.cards.items():
        card.move_to_zone(Zone.LIBRARY)
        state.players[card.owner].library.append(cid)
    ids = {}
    for alias, name, zone in [('oven', names[0], Zone.HAND), ('victim', names[1], Zone.BATTLEFIELD),
                              ('cat', names[2], Zone.GRAVEYARD)]:
        card = next(c for c in state.cards.values() if c.owner == seat and c.name == name)
        assert card.oracle_text == ROWS[name]['oracle_text']
        assert card.card_faces == list(ROWS[name].get('card_faces') or [])
        state.players[seat].library.remove(card.id)
        card.move_to_zone(zone)
        getattr(state.players[seat], zone.value).append(card.id)
        if zone == Zone.BATTLEFIELD:
            card.summoning_sick = False
            assign_static_order_on_battlefield_entry(state, card.id)
            card.counters['+1/+1'] = victim_counters
        ids[alias] = card.id
    return state, ids


def paid_food(seat, victim_counters=0):
    state, ids = board(seat, victim_counters)
    state.players[seat].mana_pool['C'] = 1
    state = act(state, seat, {'type': 'cast_spell', 'card_id': ids['oven'], 'targets': {}})
    assert len(state.stack) == 1 and not any(state.players[seat].mana_pool.values())
    state = resolve(state)
    assert state.cards[ids['oven']].zone == Zone.BATTLEFIELD
    before_ids = set(state.cards)
    state = act(state, seat, {'type': 'activate_ability', 'card_id': ids['oven'], 'ability_index': 0,
                             'targets': {}, 'payment_choices': {'sacrifice_card_ids': [ids['victim']]}})
    assert state.cards[ids['oven']].tapped
    assert state.cards[ids['victim']].zone == Zone.GRAVEYARD
    assert state.cards[ids['victim']].last_known_battlefield['toughness'] == 1 + victim_counters
    state = resolve(state)
    foods = sorted(set(state.cards) - before_ids)
    assert len(foods) == (2 if victim_counters >= 3 else 1)
    assert all(state.cards[cid].is_token and state.cards[cid].zone == Zone.BATTLEFIELD
               and 'Artifact' in state.cards[cid].types
               and state.cards[cid].type_line == 'Token Artifact \u2014 Food' for cid in foods)
    return state, ids, foods


def familiar_request(ids, selected):
    return {'type': 'activate_ability', 'card_id': ids['cat'], 'ability_index': 0,
            'targets': {}, 'payment_choices': {'sacrifice_card_ids': selected}}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('victim_counters', [0, 3])
def test_full_canonical_paid_oven_generated_food_returns_familiar_once(seat, victim_counters):
    state, ids, foods = paid_food(seat, victim_counters)
    before = facts(state)
    ability = extract_activated_abilities(state.cards[ids['cat']])[0]
    assert ability['index'] == 0 and ability['activation_zone'] == 'graveyard'
    assert ability['mana_cost'] == 'SACRIFICE A FOOD'
    offered = [m for m in legal_moves(state, seat) if m['type'] == 'activate_ability'
               and m.get('card_id') == ids['cat']]
    assert len(offered) == 1
    assert set(offered[0]['payment_options']['sacrifice_card_ids']) == set(foods)
    assert facts(state) == before
    source = state.cards[ids['cat']]
    ref = {'incarnation': object_incarnation(source), 'zone_change_sequence': source.zone_change_sequence}
    selected = foods[-1]
    paid = act(state, seat, familiar_request(ids, [selected]))
    assert paid.cards[selected].zone == Zone.CEASED and selected not in paid.players[seat].battlefield
    assert paid.cards[ids['cat']].zone == Zone.GRAVEYARD
    assert len(paid.stack) == 1
    item = paid.stack[-1]
    assert item.source_card_id == ids['cat'] and item.controller == seat
    assert item.payload['__activation_source_reference'] == ref
    assert item.payload['__graveyard_reference'] == ref
    assert item.payload['__activation_source_origin'] == 'graveyard'
    returned = resolve(paid)
    assert returned.cards[ids['cat']].zone == Zone.BATTLEFIELD
    assert returned.players[seat].battlefield.count(ids['cat']) == 1
    assert ids['cat'] not in returned.players[seat].graveyard
    assert returned.players[seat].life == 21 and returned.players[3-seat].life == 19
    assert set(foods) - {selected} <= set(returned.players[seat].battlefield)
    assert returned.cards[ids['cat']].oracle_text == ROWS['Cauldron Familiar']['oracle_text']
    assert facts(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_full_canonical_paid_familiar_cast_resolves_complete_self_entry_drain(seat):
    state, ids = board(seat)
    source = state.cards[ids['cat']]
    state.players[seat].graveyard.remove(source.id)
    source.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(source.id)
    state.players[seat].mana_pool['B'] = 1
    before = facts(state)
    paid = act(state, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    assert len(paid.stack) == 1 and not any(paid.players[seat].mana_pool.values())
    returned = resolve(paid)
    assert returned.cards[source.id].zone == Zone.BATTLEFIELD
    assert returned.cards[source.id].oracle_text == ROWS['Cauldron Familiar']['oracle_text']
    assert returned.players[seat].life == 21 and returned.players[3-seat].life == 19
    assert facts(state) == before


def entry_unit(state, ids, text, entering):
    from rules_engine.events import _trigger_from_oracle
    source = state.cards[ids['cat']]
    before = facts(state)
    result = _trigger_from_oracle(state, source.id, source.controller, text,
                                 'Public entry unit', 'enters_battlefield', {'card_id': entering})
    assert facts(state) == before
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('lose,gain,amounts', [('one', 'two', (1, 2)), ('2', 'three', (2, 3)), ('ten', 'a', (10, 1))])
def test_closed_self_entry_count_units_publish_both_explicit_controller_relative_effects(seat, lose, gain, amounts):
    # Adversarial grammar units only; runtime episodes above use unreduced rows.
    state, ids = board(seat)
    source = state.cards[ids['cat']]
    source.controller = 3-seat
    text = f'When this creature enters, each opponent loses {lose} life and you gain {gain} life.'
    spec = entry_unit(state, ids, text, source.id)
    assert spec['source_card_id'] == source.id and spec['controller'] == 3-seat
    assert spec['effect_key'] == 'effect_sequence'
    assert spec['payload']['effects'] == [
        {'effect_key': 'lose_life', 'payload': {'target_player': seat, 'amount': amounts[0]}},
        {'effect_key': 'gain_life', 'payload': {'target_player': 3-seat, 'amount': amounts[1]}},
    ]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', [' Draw a card.', ' Then exile it.', ' if you control a Food.',
                                 ' instead.', ' except target opponent.'])
def test_closed_self_entry_drain_unknown_suffix_cannot_reward_partial_gain(seat, tail):
    state, ids = board(seat)
    text = ROWS['Cauldron Familiar']['oracle_text'].splitlines()[0] + tail
    spec = entry_unit(state, ids, text, ids['cat'])
    assert spec['effect_key'] == 'noop'
    assert spec['payload']['__unsupported_trigger_instruction'] == text


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('wrong', ['victim', None])
def test_closed_self_entry_drain_wrong_event_source_never_publishes_reward(seat, wrong):
    state, ids = board(seat)
    text = ROWS['Cauldron Familiar']['oracle_text'].splitlines()[0]
    assert entry_unit(state, ids, text, ids[wrong] if wrong else None) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', [' (Draw a card.)', ' Draw a card.'])
def test_full_raw_self_entry_negative_suffix_is_not_hidden_by_direct_normalization(seat, tail):
    state, ids = board(seat)
    lines = ROWS['Cauldron Familiar']['oracle_text'].splitlines()
    lines[0] += tail
    # Adversarial negative body; retain the full base and unrelated ability line.
    text = '\n'.join(lines)
    spec = entry_unit(state, ids, text, ids['cat'])
    assert spec['effect_key'] == 'noop'
    assert spec['payload']['__unsupported_trigger_instruction'] == lines[0]
    assert state.cards[ids['cat']].oracle_text == ROWS['Cauldron Familiar']['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', [' (Draw a card.)', ' Draw a card.'])
def test_full_raw_self_entry_negative_suffix_native_paid_cast_never_rewards_partial_body(seat, tail):
    state, ids = board(seat)
    source = state.cards[ids['cat']]
    lines = source.oracle_text.splitlines()
    lines[0] += tail
    # Negative grammar metadata only, not a new or reduced canonical Oracle row.
    source.oracle_text = '\n'.join(lines)
    state.players[seat].graveyard.remove(source.id)
    source.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(source.id)
    state.players[seat].mana_pool['B'] = 1
    before = facts(state)
    paid = act(state, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    assert len(paid.stack) == 1 and not any(paid.players[seat].mana_pool.values())
    for _ in range(2):
        paid = act(paid, paid.priority_player, {'type': 'pass_priority'})
    assert paid.cards[source.id].zone == Zone.BATTLEFIELD
    assert len(paid.stack) == 1
    trigger = paid.stack[-1]
    assert trigger.source_card_id == source.id and trigger.controller == seat
    assert trigger.effect_key == 'noop'
    assert trigger.payload['__unsupported_trigger_instruction'] == lines[0]
    returned = resolve(paid)
    assert returned.players[seat].life == returned.players[3-seat].life == 20
    assert returned.cards[source.id].oracle_text == '\n'.join(lines)
    assert facts(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['wrong_zone', 'wrong_type', 'duplicate', 'empty', 'wrong_seat', 'target'])
def test_real_food_activation_rejects_invalid_selection_without_root_changes(seat, invalid):
    state, ids, foods = paid_food(seat)
    cost = parse_activated_cost('Sacrifice a Food')
    assert cost.supported
    selected = {'wrong_zone': [ids['victim']], 'wrong_type': [ids['oven']],
                'duplicate': [foods[0], foods[0]], 'empty': []}.get(invalid, [foods[0]])
    request = familiar_request(ids, selected)
    if invalid == 'target':
        request['targets'] = {'target_card_id': ids['cat']}
    before = facts(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat if invalid == 'wrong_seat' else seat, request)
    assert facts(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_reserved_real_food_is_unpayable_before_any_native_mutation(seat):
    state, ids, foods = paid_food(seat)
    assert parse_activated_cost('Sacrifice a Food').supported
    before = facts(state)
    choice = {'sacrifice_card_ids': foods}
    assert not activated_cost_available(state, seat, ids['cat'], 'Sacrifice a Food',
        payment_choices=choice, unavailable_resources=set(foods))
    assert not apply_activated_costs(state, seat, ids['cat'], 'Sacrifice a Food',
        payment_choices=choice, unavailable_resources=set(foods))
    assert facts(state) == before


@pytest.mark.parametrize('text,count,kind', [
    ('Sacrifice a Food', 1, 'subtype_artifact_food'),
    ('Sacrifice two Foods', 2, 'subtype_artifact_food'),
    ('Sacrifice an Equipment', 1, 'subtype_artifact_equipment'),
    ('Sacrifice three Auras', 3, 'subtype_enchantment_aura'),
])
def test_closed_resource_cost_component_is_shared_by_fixed_and_spell_prices(text, count, kind):
    expected = {'sacrifice_creatures': count, 'sacrifice_kind': kind}
    assert fixed_cost_component(text) == expected
    assert spell_additional_costs('As an additional cost to cast this spell, ' + text.lower() + '.') == [expected]
    cost = parse_activated_cost(text)
    assert cost.supported and cost.sacrifice_creatures == count and cost.sacrifice_kind == kind


@pytest.mark.parametrize('text', ['Sacrifice a Seafood', 'Sacrifice a Food you do not control',
    'Sacrifice a Food and draw a card', 'Sacrifice a Food or a Goblin', 'Sacrifice a Food, Dance',
    'Sacrifice a Food, Sacrifice a Goblin', 'Sacrifice a Goblin, Sacrifice a Food'])
def test_unrecognized_or_incompatible_typed_resource_cost_stays_strict(text):
    assert not parse_activated_cost(text).supported


@pytest.mark.parametrize('seat', [1, 2])
def test_typed_resource_units_require_actual_type_subtype_zone_controller_and_reservations(seat):
    # Component-only controlled metadata, not invented card abilities/Oracle rows.
    state = MatchState('typed-resource-unit', {pid: PlayerState(pid, str(pid)) for pid in (1, 2)}, {}, [])
    specifications = [
        ('food', ['Artifact'], 'Artifact - Food', seat, Zone.BATTLEFIELD, []),
        ('food_creature', ['Artifact', 'Creature'], 'Artifact Creature - Food', seat, Zone.BATTLEFIELD, []),
        ('creature_food', ['Creature'], 'Creature - Food', seat, Zone.BATTLEFIELD, []),
        ('kindred_food', ['Kindred'], 'Kindred - Food', seat, Zone.BATTLEFIELD, []),
        ('changeling', ['Creature'], 'Creature - Shapeshifter', seat, Zone.BATTLEFIELD, ['changeling']),
        ('artifact_goblin', ['Artifact'], 'Artifact - Goblin', seat, Zone.BATTLEFIELD, []),
        ('kindred_goblin', ['Kindred', 'Enchantment'], 'Kindred Enchantment - Goblin', seat, Zone.BATTLEFIELD, []),
        ('named_food', ['Artifact'], 'Artifact - Treasure', seat, Zone.BATTLEFIELD, []),
        ('enemy', ['Artifact'], 'Artifact - Food', 3-seat, Zone.BATTLEFIELD, []),
        ('hand', ['Artifact'], 'Artifact - Food', seat, Zone.HAND, []),
    ]
    for cid, types, line, controller, zone, keywords in specifications:
        card = CardInstance(cid, 'Food', controller, controller, zone, types,
                            type_line=line, keywords=keywords, power=1, toughness=1)
        state.cards[cid] = card
        getattr(state.players[controller], zone.value).append(cid)
    before = facts(state)
    cost = parse_activated_cost('Sacrifice a Food')
    assert cost.supported
    assert set(activated_cost_candidates(state, seat, 'food', cost)['sacrifice_card_ids']) == {'food', 'food_creature'}
    assert activated_cost_candidates(state, seat, 'food', cost, {'food', 'food_creature'})['sacrifice_card_ids'] == []
    option = CostOption('base', 'Base', '', sacrifice_creatures=1, sacrifice_kind=cost.sacrifice_kind)
    assert set(additional_cost_candidates(state, seat, 'hand', option)['sacrifice_card_ids']) == {'food', 'food_creature'}
    goblin = parse_activated_cost('Sacrifice a Goblin')
    assert goblin.supported and goblin.sacrifice_kind == 'subtype_goblin'
    assert set(activated_cost_candidates(state, seat, 'food', goblin)['sacrifice_card_ids']) == {'changeling', 'kindred_goblin'}
    assert facts(state) == before
