"""Canonical matched-trigger context, public target choices and HTTP replay."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone, _infer_keywords
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_spell_trigger_surface_audit import (
    act, add as fixture_add, cards, install, offline_http, position, record, restore, settle, snapshot,
)
from tests import test_spell_trigger_surface_siblings as siblings


DIRECTORY = Path(__file__).parent / 'fixtures/trigger_context'
RAW = {row['name']: row for row in map(json.loads, (DIRECTORY / 'canonical.jsonl').read_text().splitlines())}
cards.ROWS.update(RAW)
TOKEN_RAW = json.loads((Path(__file__).parent / 'fixtures/token_descriptor_canonical/canonical.json').read_text())
cards.ROWS.update(TOKEN_RAW)


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    card = fixture_add(state, name, seat, zone)
    # The raw keyword metadata says "Protection", not its Oracle quality.
    # MatchFactory normally supplies these inferred printed keyword phrases.
    card.keywords = sorted(set(card.keywords) | set(_infer_keywords(card.oracle_text)))
    return card


def test_new_raw_rows_are_unchanged_canonical_records():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert provenance['offline'] and not provenance['facts_modified']
    assert hashlib.sha256((DIRECTORY / 'canonical.jsonl').read_bytes()).hexdigest() == provenance['fixture_sha256']
    for row in provenance['rows']:
        assert (RAW[row['name']]['id'], RAW[row['name']]['oracle_id']) == (row['id'], row['oracle_id'])


def private_view(match, secret):
    public = main._serialize_match_controller(match)
    assert secret.id not in json.dumps(public)
    assert public['root_seed'] is None
    return public


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Resounding Roar', 'Resounding Thunder'])
def test_actual_private_http_cycle_targets_cost_source_and_restart(request, offline_http, seat, name):
    state, source = position(seat, name)
    own = add(state, 'Krosan Tusker', seat)
    opponent = add(state, 'Krosan Tusker', 3-seat)
    hexproof = add(state, 'Slippery Bogle', 3-seat)
    shroud = add(state, 'Wall of Denial', 3-seat)
    protected = add(state, 'Kor Firewalker', 3-seat)
    secret = add(state, 'Swamp', 3-seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 5, 'B': 1, 'R': 1, 'G': 1, 'W': 1}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    match = install(state, seat, request, private=True)
    response = act(offline_http, match, seat, {'type': 'cycle_card', 'card_id': source.id})
    assert response.status_code == 200, response.text
    match = restore(state.id)
    queued = serialize_match_snapshot(match.state)
    pending = deepcopy(match.state.pending_trigger_order)
    assert pending and pending['phase'] == 'targets'
    with cards.unchanged_root(match.state):
        offered = RulesEngine().legal_moves(match.state, seat)
    record(request, {'queued': queued, 'pending': pending, 'offered': offered})
    assert {move['type'] for move in offered} == {'choose_trigger_target'}
    ids = {move.get('target_card_id') for move in offered}
    assert own.id in ids and opponent.id in ids
    assert hexproof.id not in ids and shroud.id not in ids
    assert (protected.id in ids) == (name == 'Resounding Roar')
    choice = {'type': 'choose_trigger_target', 'stack_id': pending['current_stack_id']}
    before = snapshot(match)
    wrong_actor = act(offline_http, match, 3-seat, {**choice, 'target_card_id': own.id})
    assert wrong_actor.status_code == 403 and snapshot(match) == before
    bad_target = act(offline_http, match, seat, {**choice, 'target_card_id': source.id})
    assert bad_target.status_code == 422 and snapshot(match) == before
    if name == 'Resounding Roar':
        choice['target_card_id'] = opponent.id
    else:
        choice['target_player'] = 3-seat
    response = act(offline_http, match, seat, choice)
    assert response.status_code == 200, response.text
    chosen = serialize_match_snapshot(restore(state.id).state)
    match, optional = settle(offline_http, state.id, seat)
    assert not optional
    assert match.state.players[seat].life == 20
    assert match.state.players[3-seat].life == (14 if name == 'Resounding Thunder' else 20)
    expected = (12, 11) if name == 'Resounding Roar' else (6, 5)
    assert (effective_power(match.state, opponent.id), effective_toughness(match.state, opponent.id)) == expected
    assert (effective_power(match.state, own.id), effective_toughness(match.state, own.id)) == (6, 5)
    assert match.state.draws_this_turn.get(seat) == 1
    assert match.state.cards[source.id].zone == Zone.GRAVEYARD
    record(request, {'canonical': RAW.get(name, siblings.SIBLINGS.get(name)),
                     'queued': queued, 'pending': pending, 'offered': offered,
                     'choice': choice, 'chosen': chosen, 'public': private_view(match, secret),
                     'resolved': serialize_match_snapshot(match.state)})


@pytest.mark.parametrize('seat', [1, 2])
def test_cycle_with_no_legal_target_keeps_the_draw_not_an_untargeted_buff(request, seat):
    state, source = position(seat, 'Resounding Roar')
    state.players[seat].mana_pool = {'C': 5, 'R': 1, 'G': 1, 'W': 1}
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, {'type': 'cycle_card', 'card_id': source.id})
    record(request, {'queued': serialize_match_snapshot(paid)})
    assert [item.effect_key for item in paid.stack] == ['cycle_draw']
    assert any('has no legal target' in line for line in paid.log)
    assert resolve_top_of_stack(paid)
    assert paid.draws_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_two_canonical_cast_listeners_keep_separate_sources_actual_http(request, offline_http, seat):
    state, source = position(seat)
    shark = add(state, 'Shark Typhoon', seat)
    drake = add(state, 'Talrand, Sky Summoner', seat)
    secret = add(state, 'Swamp', 3-seat, Zone.HAND)
    match = install(state, seat, request, private=True)
    response = act(offline_http, match, seat, cards.cast(source))
    assert response.status_code == 200, response.text
    match = restore(state.id)
    queued = serialize_match_snapshot(match.state)
    triggers = [item for item in match.state.stack if item.payload.get('__trigger_event') == 'spell_cast']
    assert {item.source_card_id for item in triggers} == {shark.id, drake.id}
    shark_trigger = next(item for item in triggers if item.source_card_id == shark.id)
    assert shark_trigger.effect_key == 'create_shark_token'
    assert shark_trigger.payload['source_card_id'] == source.id
    assert 'cycle' not in shark_trigger.payload['__trigger_full_clause']
    match, optional = settle(offline_http, state.id, seat)
    assert not optional
    tokens = [match.state.cards[cid] for cid in match.state.players[seat].battlefield if match.state.cards[cid].is_token]
    assert sorted((card.name, card.power, card.toughness) for card in tokens) == [('Drake', 2, 2), ('Shark', 3, 3)]
    actual_drake = next(card for card in tokens if card.name == 'Drake')
    assert actual_drake.colors == ['U'] and actual_drake.keywords == ['flying']
    assert 'Artifact' not in actual_drake.types
    assert match.state.players[seat].life == 26
    record(request, {'queued': queued, 'public': private_view(match, secret),
                     'resolved': serialize_match_snapshot(match.state)})


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_trigger_survives_source_removal_with_each_cast_mana_value(request, offline_http, seat):
    state, source = position(seat)
    shark = add(state, 'Shark Typhoon', seat)
    removal = add(state, 'Disenchant', seat, Zone.HAND)
    secret = add(state, 'Swamp', 3-seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 3, 'W': 2, 'U': 1}
    match = install(state, seat, request, private=True)
    response = act(offline_http, match, seat, cards.cast(source))
    assert response.status_code == 200, response.text
    match = restore(state.id)
    response = act(offline_http, match, seat, cards.cast(removal, targets={'target_card_id': shark.id}))
    assert response.status_code == 200, response.text
    queued = serialize_match_snapshot(restore(state.id).state)
    match, optional = settle(offline_http, state.id, seat)
    assert not optional and match.state.cards[shark.id].zone == Zone.GRAVEYARD
    tokens = [match.state.cards[cid] for cid in match.state.players[seat].battlefield if match.state.cards[cid].is_token]
    assert sorted((card.power, card.toughness) for card in tokens) == [(2, 2), (3, 3)]
    assert match.state.players[seat].life == 26
    record(request, {'queued': queued, 'public': private_view(match, secret),
                     'resolved': serialize_match_snapshot(match.state)})


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_cast_vs_copy_event_routing_not_a_played_copy_claim(request, seat):
    state, source = position(seat, 'Shock')
    storm = add(state, 'Storm-Kiln Artist', seat)
    shark = add(state, 'Shark Typhoon', seat)
    state.players[seat].mana_pool = {'R': 1}
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, cards.cast(source, targets={'target_player': 3-seat}))
    emit_event(paid, 'spell_copy', {'source_card_id': source.id, 'controller': seat})
    triggers = [item for item in paid.stack if item.payload.get('__trigger_event') in {'spell_cast', 'spell_copy'}]
    assert sum(item.source_card_id == storm.id for item in triggers) == 2
    assert sum(item.source_card_id == shark.id for item in triggers) == 1
    queued = serialize_match_snapshot(paid)
    for _ in range(6):
        if not paid.stack:
            break
        assert resolve_top_of_stack(paid)
    tokens = [paid.cards[cid] for cid in paid.players[seat].battlefield if paid.cards[cid].is_token]
    assert sorted(card.name for card in tokens) == ['Shark', 'Treasure', 'Treasure']
    assert paid.players[3-seat].life == 18
    record(request, {'queued': queued, 'resolved': serialize_match_snapshot(paid),
                     'copy_notification_only': True})
