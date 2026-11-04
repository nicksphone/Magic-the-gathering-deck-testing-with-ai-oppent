"""Canonical component controls; not gameplay or trained-model qualification.

Use the original strong precollection runner after the engine-green barrier.
No synthetic StackItem, guessed Oracle outcome, trained policy or SQL is used.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.type_effects import effective_types
from tests import test_ai_search_prefix as source_fixture
from tests.test_ai_attachment_explicit_choices import aura_position
from tests.test_ai_recurring_engines import add as add_printed
from tests.test_linked_damage_targets import raw_card


FIXTURES = Path(source_fixture.__file__).parent / 'fixtures'
PINS = {
    'knowledge_profiles/seed155-scryfall.jsonl': '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
    'aura_costs.json': 'c6861515e20337ec3c32763a6ca89332e0ed665aad54f8bb520261c4e5a9d17c',
    'land_types.json': 'a080fedcf0314f76c42102ba8b5d28312f08b119ef39c7f8b84f8e6de56e4597',
    'conditional_types.json': '866fed5d0275fd65765468893e791d5d7aa4fdd2b413ca5288f986f3def1e2b8',
    'pending_permanent_fullraw/canonical.jsonl': 'bbc868c335b6f5bc7e5a02f5aafe92bf16e25ede7652a0f2e7d5ae5428c5048a',
    'mana_two_p2_T57/wild-growth.raw.json': 'f719a52e0a85fe31979867341ee142e7762e4a319a7a27fec2ed4422f415f2b0',
    'favor_target_lifecycle/cloudshift.json': 'a6477d60b641d708f9447b8f53637a6701b02531fce76c6b04f9cb0fc6ded47b',
    'cloudshift_compound_audit/flicker-of-fate.json': 'a52175e1928539cac7243e6e2a7687c99ac23d320b89218472e07590a35cf29d',
    'graveyard_batch_native_bf62/eidolon-of-blossoms.json': '515e31839799a1e1893d4df5c821b7f2855e549bbe0f4c1eab9aaea7d2396b5f',
}
PRINTS = {}
for relative, expected in PINS.items():
    data = (FIXTURES / relative).read_bytes()
    assert sha256(data).hexdigest() == expected
    value = ([json.loads(line) for line in data.splitlines()]
             if relative.endswith('.jsonl') else json.loads(data))
    rows = value if isinstance(value, list) else [value]
    for row in rows:
        # Keep a full raw printing when multiple canonical sources overlap.
        if row['name'] not in PRINTS or row.get('object') == 'card':
            PRINTS[row['name']] = row


def add(state, name, seat, zone):
    row = PRINTS[name]
    card = (raw_card(state, row, seat, zone) if row.get('object') == 'card'
            else add_printed(state, name, seat, zone, cards=PRINTS))
    assert (card.name, card.mana_cost, card.oracle_text, card.type_line) == tuple(
        row[field] for field in ('name', 'mana_cost', 'oracle_text', 'type_line'))
    if zone == Zone.BATTLEFIELD:
        card.summoning_sick = False
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def pose(seat, *, enemy=False):
    state = source_fixture.bare_state(seat)
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    lands = [add(state, 'Plains', seat, Zone.BATTLEFIELD) for _ in range(4)]
    spell = add(state, 'Ossification', seat, Zone.HAND)
    other = add(state, 'Recruitment Officer', 3-seat, Zone.BATTLEFIELD) if enemy else None
    return state, spell, lands, other


def offered(state, seat, spell):
    return deepcopy(next(move for move in RulesEngine().legal_moves(state, seat)
                         if move.get('type') == 'cast_spell' and move.get('card_id') == spell.id))


def projection(state, seat, move):
    before, supplied = serialize_match_snapshot(state), deepcopy(move)
    global_rng, local_rng = random.getstate(), state.rng.getstate()
    result = AIAgent('master', 'Control')._attachment_projection(state, move, seat)
    assert serialize_match_snapshot(state) == before and move == supplied
    assert random.getstate() == global_rng and state.rng.getstate() == local_rng
    return result


def settled_cast(state, seat, action, *, entry_target=None):
    """Resolve only the genuine cast and a supplied public ETB target."""
    rules = RulesEngine()
    state = checked_action(state, rules, seat, deepcopy(action))
    for _ in range(32):
        assert not state.pending_mechanic_choice and not state.pending_replacement_choice
        if state.pending_trigger_order:
            assert entry_target is not None, 'Unresolved choice is not a guessed continuation'
            choices = [move for move in rules.legal_moves(state, seat)
                       if move.get('type') == 'choose_trigger_target'
                       and move.get('target_card_id') == entry_target]
            assert len(choices) == 1
            state = checked_action(state, rules, seat, deepcopy(choices[0]))
        elif not state.stack:
            return state
        else:
            state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Bounded canonical settlement exhausted; no forced continuation')


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_entry_only_aura_has_no_ai_candidate_but_remains_human_legal(seat):
    state, spell, lands, _ = pose(seat)
    move = offered(state, seat, spell)
    assert not state.stack
    assert not any({'Creature', 'Planeswalker'} & set(effective_types(state, state.cards[cid]))
                   for cid in state.players[3-seat].battlefield)
    action, gain = projection(state, seat, move)
    assert action is None and gain == 0.0  # Intended behavioral RED, not an intrinsic-score tweak.
    native = settled_cast(state, seat, {'type': 'cast_spell', 'card_id': spell.id,
                                       'targets': {'target_card_id': lands[0].id}})
    assert native.cards[spell.id].zone == Zone.BATTLEFIELD
    assert native.cards[spell.id].attached_to == lands[0].id
    assert not native.linked_exiles


@pytest.mark.parametrize('seat', [1, 2])
def test_productive_linked_aura_preserves_explicit_land_cost_and_actual_enemy_exile(seat):
    state, spell, lands, enemy = pose(seat, enemy=True)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    move = {**offered(state, seat, spell), 'cost_choice': {'id': 'base'},
            'targets': {'target_card_id': lands[1].id}}
    action, gain = projection(state, seat, move)
    assert action is not None and gain > 0
    assert action['targets'] == move['targets'] and action['cost_choice'] == move['cost_choice']
    native = settled_cast(state, seat, action, entry_target=enemy.id)
    assert native.cards[enemy.id].zone == Zone.EXILE
    assert any(link['source_id'] == spell.id and enemy.id in link['card_ids']
               for link in native.linked_exiles)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Spirit Mantle', 'Curiosity', 'Wild Growth', 'Lush Growth'])
def test_other_canonical_aura_effects_are_not_the_empty_entry_class(seat, name):
    state = source_fixture.bare_state(seat)
    state.players[seat].mana_pool = {color: 4 for color in 'WUBRGC'}
    host = add(state, 'Recruitment Officer' if name in {'Spirit Mantle', 'Curiosity'}
               else 'Island', seat, Zone.BATTLEFIELD)
    spell = add(state, name, seat, Zone.HAND)
    move = {**offered(state, seat, spell), 'targets': {'target_card_id': host.id}}
    action, gain = projection(state, seat, move)
    assert action is not None and gain > 0
    assert action['targets']['target_card_id'] == host.id
    native = settled_cast(state, seat, action)
    assert native.cards[spell.id].attached_to == host.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('branch', ['G', 'U'])
def test_favor_explicit_hybrid_and_host_are_not_repriced_or_rewritten(seat, branch):
    state, _, move, _, hosts = aura_position(seat, second_host=True)
    supplied = {**move, 'cost_choice': {'id': 'base'}, 'hybrid_choices': [branch],
                'targets': {'target_card_id': hosts[0].id}}
    action, gain = projection(state, seat, supplied)
    assert action is not None and gain > 0
    for key in ('cost_choice', 'hybrid_choices', 'targets'):
        assert action[key] == supplied[key]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('context', ['prowess', 'enchantment_entry', 'devotion',
                                   'hand_devotion', 'hand_blink', 'hand_enchantment_scaling'])
def test_public_or_own_hand_payoff_context_abstains_from_the_empty_entry_veto(seat, context):
    state, spell, _, _ = pose(seat)
    name, zone = {
        'prowess': ('Monastery Swiftspear', Zone.BATTLEFIELD),
        'enchantment_entry': ('Eidolon of Blossoms', Zone.BATTLEFIELD),
        'devotion': ('Heliod, God of the Sun', Zone.BATTLEFIELD),
        'hand_devotion': ('Heliod, God of the Sun', Zone.HAND),
        'hand_blink': ('Flicker of Fate', Zone.HAND),
        'hand_enchantment_scaling': ('All That Glitters', Zone.HAND),
    }[context]
    context_card = add(state, name, seat, zone)
    if context == 'hand_blink':
        from rules_engine.oracle_effects import inspect_target_hints
        from rules_engine.targeting import validate_cast_targets
        land = state.players[seat].battlefield[0]
        paid = settled_cast(state, seat, {'type': 'cast_spell', 'card_id': spell.id,
                                         'targets': {'target_card_id': land}})
        hints = inspect_target_hints(paid, paid.cards[context_card.id], seat)
        assert validate_cast_targets(hints, {'target_card_id': spell.id})[0] is True
    action, gain = projection(state, seat, offered(state, seat, spell))
    # Preserve old valuation; this does not certify a future payoff or winning line.
    assert action is not None and gain > 0


@pytest.mark.parametrize('seat', [1, 2])
def test_resourceful_enchanted_land_is_not_assumed_to_be_a_plain_funding_land(seat):
    state, spell, lands, _ = pose(seat)
    growth = add(state, 'Wild Growth', seat, Zone.HAND)
    state.players[seat].mana_pool['G'] = 1
    state = settled_cast(state, seat, {'type': 'cast_spell', 'card_id': growth.id,
                                      'targets': {'target_card_id': lands[0].id}})
    assert state.cards[growth.id].attached_to == lands[0].id
    move = {**offered(state, seat, spell), 'targets': {'target_card_id': lands[0].id}}
    action, gain = projection(state, seat, move)
    assert action is not None and gain > 0


@pytest.mark.parametrize('seat', [1, 2])
def test_synthetic_unknown_extra_surface_is_abstention_not_a_shortened_real_print(seat):
    state, spell, _, _ = pose(seat)
    # Explicit SYNTHETIC protocol, never presented as canonical Oracle or native proof.
    spell.oracle_text += '\nUnrecognized additional public instruction.'
    action, gain = projection(state, seat, offered(state, seat, spell))
    assert action is not None and gain > 0


@pytest.mark.parametrize('seat', [1, 2])
def test_private_order_permutations_do_not_change_empty_entry_decision(seat):
    state, spell, _, _ = pose(seat)
    add(state, 'Recruitment Officer', 3-seat, Zone.HAND)
    add(state, 'Forest', 3-seat, Zone.HAND)
    move = offered(state, seat, spell)
    view, moves = decision_view(state, seat, [move])
    original = projection(view, seat, moves[0])
    hidden = deepcopy(state)
    hidden.players[3-seat].hand.reverse()
    for player in hidden.players.values():
        player.library.reverse()
    other_view, other_moves = decision_view(hidden, seat, [move])
    assert projection(other_view, seat, other_moves[0]) == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('location', ['held', 'two_held', 'empty_battlefield'])
def test_other_self_only_dead_auras_are_not_cross_card_payoffs(seat, location):
    state, spell, lands, _ = pose(seat)
    other = add(state, 'Ossification', seat, Zone.HAND)
    if location == 'two_held':
        add(state, 'Ossification', seat, Zone.HAND)
    elif location == 'empty_battlefield':
        state = settled_cast(state, seat, {'type': 'cast_spell', 'card_id': other.id,
                                          'targets': {'target_card_id': lands[0].id}})
        assert state.cards[other.id].zone == Zone.BATTLEFIELD and not state.linked_exiles
    action, gain = projection(state, seat, offered(state, seat, spell))
    assert action is None and gain == 0.0


@pytest.mark.parametrize('seat', [1, 2])
def test_creature_only_cloudshift_cannot_blink_an_enchantment_aura(seat):
    from rules_engine.oracle_effects import inspect_target_hints
    from rules_engine.targeting import validate_cast_targets
    state, spell, lands, _ = pose(seat)
    blink = add(state, 'Cloudshift', seat, Zone.HAND)
    paid = settled_cast(state, seat, {'type': 'cast_spell', 'card_id': spell.id,
                                     'targets': {'target_card_id': lands[0].id}})
    hints = inspect_target_hints(paid, paid.cards[blink.id], seat)
    assert validate_cast_targets(hints, {'target_card_id': spell.id})[0] is False
    action, gain = projection(state, seat, offered(state, seat, spell))
    assert action is None and gain == 0.0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('delta', ['none', 'life', 'mana_gain', 'host_counter', 'aura_counter',
                                  'library_count', 'pending', 'terminal'])
def test_synthetic_public_delta_certificate_is_not_a_native_outcome_claim(seat, delta):
    state, spell, lands, _ = pose(seat)
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'targets': {'target_card_id': lands[0].id}, 'cost_choice': {'id': 'base'}}
    after = settled_cast(state, seat, action)
    assert after.cards[spell.id].counters == {'__attached_to': 0}
    # Deliberate SYNTHETIC comparison-operand mutations, never engine outcomes.
    if delta == 'life':
        after.players[seat].life += 1
    elif delta == 'mana_gain':
        after.players[seat].mana_pool['C'] += 1
    elif delta == 'host_counter':
        after.cards[lands[0].id].counters['+1/+1'] = 1
    elif delta == 'aura_counter':
        after.cards[spell.id].counters['shield'] = 1
    elif delta == 'library_count':
        cid = after.players[seat].library.pop()
        after.cards[cid].move_to_zone(Zone.EXILE)
        after.players[seat].exile.append(cid)
    elif delta == 'pending':
        after.staged_triggers.append({})
    elif delta == 'terminal':
        after.winner = seat
    before, trial = serialize_match_snapshot(state), serialize_match_snapshot(after)
    rng, local = random.getstate(), state.rng.getstate()
    result = AIAgent('master', 'Control')._empty_entry_only_removal_aura(state, after, action, seat)
    assert result is (delta == 'none')
    assert serialize_match_snapshot(state) == before and serialize_match_snapshot(after) == trial
    assert random.getstate() == rng and state.rng.getstate() == local


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('held_attack_trigger', [False, True])
def test_held_attack_trigger_is_not_a_cast_or_entry_payoff(seat, held_attack_trigger):
    state, spell, lands, _ = pose(seat)
    # Public canonical construction, not a copy of a private replay snapshot.
    for land in lands[2:]:
        state.players[seat].battlefield.remove(land.id)
        land.move_to_zone(Zone.LIBRARY)
        state.players[seat].library.append(land.id)
    add(state, 'Recruitment Officer', seat, Zone.BATTLEFIELD)
    add(state, 'Lay Down Arms', seat, Zone.HAND)
    add(state, 'Lay Down Arms', seat, Zone.HAND)
    add(state, 'Plains', seat, Zone.HAND)
    if held_attack_trigger:
        held = add(state, 'Adeline, Resplendent Cathar', seat, Zone.HAND)
        assert 'Whenever you attack' in held.oracle_text and held.zone == Zone.HAND
    action, gain = projection(state, seat, offered(state, seat, spell))
    assert action is None and gain == 0.0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('held', [True, False])
def test_canonical_prowess_zone_distinguishes_held_card_from_live_trigger(seat, held):
    from rules_engine.continuous import effective_combat_stats
    state, spell, _, _ = pose(seat)
    creature = add(state, 'Monastery Swiftspear', seat,
                   Zone.HAND if held else Zone.BATTLEFIELD)
    assert 'Prowess' in creature.oracle_text and creature.oracle_text == PRINTS[creature.name]['oracle_text']
    action, gain = projection(state, seat, offered(state, seat, spell))
    if held:
        assert action is None and gain == 0.0
    else:
        assert action is not None and gain > 0
        native = settled_cast(state, seat, action)
        assert effective_combat_stats(native, creature.id)[0] > effective_combat_stats(state, creature.id)[0]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keyword', ['Storm', 'Affinity for enchantments', 'Prowess', 'Extort', 'Cascade'])
def test_synthetic_hand_keyword_protocol_distinguishes_trigger_zone_from_count(seat, keyword):
    state, spell, lands, _ = pose(seat)
    held = add(state, 'Recruitment Officer', seat, Zone.HAND)
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'targets': {'target_card_id': lands[0].id}, 'cost_choice': {'id': 'base'}}
    after = settled_cast(state, seat, action)
    # SYNTHETIC keyword-intake protocol, not a canonical printing or payoff proof.
    # No existing full canonical storm fixture is claimed by this control.
    state.cards[held.id].keywords = [keyword]
    after.cards[held.id].keywords = [keyword]
    before, trial = serialize_match_snapshot(state), serialize_match_snapshot(after)
    expected = keyword in {'Prowess', 'Extort', 'Cascade'}
    assert AIAgent('master', 'Control')._empty_entry_only_removal_aura(state, after, action, seat) is expected
    assert serialize_match_snapshot(state) == before and serialize_match_snapshot(after) == trial
