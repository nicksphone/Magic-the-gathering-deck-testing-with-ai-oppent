"""Tests/report-only: separate cast abilities and canonical subject predicates."""
from copy import copy, deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import main
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_spell_trigger_surface_audit import (
    act, cards, install, offline_http, record, restore, snapshot,
)


DIRECTORY = Path(__file__).parent / 'fixtures/multicast_audit'
RAW = {row['name']: row for row in map(json.loads, (DIRECTORY / 'canonical.jsonl').read_text().splitlines())}
FAMILIES = ['Storm-Kiln Artist', 'Archmage Emeritus', 'Talrand, Sky Summoner', 'Balmor, Battlemage Captain']


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    raw = RAW.get(name, cards.ROWS.get(name))
    assert raw and raw['name'] == name
    hydrated = deepcopy(raw)
    if raw.get('card_faces'):
        front = raw['card_faces'][0]
        for key in ['oracle_text', 'mana_cost', 'power', 'toughness', 'loyalty', 'colors']:
            if key in front:
                hydrated[key] = front[key]
    sample = MatchFactory.from_decks([{**hydrated, 'card_name': raw['name'], 'quantity': 1}], [], seed=101)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    card.summoning_sick = False
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def position(seat, source_name='Shock'):
    state = cards.position(seat)
    source = add(state, source_name, seat, Zone.HAND)
    for name in ['Island', 'Forest', 'Swamp']:
        add(state, name, seat, Zone.LIBRARY)
    state.players[seat].mana_pool = {color: 20 for color in 'WUBRGC'}
    return state, source


def announce(state, seat, source, face=None, target=None):
    action = {'type': 'cast_spell', 'card_id': source.id}
    if face is not None:
        action['selected_face_index'] = face
    if source.name == 'Shock' or face == 1:
        action['targets'] = {'target_player': 3-seat} if target is None else {'target_card_id': target}
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    return paid, action


def restart(state):
    before = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(deepcopy(before))
    assert serialize_match_snapshot(result) == before
    return result


def test_canonical_provenance_no_modified_facts_or_aliases():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert provenance['offline'] and not provenance['facts_modified']
    assert hashlib.sha256((DIRECTORY / 'canonical.jsonl').read_bytes()).hexdigest() == provenance['fixture_sha256']
    assert len(RAW) == 12
    for row in provenance['rows']:
        assert (RAW[row['name']]['id'], RAW[row['name']]['oracle_id']) == (row['id'], row['oracle_id'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('source_name,face,expected', [
    ('Shock', None, 1), ('Raging Goblin', None, 0), ('Jeskai Ascendancy', None, 0),
    ('Bonecrusher Giant // Stomp', 0, 0), ('Bonecrusher Giant // Stomp', 1, 1),
])
def test_actual_checked_subject_predicates_and_adventure_surface(request, seat, family, source_name, face, expected):
    state, source = position(seat, source_name)
    listener = add(state, family, seat)
    paid, action = announce(state, seat, source, face)
    triggers = [item for item in paid.stack if item.source_card_id == listener.id]
    record(request, {'family_oracle': RAW[family], 'source_raw': RAW[source_name], 'action': action,
                     'expected_count': expected, 'actual_count': len(triggers),
                     'queued': serialize_match_snapshot(paid)})
    assert len(triggers) == expected
    assert serialize_match_snapshot(restart(paid)) == serialize_match_snapshot(paid)


@pytest.mark.parametrize('seat', [1, 2])
def test_two_printed_cast_abilities_are_two_distinct_stack_items(request, seat):
    state, source = position(seat)
    listener = add(state, 'Jeskai Ascendancy', seat)
    paid, action = announce(state, seat, source)
    triggers = [item for item in paid.stack if item.source_card_id == listener.id]
    instructions = []
    for line in listener.oracle_text.splitlines():
        proxy = copy(listener)
        proxy.oracle_text = line.split(', ', 1)[1]
        with cards.unchanged_root(state):
            compiled = infer_effect_from_oracle(state, proxy, seat, report_unsupported=False)
        instructions.append({'oracle_clause': line, 'compiled': compiled})
    record(request, {'action': action, 'instructions': instructions,
                     'expected_count': 2, 'actual_count': len(triggers), 'queued': serialize_match_snapshot(paid)})
    assert len(triggers) == 2 and len({item.id for item in triggers}) == 2


def settle_http(client, identifier, seat, accept, request):
    trace = []
    for _ in range(32):
        match = restore(identifier)
        state = match.state
        pending = state.pending_trigger_order
        mechanic = state.pending_mechanic_choice
        if pending and pending.get('phase') == 'optional':
            actor = pending['current_controller']
            action = {'type': 'choose_optional_effect', 'stack_id': pending['current_stack_id'], 'accept': accept}
        elif pending and 'phase' not in pending:
            actor = pending['current_controller']
            group = pending['groups'][str(actor)]
            action = {'type': 'choose_trigger_order', 'trigger_order': [row['_choice_id'] for row in reversed(group)]}
        elif mechanic:
            actor = mechanic['player_id']
            if mechanic['kind'] == 'copy_target':
                assert 'keep' in mechanic['options']
                action = {'type': 'choose_mechanic', 'card_ids': ['keep']}
            else:
                raise AssertionError('Unqualified continuation requires explicit new handler: ' + repr(mechanic))
        elif not state.stack:
            return match, trace
        else:
            actor = state.priority_player
            action = {'type': 'pass_priority'}
        trace.append({'actor': actor, 'action': action, 'before': serialize_match_snapshot(state)})
        record(request, {'continuation': trace, 'current': serialize_match_snapshot(state)})
        if match.controllers[actor] == 'ai':
            response = client.post('/matches/' + identifier + '/autoplay?ticks=1')
        else:
            response = act(client, match, actor, action)
        assert response.status_code == 200, response.text
    raise AssertionError('Bounded32-step canonical continuation did not finish')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_actual_private_http_multi_cast_order_life_hand_board_restart(request, offline_http, seat, accept):
    state, source = position(seat)
    ascendancy = add(state, 'Jeskai Ascendancy', seat)
    storm = add(state, 'Storm-Kiln Artist', seat)
    talrand = add(state, 'Talrand, Sky Summoner', seat)
    goblin = add(state, 'Raging Goblin', seat)
    state.cards[goblin.id].tapped = True
    held = add(state, 'Raging Goblin', seat, Zone.HAND)
    secret = add(state, 'Raging Goblin', 3-seat, Zone.HAND)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    match = install(state, seat, request, private=True)
    response = act(offline_http, match, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {'target_player': 3-seat}})
    assert response.status_code == 200, response.text
    match = restore(state.id)
    pending = deepcopy(match.state.pending_trigger_order)
    assert pending and 'phase' not in pending
    group = pending['groups'][str(seat)]
    order = [row['_choice_id'] for row in reversed(group)]
    action = {'type': 'choose_trigger_order', 'trigger_order': order}
    before = snapshot(match)
    response = act(offline_http, match, 3-seat, action)
    assert response.status_code == 403 and snapshot(match) == before
    response = act(offline_http, match, seat, {**action, 'trigger_order': order[:-1]})
    assert response.status_code == 422 and snapshot(match) == before
    response = act(offline_http, match, seat, action)
    assert response.status_code == 200, response.text
    queued = serialize_match_snapshot(restore(state.id).state)
    match, trace = settle_http(offline_http, state.id, seat, accept, request)
    public = main._serialize_match_controller(match)
    assert secret.id not in json.dumps(public) and public['root_seed'] is None
    record(request, {'canonical_oracle': RAW['Jeskai Ascendancy'], 'pending': pending, 'order': order,
                     'queued': queued, 'continuation': trace, 'accept': accept, 'public': public,
                     'actual_hand': list(match.state.players[seat].hand), 'expected_hand_count': 1,
                     'actual_goblin_pt': [effective_power(match.state, goblin.id), effective_toughness(match.state, goblin.id)],
                     'actual_tapped': match.state.cards[goblin.id].tapped,
                     'resolved': serialize_match_snapshot(match.state)})
    assert sum(row['source_card_id'] == ascendancy.id for row in group) == 2
    assert {row['source_card_id'] for row in group} == {ascendancy.id, storm.id, talrand.id}
    assert len(group) == 4 and len(set(order)) == 4
    assert not match.state.cards[goblin.id].tapped
    assert (effective_power(match.state, goblin.id), effective_toughness(match.state, goblin.id)) == (2, 2)
    assert len(match.state.players[seat].hand) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('caster_active', [False, True])
def test_actual_cast_target_ward_apnap_and_user_order_preserved(request, seat, caster_active):
    state, source = position(seat)
    state.active_player = seat if caster_active else 3-seat
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat, 3-seat}
    listeners = [add(state, family, seat) for family in ['Storm-Kiln Artist', 'Archmage Emeritus']]
    target = add(state, 'Kappa Cannoneer', 3-seat)
    paid, action = announce(state, seat, source, target=target.id)
    pending = deepcopy(paid.pending_trigger_order)
    assert pending and 'phase' not in pending
    group = pending['groups'][str(seat)]
    order = [row['_choice_id'] for row in reversed(group)]
    with cards.unchanged_root(paid):
        ordered = checked_action(paid, RulesEngine(), seat, {'type': 'choose_trigger_order', 'trigger_order': order})
    ordered = restart(ordered)
    triggers = [item for item in ordered.stack if item.payload.get('__trigger_event')]
    record(request, {'action': action, 'pending': pending, 'chosen_order': order,
                     'ordered': serialize_match_snapshot(ordered), 'controllers': [item.controller for item in triggers]})
    expected = [seat, seat, 3-seat] if caster_active else [3-seat, seat, seat]
    assert [item.controller for item in triggers] == expected
    assert {item.source_card_id for item in triggers if item.controller == seat} == {card.id for card in listeners}
    assert next(item for item in triggers if item.controller == 3-seat).source_card_id == target.id


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_reverberate_copy_only_matches_magecraft_not_cast_only(request, offline_http, seat):
    state, source = position(seat)
    storm = add(state, 'Storm-Kiln Artist', seat)
    archmage = add(state, 'Archmage Emeritus', seat)
    talrand = add(state, 'Talrand, Sky Summoner', seat)
    copying = add(state, 'Reverberate', seat, Zone.HAND)
    match = install(state, seat, request)
    response = act(offline_http, match, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {'target_player': 3-seat}})
    assert response.status_code == 200, response.text
    match = restore(state.id)
    original = next(item for item in match.state.stack if item.source_card_id == source.id)
    response = act(offline_http, match, seat, {'type': 'cast_spell', 'card_id': copying.id, 'targets': {'target_stack_id': original.id}})
    assert response.status_code == 200, response.text
    queued = serialize_match_snapshot(restore(state.id).state)
    match, trace = settle_http(offline_http, state.id, seat, False, request)
    tokens = [match.state.cards[cid] for cid in match.state.players[seat].battlefield if match.state.cards[cid].is_token]
    counts = {name: sum(card.name == name for card in tokens) for name in ['Treasure', 'Drake']}
    record(request, {'queued': queued, 'continuation': trace, 'counts': counts,
                     'listeners': [storm.id, archmage.id, talrand.id], 'resolved': serialize_match_snapshot(match.state)})
    assert counts == {'Treasure': 3, 'Drake': 2}
    assert match.state.draws_this_turn[seat] == 3
    assert match.state.players[3-seat].life == 16
