"""NEW mixed proposal: actual paid HTTP/SQLite; private views are AI, not HH UI."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path

import pytest
from sqlmodel import Session

import main
from ai.information import decision_view, is_unknown
from game_state.observations import public_card_ids, remembered_hand_card
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from rules_engine.targeting import stack_object_kind
from tests.test_api_input_contracts import game, persist, snapshot
from tests import pending_source_privacy_support as causal
import test_brainstorm_desired as brain


def current(mid):
    return main.ACTIVE_MATCHES[mid]


def request(client, mid, actor, action, headers=None):
    response = client.post(f'/matches/{mid}/action',
                           json={'player_id': actor, 'action': action}, headers=headers or {})
    directory = os.environ.get('MTG_BRAINSTORM_MIXED_EVIDENCE')
    if directory:
        path = Path(directory)/'actual-http-episodes.jsonl'
        row = {'case': os.environ.get('PYTEST_CURRENT_TEST'), 'actor': actor,
               'action': action, 'headers': headers or {}, 'status': response.status_code,
               'response': response.json(), 'snapshot': serialize_match_snapshot(current(mid).state)}
        encoded = json.dumps(row, sort_keys=True) + '\n'
        assert (path.stat().st_size if path.exists() else 0) + len(encoded.encode()) <= 256*1024*1024
        with path.open('a') as out:
            out.write(encoded)
    return response


def submit(client, mid, actor, action, headers=None):
    response = request(client, mid, actor, action, headers)
    assert response.status_code == 200, response.text
    return current(mid).state


def moves(client, mid, actor):
    before = snapshot(current(mid))
    response = client.get(f'/matches/{mid}/legal-moves?player_id={actor}')
    assert response.status_code == 200, response.text
    assert snapshot(current(mid)) == before
    return response.json()['moves']


def restore(mid):
    before = snapshot(current(mid))
    main.ACTIVE_MATCHES.pop(mid)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), mid)
    assert snapshot(current(mid)) == before
    return current(mid).state


def install_position(controller, state):
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    return state.id


def advance(client, mid, predicate):
    for _ in range(96):
        state = current(mid).state
        if predicate(state):
            return state
        assert not state.pending_trigger_order and not state.pending_replacement_choice
        assert not state.pending_mechanic_choice
        submit(client, mid, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('96 genuine HTTP priority actions exceeded bound')


def cast(client, mid, actor, cid, targets=None):
    state = current(mid).state
    if state.priority_player != actor:
        submit(client, mid, state.priority_player, {'type': 'pass_priority'})
    assert current(mid).state.priority_player == actor
    offered = moves(client, mid, actor)
    assert any(m['type'] == 'cast_spell' and m.get('card_id') == cid for m in offered)
    pool = deepcopy(current(mid).state.players[actor].mana_pool)
    old_stack_ids = {item.id for item in current(mid).state.stack}
    state = submit(client, mid, actor, {'type': 'cast_spell', 'card_id': cid,
                                     'cost_choice': {'id': 'base'}, 'targets': targets or {}})
    assert state.players[actor].mana_pool != pool
    assert state.cards[cid].zone == Zone.STACK
    added = [item for item in state.stack if item.id not in old_stack_ids
             and item.source_card_id == cid and stack_object_kind(state, item) == 'spell']
    assert len(added) == 1
    item = added[0]
    canonical = {**brain.ROWS, **causal.ROWS}[state.cards[cid].name]
    assert state.cards[cid].oracle_text == canonical['oracle_text']
    assert item.payload['mana_spent'] == int(canonical['cmc'])
    assert sum(pool.values())-sum(state.players[actor].mana_pool.values()) == int(canonical['cmc'])
    return item.id


def pending_brainstorm(client, mid, actor, source):
    state = current(mid).state
    old_hand = set(state.players[actor].hand) - {source}
    old_library = list(state.players[actor].library)
    frame = cast(client, mid, actor, source)
    state = advance(client, mid, lambda s: bool(s.pending_mechanic_choice))
    assert state.pending_mechanic_choice['kind'] == 'hand_top_order'
    assert state.pending_mechanic_choice['player_id'] == actor
    assert state.pending_mechanic_choice['count'] == 2
    assert state.players[actor].library == old_library[:-3]
    assert set(state.players[actor].hand) == old_hand | set(old_library[-3:])
    assert state.cards[source].zone == Zone.STACK
    assert all(item.id != frame for item in state.stack)
    public = moves(client, mid, actor)
    assert len(public) == 1 and public[0]['kind'] == 'hand_top_order'
    assert set(public[0]['options']) == set(state.players[actor].hand)
    assert 'topmost first' in public[0]['label']
    assert 'effect_payload' not in public[0] and 'resolving_item' not in public[0]
    assert moves(client, mid, 3-actor) == []
    return restore(mid)


def ordinary(game, seat):
    client, controller = game
    state = brain.position(seat)
    brain.add(state, 'Counterspell', seat, Zone.HAND)
    foreign = brain.add(state, 'Regrowth', 3-seat, Zone.HAND)
    source = brain.add(state, 'Brainstorm', seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1}
    mid = install_position(controller, state)
    state = pending_brainstorm(client, mid, seat, source)
    assert state.players[seat].mana_pool.get('U', 0) == 0
    return client, mid, source, foreign


def private_cards(state, seat):
    before = serialize_match_snapshot(state)
    view, _ = decision_view(state, 3-seat, [])
    assert all(is_unknown(view.cards[cid]) for player in state.players.values() for cid in player.library)
    assert all(is_unknown(view.cards[cid]) for cid in state.players[seat].hand
               if remembered_hand_card(state, 3-seat, state.cards[cid]) is None)
    assert serialize_match_snapshot(state) == before
    return view


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reverse', [False, True])
def test_paid_ordered_put_two_pending_sql_restore(game, seat, reverse):
    client, mid, source, _ = ordinary(game, seat)
    state = current(mid).state
    private_cards(state, seat)
    chosen = list(state.players[seat].hand[:2])
    if reverse:
        chosen.reverse()
    refs = {cid: state.cards[cid].zone_change_sequence for cid in chosen}
    library = list(state.players[seat].library)
    state = submit(client, mid, seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    assert state.players[seat].library == library + list(reversed(chosen))
    assert all(state.cards[cid].zone == Zone.LIBRARY and
               state.cards[cid].zone_change_sequence == refs[cid]+1 for cid in chosen)
    assert not state.pending_mechanic_choice and state.cards[source].zone == Zone.GRAVEYARD
    private_cards(restore(mid), seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['duplicate', 'short', 'foreign', 'wrong-seat'])
def test_pending_invalid_selection_full_root_and_sql_atomic(game, seat, bad):
    client, mid, _, foreign = ordinary(game, seat)
    ids = current(mid).state.players[seat].hand[:2]
    if bad == 'duplicate': ids = [ids[0], ids[0]]
    if bad == 'short': ids = ids[:1]
    if bad == 'foreign': ids = [ids[0], foreign]
    actor = 3-seat if bad == 'wrong-seat' else seat
    before = snapshot(current(mid))
    response = request(client, mid, actor, {'type': 'choose_mechanic', 'card_ids': ids})
    assert response.status_code == 422, response.text
    assert snapshot(current(mid)) == before
    restore(mid)
    assert snapshot(current(mid)) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_exact_order_retry_receipt_restores_and_conflict_is_atomic(game, seat):
    client, mid, _, _ = ordinary(game, seat)
    chosen = list(reversed(current(mid).state.players[seat].hand[:2]))
    action = {'type': 'choose_mechanic', 'card_ids': chosen}
    headers = {'Idempotency-Key': f'brainstorm-order-{seat}',
               'X-Match-Revision': str(current(mid).revision)}
    submit(client, mid, seat, action, headers)
    before = snapshot(current(mid))
    restore(mid)
    response = request(client, mid, seat, action, headers)
    assert response.status_code == 200, response.text
    assert snapshot(current(mid)) == before
    response = request(client, mid, seat,
                       {'type': 'choose_mechanic', 'card_ids': list(reversed(chosen))}, headers)
    assert response.status_code == 409 and response.json()['detail']['code'] == 'idempotency_conflict'
    assert snapshot(current(mid)) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reenter', [False, True])
def test_real_paid_return_library_trip_old_channel_private_and_reentry(game, seat, reenter):
    client, controller = game
    state, source, _, spells = causal.setup(seat, 'sniper')
    first = brain.add(state, 'Brainstorm', seat, Zone.HAND)
    second = brain.add(state, 'Brainstorm', seat, Zone.HAND)
    mid = install_position(controller, state)
    pool = deepcopy(state.players[seat].mana_pool)
    state = submit(client, mid, seat, {'type': 'activate_ability', 'card_id': source,
                                    'ability_index': 0, 'targets': {'target_player': 3-seat}})
    assert state.players[seat].mana_pool != pool and state.cards[source].zone == Zone.GRAVEYARD
    assert sum(pool.values())-sum(state.players[seat].mana_pool.values()) == 2
    assert state.players[seat].mana_pool['R'] == pool['R']-1
    channel = next(item.id for item in state.stack if item.source_card_id == source)
    retained = deepcopy(asdict(next(item for item in state.stack if item.id == channel)))
    frame = cast(client, mid, seat, spells['Zombify'], {'target_card_id': source})
    state = advance(client, mid, lambda s: all(item.id != frame for item in s.stack))
    assert state.cards[source].zone == Zone.BATTLEFIELD and state.stack[-1].id == channel
    frame = cast(client, mid, seat, spells['Unsummon'], {'target_card_id': source})
    state = advance(client, mid, lambda s: all(item.id != frame for item in s.stack))
    assert state.cards[source].zone == Zone.HAND and state.stack[-1].id == channel
    assert remembered_hand_card(state, 3-seat, state.cards[source]).name == causal.ROWS['Twinshot Sniper']['name']
    state = pending_brainstorm(client, mid, seat, first)
    other = next(cid for cid in state.players[seat].hand if cid not in {source, second})
    source_seq = state.cards[source].zone_change_sequence
    state = submit(client, mid, seat, {'type': 'choose_mechanic', 'card_ids': [source, other]})
    state = restore(mid)
    assert state.players[seat].library[-1] == source
    assert state.cards[source].zone == Zone.LIBRARY and state.cards[source].zone_change_sequence == source_seq+1
    assert source not in public_card_ids(state)
    assert remembered_hand_card(state, 3-seat, state.cards[source]) is None
    assert asdict(next(item for item in state.stack if item.id == channel)) == retained
    before = serialize_match_snapshot(state)
    for viewer in (seat, 3-seat):
        view, _ = decision_view(state, viewer, [])
        assert is_unknown(view.cards[source])
        assert all(is_unknown(view.cards[cid]) for player in state.players.values() for cid in player.library)
        assert asdict(next(item for item in view.stack if item.id == channel)) == retained
    # Information-flow counterfactual following a real hidden-zone trip, not a lawful print change.
    probe = deepcopy(state)
    probe.cards[source].name = 'Unobserved hidden identity'
    probe.cards[source].oracle_text = 'Unobserved private text'
    for player in probe.players.values():
        player.library.reverse()
    projected, _ = decision_view(causal.reload_exact(probe), 3-seat, [])
    assert is_unknown(projected.cards[source]) and projected.cards[source].name == ''
    assert serialize_match_snapshot(state) == before
    if reenter:
        state = pending_brainstorm(client, mid, seat, second)
        assert state.cards[source].zone == Zone.HAND
        assert remembered_hand_card(state, 3-seat, state.cards[source]) is None
        private_cards(state, seat)
        others = [cid for cid in state.players[seat].hand if cid != source][:2]
        assert len(others) == 2
        state = submit(client, mid, seat, {'type': 'choose_mechanic', 'card_ids': others})
        frame = cast(client, mid, seat, source)
        state = advance(client, mid, lambda s: all(item.id != frame for item in s.stack))
        assert state.cards[source].zone == Zone.BATTLEFIELD and source in public_card_ids(state)
        assert asdict(next(item for item in state.stack if item.id == channel)) == retained
    state = advance(client, mid, lambda s: all(item.id != channel for item in s.stack))
    assert state.players[3-seat].life == 18
    restore(mid)


@pytest.mark.parametrize('seat', [1, 2])
def test_strict_public_pending_context_diagnostic(game, seat):
    client, mid, source, _ = ordinary(game, seat)
    state = current(mid).state
    before = snapshot(current(mid))
    response = client.get(f'/matches/{mid}')
    assert response.status_code == 200, response.text
    exported = response.json()['pending_mechanic_choice']
    legal = moves(client, mid, seat)[0]
    private, _ = decision_view(state, 3-seat, [])
    # Search exact string values, not substrings or a fabricated private payload.
    def strings(value):
        if isinstance(value, str):
            return {value}
        if isinstance(value, dict):
            return set().union(*(strings(v) for v in value.values())) if value else set()
        if isinstance(value, list):
            return set().union(*(strings(v) for v in value)) if value else set()
        return set()
    values = strings(exported)
    hidden_identity_hits = {cid: state.cards[cid].name for cid in state.cards
                            if is_unknown(private.cards[cid]) and state.cards[cid].name in values}
    internal_keys = sorted(set(exported) & {'effect_payload', 'resolving_item'})
    evidence = {'seat': seat, 'source': source, 'source_zone': state.cards[source].zone.value,
                'exported_pending': exported, 'raw_pending': state.pending_mechanic_choice,
                'declared_legal_choice': legal, 'internal_context_keys': internal_keys,
                'undisclosed_identity_exact_value_hits': hidden_identity_hits,
                'scope': 'Strict exported-context diagnostic; HH hands are intentionally visible. '
                         'Internal public spell context alone is NOT a hidden-identity leak.'}
    directory = os.environ.get('MTG_BRAINSTORM_MIXED_EVIDENCE')
    if directory:
        with (Path(directory)/f'public-pending-context-seat{seat}.json').open('x') as out:
            json.dump(evidence, out, indent=2)
    assert snapshot(current(mid)) == before
    assert not hidden_identity_hits, evidence
    assert not internal_keys, evidence
