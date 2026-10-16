"""Canonical qualified prevention; explicit primitive and native-frame boundaries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from effects.handlers import deal_damage, destroy_permanent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.combat import _deal_unblocked_damage
from rules_engine.damage_results import damage_source_control
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine import replacement
from rules_engine.prevention import validate_legacy_damage_boundary
from rules_engine.stack_engine import resolve_top_of_stack
from tests.damage_life_printed_79 import (
    PRINTED_FIELDS, canonical_base_state, canonical_card, raw_card,
)
from tests.rules_printed_facts_e4 import canonical_card as rules_card


HEKMA = 'Protection of the Hekma'
RULES = RulesEngine()


def snapshot(state):
    return serialize_match_snapshot(state)


def reload(state):
    before = snapshot(state)
    result = deserialize_match_snapshot(json.loads(json.dumps(before)))
    assert snapshot(result) == before
    return result


def act(state, actor, action):
    before = snapshot(state)
    result = checked_action(state, RULES, actor, action)
    assert snapshot(state) == before
    return result


def add(state, name, controller, zone=Zone.BATTLEFIELD, *, owner=None, cid=None):
    factory = rules_card if name in {'Twincast', 'Counterspell'} else canonical_card
    card = factory(name, id=cid or state.allocate_object_id(),
        owner=controller if owner is None else owner, controller=controller, zone=zone)
    state.cards[card.id] = card
    getattr(state.players[controller], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        card.summoning_sick = False
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def position(defender):
    state = canonical_base_state()
    for player in state.players.values():
        player.mana_pool = {color: 20 for color in 'WUBRGC'}
    wards = [add(state, HEKMA, defender, cid=f'hekma-{index}') for index in (1, 2)]
    return state, wards


def assert_printed_wards(state, wards):
    raw = raw_card(HEKMA)
    assert 'a source an opponent controls' in raw['oracle_text']
    for cid in wards:
        card = state.cards[cid]
        expected = canonical_card(HEKMA, id=cid, owner=card.owner,
                                  controller=card.controller, zone=card.zone)
        assert {key: getattr(card, key) for key in PRINTED_FIELDS} == {
            key: getattr(expected, key) for key in PRINTED_FIELDS}
        assert card.id == cid and card.zone == Zone.BATTLEFIELD


def observe_candidates(monkeypatch, state, wards, source):
    delegate = replacement._player_damage_candidates
    calls = []

    def observe(actual_state, *args, **kwargs):
        assert actual_state is state
        assert_printed_wards(actual_state, wards)
        assert kwargs.get('source_card_id') == source
        calls.append(deepcopy(kwargs))
        return delegate(actual_state, *args, **kwargs)

    monkeypatch.setattr(replacement, '_player_damage_candidates', observe)
    return calls


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opponent', [False, True])
@pytest.mark.parametrize('foreign_owner', [False, True])
@pytest.mark.parametrize('route', ['query', 'application', 'combat'])
def test_full_raw_before_helper_and_controller_not_owner_parity(
        monkeypatch, seat, opponent, foreign_owner, route):
    state, wards = position(seat)
    controller = 3-seat if opponent else seat
    name = 'Vampire Nighthawk' if route == 'combat' else 'Prodigal Pyromancer'
    source = add(state, name, controller, owner=3-controller if foreign_owner else controller)
    calls = observe_candidates(monkeypatch, state, wards, source)
    before, raw_before = snapshot(state), raw_card(HEKMA)
    if route == 'query':
        rows = replacement.replacement_options(state, 'damage_to_player', target_player=seat,
                                                source_card_id=source, amount=2)
        assert [row['source_id'] for row in rows] == (wards[::-1] if opponent else [])
        assert snapshot(state) == before
    else:
        amount = (_deal_unblocked_damage(state, f'player:{seat}', 2, source)
                  if route == 'combat' else deal_damage(state, controller, {
                      'target_player': seat, 'amount': 2, '__source_card_id': source}))
        assert amount == (0 if opponent else 2)
        assert state.players[seat].life == 20-amount
    assert calls and raw_card(HEKMA) == raw_before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('returned', [False, True])
def test_retained_departed_activation_control_wins_over_new_incarnation(seat, returned):
    state, wards = position(seat)
    actor = 3-seat
    state.active_player = state.priority_player = actor
    source = add(state, 'Prodigal Pyromancer', actor)
    state = act(state, actor, {'type': 'activate_ability', 'card_id': source,
        'ability_index': 0, 'targets': {'target_player': seat}})
    destroy_permanent(state, seat, {'target_card_id': source})
    retained = deepcopy(state.stack[-1].payload['__source_lki'])
    assert retained['controller'] == actor
    if returned:
        card = state.cards[source]
        state.players[card.owner].graveyard.remove(source)
        state.players[seat].battlefield.append(source)
        card.move_to_zone(Zone.BATTLEFIELD)
        card.controller = seat
        assign_static_order_on_battlefield_entry(state, source)
    state = reload(state)
    before = snapshot(state)
    rows = replacement.replacement_options(state, 'damage_to_player', target_player=seat,
        source_card_id=source, source_lki=retained, amount=1)
    assert {row['source_id'] for row in rows} == set(wards)
    assert snapshot(state) == before
    assert resolve_top_of_stack(state)
    assert state.players[seat].life == 20


def hand_frame(seat):
    state, wards = position(seat)
    actor = 3-seat
    state.active_player = state.priority_player = actor
    path = Path(__file__).parents[2] / 'hand-source-causal/raw/twinshot-sniper.json'
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == '23ce6813335697376eb1398f0c5f94e03ab2cdffda8d8ae6162e2e8adbde2453'
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == 'Twinshot Sniper'
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 1}], [], seed=61)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = actor
    card.move_to_zone(Zone.HAND)
    state.cards[card.id] = card
    state.players[actor].hand.append(card.id)
    ability = next(row for row in extract_activated_abilities(card) if row['activation_zone'] == 'hand')
    state = act(state, actor, {'type': 'activate_ability', 'card_id': card.id,
        'ability_index': ability['index'], 'targets': {'target_player': seat}})
    frame = state.stack[-1]
    assert frame.controller == actor and frame.payload['__activation_source_context']['controller'] is None
    assert '__source_lki' not in frame.payload and state.cards[card.id].zone == Zone.GRAVEYARD
    return reload(state), wards, card.id


@pytest.mark.parametrize('seat', [1, 2])
def test_valid_hand_unknown_control_forwarded_to_legacy_preflight_and_application(monkeypatch, seat):
    state, wards, source = hand_frame(seat)
    state.players[seat].prevent_damage_shield = 1  # Explicit legacy scalar, not a typed receipt.
    frame = state.stack[-1]
    context = deepcopy(frame.payload['__activation_source_context'])
    assert damage_source_control(state, source, source_context=context) is None
    delegate = replacement.replacement_options
    seen = []

    def observe(*args, **kwargs):
        assert kwargs.get('source_context') == context
        assert kwargs.get('source_controller') is None
        seen.append(True)
        return delegate(*args, **kwargs)

    monkeypatch.setattr(replacement, 'replacement_options', observe)
    before = snapshot(state)
    validate_legacy_damage_boundary(state, frame)
    assert seen and snapshot(state) == before
    assert resolve_top_of_stack(state)
    assert state.players[seat].life == 19
    assert state.players[seat].prevent_damage_shield == 0
    assert_printed_wards(state, wards)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['version', 'controller', 'conflicting-lki'])
def test_malformed_or_conflicting_hand_context_rejects_without_query_mutation(seat, bad):
    state, wards, source = hand_frame(seat)
    context = deepcopy(state.stack[-1].payload['__activation_source_context'])
    lki = None
    if bad == 'version':
        context['version'] = 2
    elif bad == 'controller':
        context['controller'] = 3-seat
    else:
        lki = {'controller': 3-seat}
    before = snapshot(state)
    with pytest.raises(ActionRejected, match='HAND'):
        replacement.replacement_options(state, 'damage_to_player', target_player=seat,
            source_card_id=source, source_context=context, source_lki=lki, amount=2)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['missing', 'empty-lki', 'bad-lki', 'bool-lki', 'bad-controller'])
def test_unknown_source_never_uses_active_player_or_owner_as_controller(seat, case):
    state, wards = position(seat)
    state.active_player = 3-seat
    kwargs = {'source_card_id': 'departed-unknown'}
    if case == 'empty-lki':
        kwargs['source_lki'] = {}
    elif case == 'bad-lki':
        kwargs['source_lki'] = {'controller': 'opponent'}
    elif case == 'bool-lki':
        kwargs['source_lki'] = {'controller': True}
    elif case == 'bad-controller':
        kwargs['source_controller'] = 'opponent'
    before = snapshot(state)
    assert replacement.replacement_options(state, 'damage_to_player', target_player=seat,
                                           amount=2, **kwargs) == []
    assert snapshot(state) == before


def copied_bolt(seat, departed):
    state, wards = position(seat)
    state.active_player = state.priority_player = seat
    source = add(state, 'Lightning Bolt', seat, Zone.HAND)
    twin = add(state, 'Twincast', 3-seat, Zone.HAND)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source,
                             'targets': {'target_player': seat}})
    original = state.stack[-1].id
    state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': twin,
                              'targets': {'target_stack_id': original}})
    assert not resolve_top_of_stack(state)
    assert 'keep' in state.pending_mechanic_choice['options']
    state = act(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    copied = state.stack[-1]
    assert copied.controller == 3-seat and copied.payload['__stack_copy_kind'] == 'spell'
    assert copied.source_card_id == source and state.cards[source].controller == seat
    copied_id = copied.id
    if departed:
        counter = add(state, 'Counterspell', seat, Zone.HAND)
        if state.priority_player != seat:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
        state = act(state, seat, {'type': 'cast_spell', 'card_id': counter,
                                 'targets': {'target_stack_id': original}})
        assert resolve_top_of_stack(state)
        assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.stack[-1].id == copied_id
    return reload(state), wards, source


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('departed', [False, True])
def test_real_copy_legacy_veto_retains_actual_controller_before_pop(seat, departed):
    state, wards, source = copied_bolt(seat, departed)
    state.players[seat].prevent_damage_shield = 1
    before = snapshot(state)
    with pytest.raises(ActionRejected, match='Legacy numeric prevention'):
        resolve_top_of_stack(state)
    assert snapshot(state) == before
    assert state.stack[-1].controller != state.cards[source].controller


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('departed', [False, True])
def test_actual_copy_choices_keep_retained_control_across_snapshot_and_resume(seat, departed):
    state, wards, source = copied_bolt(seat, departed)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    assert not resolve_top_of_stack(state)
    selected = []
    for index in range(2):
        pending = state.pending_replacement_choice
        assert pending is not None
        assert {row['source_id'] for row in pending['options']} == set(wards)-set(selected)
        chosen = pending['options'][0]['source_id']
        selected.append(chosen)
        state = reload(state)
        state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': chosen})
    assert state.pending_replacement_choice is None and set(selected) == set(wards)
    assert state.players[seat].life == 19


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('amount', [0, -1])
def test_nonpositive_damage_still_has_no_offers_or_consumption(seat, amount):
    state, wards = position(seat)
    source = add(state, 'Prodigal Pyromancer', 3-seat)
    before = snapshot(state)
    assert replacement.replacement_options(state, 'damage_to_player', target_player=seat,
        source_card_id=source, amount=amount) == []
    assert replacement.apply_damage_replacements(state, seat, amount) == amount
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unpreventable_damage_never_offers_or_consumes_qualified_prevention(seat):
    state, wards = position(seat)
    source = add(state, 'Prodigal Pyromancer', 3-seat)
    state.turn_damage_cant_be_prevented = True
    before = snapshot(state)
    assert replacement.replacement_options(state, 'damage_to_player', target_player=seat,
        source_card_id=source, amount=2) == []
    assert snapshot(state) == before
    assert deal_damage(state, 3-seat, {'target_player': seat, 'amount': 2,
                                     '__source_card_id': source}) == 2
    assert state.players[seat].life == 18
