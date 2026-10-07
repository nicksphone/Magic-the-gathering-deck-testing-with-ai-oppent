"""Canonical checked self returns; grammar/native-provider controls are labeled."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.move_generator import legal_moves
from rules_engine.oracle_effects import extract_activated_abilities, activation_source_eligible
from rules_engine.targeting import stack_object_kind
from tests.test_canonical_land_animation_audit import position as land_position, snapshot
from tests.test_linked_damage_targets import raw_card

D = Path(__file__).parent / 'fixtures/graveyard_self_activation'
ROWS = {}
for manifest in ('provenance.json', 'control-provenance.json'):
    for entry in json.loads((D / manifest).read_text())['cards']:
        data = (D / entry['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry['sha256']
        row = json.loads(data)
        assert row['id'] == entry['id'] and row['oracle_id'] == entry['oracle_id']
        ROWS[row['name']] = row
FAMILIES = ['Reassembling Skeleton', 'Sanitarium Skeleton']


def record(request, **data):
    path = Path(os.environ['MTG_GY_SELF_EVIDENCE']) / (
        hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    with path.open('x') as stream:
        json.dump({'node': request.node.nodeid, **data}, stream, sort_keys=True, indent=2)


def position(seat, name):
    state, unused = land_position(seat, 'Mutavault')
    state.players[seat].battlefield.remove(unused.id)
    del state.cards[unused.id]
    source = raw_card(state, ROWS[name], seat, Zone.GRAVEYARD)
    state.players[seat].mana_pool = {'B': 1, 'C': 1 if name == FAMILIES[0] else 2}
    return state, source


def action(source):
    return {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0}


def act(state, seat, value):
    before = snapshot(state)
    result = checked_action(state, RulesEngine(), seat, value)
    assert snapshot(state) == before
    assert snapshot(deserialize_match_snapshot(snapshot(result))) == snapshot(result)
    return result


def resolve(state):
    for _ in range(16):
        if not state.stack or state.pending_replacement_choice:
            return state
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Real priority resolution exceeded sixteen passes')


def paid(state, seat, source):
    before = snapshot(state)
    ref = {'incarnation': object_incarnation(source),
           'zone_change_sequence': source.zone_change_sequence}
    offers = [m for m in legal_moves(state, seat)
              if m['type'] == 'activate_ability' and m.get('card_id') == source.id]
    assert len(offers) == 1 and offers[0]['ability_index'] == 0
    assert not offers[0]['target_hints'].get('action_has_target_text')
    assert snapshot(state) == before
    result = act(state, seat, action(source))
    assert not any(result.players[seat].mana_pool.values())
    item = result.stack[-1]
    assert stack_object_kind(result, item) == 'activated' and item.controller == seat
    assert item.payload['__activation_source_reference'] == ref
    assert item.payload['target_card_id'] == source.id
    key = 'zone_change_sequence' if source.name == FAMILIES[0] else 'zone_sequence'
    assert item.payload['__graveyard_reference'] == {
        'incarnation': ref['incarnation'], key: ref['zone_change_sequence']}
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_full_canonical_paid_self_return_and_snapshot_golden(request, seat, name, monkeypatch):
    state, source = position(seat, name)
    # A graveyard card has no battlefield controller; owner authorizes activation.
    source.controller = 3-seat
    printed = deepcopy((source.oracle_text, source.type_line, source.colors))
    announced = paid(state, seat, source)
    observations = []
    import effects.handlers as handlers
    original = handlers.emit_event
    def observe(current, event, payload):
        if event == 'enters_battlefield' and payload.get('card_id') == source.id:
            observations.append({'tapped': current.cards[source.id].tapped,
                                 'controller': current.cards[source.id].controller})
        return original(current, event, payload)
    monkeypatch.setattr(handlers, 'emit_event', observe)
    result = resolve(deserialize_match_snapshot(snapshot(announced)))
    returned = result.cards[source.id]
    destination = Zone.BATTLEFIELD if name == FAMILIES[0] else Zone.HAND
    assert returned.zone == destination and returned.owner == returned.controller == seat
    assert source.id not in result.players[seat].graveyard
    assert getattr(result.players[seat], destination.value).count(source.id) == 1
    assert (returned.oracle_text, returned.type_line, returned.colors) == printed
    assert returned.zone_change_sequence == source.zone_change_sequence + 1
    if destination == Zone.BATTLEFIELD:
        assert returned.tapped and returned.summoning_sick
        assert observations == [{'tapped': True, 'controller': seat}]
    else:
        assert observations == []
    first_observations = deepcopy(observations)
    assert snapshot(resolve(deepcopy(announced))) == snapshot(result)
    record(request, before=snapshot(state), announced=snapshot(announced),
           after=snapshot(result), entry_observations=first_observations)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('fault', ['wrong_actor', 'unpayable', 'foreign_owner', 'missing_membership', 'forged_target'])
def test_rejected_self_activation_is_entire_root_atomic(request, seat, name, fault):
    state, source = position(seat, name)
    actor, request_action = seat, action(source)
    if fault == 'wrong_actor':
        actor = 3-seat
        state.priority_player = actor
    elif fault == 'unpayable':
        state.players[seat].mana_pool = {}
    elif fault == 'foreign_owner':
        source.owner = 3-seat
    elif fault == 'missing_membership':
        state.players[seat].graveyard.remove(source.id)
    else:
        other = raw_card(state, ROWS[name], seat, Zone.GRAVEYARD)
        request_action['targets'] = {'target_card_id': other.id}
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), actor, request_action)
    assert snapshot(state) == before
    record(request, fault=fault, root=before)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('zone', [Zone.BATTLEFIELD, Zone.HAND, Zone.EXILE])
def test_complete_self_instruction_is_not_a_permission_from_other_zones(request, seat, name, zone):
    state, source = position(seat, name)
    state.players[seat].graveyard.remove(source.id)
    source.move_to_zone(zone)
    getattr(state.players[seat], zone.value).append(source.id)
    before = snapshot(state)
    assert not activation_source_eligible(state, seat, source.id, extract_activated_abilities(source)[0])
    assert not any(m['type'] == 'activate_ability' and m.get('card_id') == source.id
                   for m in legal_moves(state, seat))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action(source))
    assert snapshot(state) == before
    record(request, zone=zone.value, root=before)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_real_paid_stifle_counters_only_ability_without_cost_refund(request, seat, name):
    state, source = position(seat, name)
    counter = raw_card(state, ROWS['Stifle'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    state = paid(state, seat, source)
    activation = state.stack[-1].id
    state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                              'targets': {'target_stack_id': activation}})
    result = resolve(state)
    assert not result.stack and result.cards[source.id].zone == Zone.GRAVEYARD
    assert not any(result.players[seat].mana_pool.values())
    assert not any(result.players[3-seat].mana_pool.values())
    assert result.cards[counter.id].zone == Zone.GRAVEYARD
    record(request, after=snapshot(result), countered_stack_id=activation)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_real_cremate_response_and_native_graveyard_reentry_does_not_return_new_object(request, seat, name):
    from rules_engine.replacement import select_graveyard_entry_plan
    from rules_engine.zone_actions import execute_graveyard_entry
    state, source = position(seat, name)
    exile = raw_card(state, ROWS['Cremate'], seat, Zone.HAND)
    state = paid(state, seat, source)
    state.players[seat].mana_pool = {'B': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': exile.id,
                            'targets': {'target_card_id': source.id}})
    # Resolve the actual Cremate only, keeping the old activation on the stack.
    for _ in range(8):
        if len(state.stack) == 1:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert len(state.stack) == 1 and state.cards[source.id].zone == Zone.EXILE
    exiled = snapshot(state)
    state = deserialize_match_snapshot(exiled)
    # Native provider identity control, NOT a claim that Pull from Eternity is supported.
    execute_graveyard_entry(state, select_graveyard_entry_plan(state, source.id))
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    reentered = snapshot(state)
    result = resolve(state)
    assert result.cards[source.id].zone == Zone.GRAVEYARD
    assert result.cards[source.id].zone_change_sequence == reentered['cards'][source.id]['zone_change_sequence']
    assert not any(result.players[seat].mana_pool.values())
    record(request, exiled=exiled, native_provider_reentry=reentered, after=snapshot(result),
           limitation='Reentry uses real native zone provider, not a checked return-from-exile card spell')


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_entry_prohibition_preserves_paid_cost_and_source(request, seat):
    state, source = position(seat, FAMILIES[0])
    cage = raw_card(state, ROWS["Grafdigger's Cage"], 3-seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, cage.id)
    result = resolve(paid(state, seat, source))
    assert result.cards[source.id].zone == Zone.GRAVEYARD
    assert not any(result.players[seat].mana_pool.values())
    record(request, after=snapshot(result))


@pytest.mark.parametrize('seat', [1, 2])
def test_real_counter_pending_retains_tapped_entry_across_native_restore(request, seat):
    state, source = position(seat, FAMILIES[0])
    for name in ('Renata, Called to the Hunt', 'Doubling Season', "Lae'zel, Vlaakith's Champion"):
        card = raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, card.id)
    state.replacement_choice_players = {seat}
    state = resolve(paid(state, seat, source))
    assert state.pending_replacement_choice and state.cards[source.id].zone == Zone.GRAVEYARD
    pending = snapshot(state)
    assert '"tapped": true' in json.dumps(pending['pending_replacement_choice'])
    state = deserialize_match_snapshot(pending)
    option = next(o for o in state.pending_replacement_choice['options'] if o['operation'] == 'add')
    state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    if state.pending_replacement_choice:
        option = state.pending_replacement_choice['options'][0]
        state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    assert not state.pending_replacement_choice
    assert state.cards[source.id].zone == Zone.BATTLEFIELD and state.cards[source.id].tapped
    assert state.cards[source.id].counters.get('+1/+1') == 4
    record(request, pending=pending, after=snapshot(state))


@pytest.mark.parametrize('suffix', [' Draw a card.', ' Activate only during your upkeep.',
                                  ' If you gained life this turn.', ' Then draw a card.'])
@pytest.mark.parametrize('name', FAMILIES)
def test_grammar_only_unknown_complete_tail_not_prefix_admitted_and_indices_preserved(name, suffix):
    from rules_engine.oracle_effects import _pure_self_graveyard_return_instruction
    raw = ROWS[name]
    text = raw['oracle_text'].split(':', 1)[1].strip() + suffix
    assert _pure_self_graveyard_return_instruction(None, text) is None
    proxy = SimpleNamespace(name=name, oracle_text=raw['oracle_text'] + suffix + '\n{1}: Draw a card.')
    extracted = extract_activated_abilities(proxy)
    assert len(extracted) == 1 and extracted[0]['index'] == 1
    assert extracted[0]['activation_zone'] == 'battlefield'


@pytest.mark.parametrize('name', FAMILIES)
def test_grammar_only_parenthesized_unknown_restriction_is_not_erased(name):
    from rules_engine.oracle_effects import _pure_self_graveyard_return_instruction
    text = ROWS[name]['oracle_text'] + ' (Activate only during your upkeep.)'
    assert _pure_self_graveyard_return_instruction(None, text.split(':', 1)[1]) is None
    assert extract_activated_abilities(SimpleNamespace(name=name, oracle_text=text)) == []
