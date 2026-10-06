"""Resolver ABI tests, not certification of a targeted card's compiler.

The retained context is captured from an actual paid Rampant Growth. Retargeting
that resolver packet below is an explicit unit-level ownership exercise, not a
claim that Rampant Growth's printed instruction targets another player.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from effects.handlers import search_library
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_linked_damage_targets import raw_card


FIXTURES = Path(__file__).parent / 'fixtures/targeted_search_resolver'
PROVENANCE = json.loads((FIXTURES / 'provenance.json').read_text())
for row in PROVENANCE['cards']:
    assert hashlib.sha256((FIXTURES / row['file']).read_bytes()).hexdigest() == row['sha256']


def raw(name):
    return json.loads((FIXTURES / (name + '.json')).read_text())


def snap(state):
    return json.loads(json.dumps(serialize_match_snapshot(state)))


def restore(state):
    before = snap(state)
    restored = deserialize_match_snapshot(before)
    assert snap(restored) == before
    return restored


def position(seat):
    row = raw('forest')
    deck = [{**row, 'card_name': row['name'], 'quantity': 16}]
    state = MatchFactory.from_decks(deck, deck, seed=60217)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    card = raw_card(state, raw('rampant-growth'), seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 2}
    before = snap(state)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': card.id, 'targets': {}})
    assert before['players'][str(seat)]['mana_pool'] == {'G': 2}
    assert state.players[seat].mana_pool['G'] == 0
    item = state.stack.pop()
    frame = asdict(item)
    payload = {**item.payload, '__resolving_item': frame}
    assert frame['source_card_id'] == card.id and frame['controller'] == seat
    return state, payload


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('targeted', [False, True])
@pytest.mark.parametrize('find', [False, True])
def test_deliberate_owner_choice_empty_shuffle_context_and_restart(seat, targeted, find, monkeypatch):
    state, payload = position(seat)
    owner = 3-seat if targeted else seat
    if targeted:
        payload['target_player'] = owner
    untouched = list(state.players[3-owner].library)
    seen = []
    import rules_engine.events as events
    emit = events.emit_event

    def spy(current, event, data):
        if event == 'shuffle':
            seen.append(deepcopy(data))
        return emit(current, event, data)

    monkeypatch.setattr(events, 'emit_event', spy)
    search_library(state, seat, payload)
    pending = state.pending_mechanic_choice
    assert pending['player_id'] == owner and pending['min_count'] == 0
    assert pending['continuation_controller'] == seat
    assert pending['resolving_item'] == payload['__resolving_item']
    chosen = pending['options'][-1]
    assert chosen in state.players[owner].library
    assert not RulesEngine().legal_moves(state, 3-owner)
    state = restore(state)
    before = snap(state)
    action = {'type': 'choose_mechanic', 'card_ids': [chosen] if find else []}
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-owner, action)
    assert snap(state) == before
    result = checked_action(state, RulesEngine(), owner, action)
    assert snap(state) == before
    assert len(seen) == 1 and seen[0]['player_id'] == owner
    assert seen[0]['cause']['controller'] == seat
    assert seen[0]['cause']['stack_id'] == payload['__resolving_item']['id']
    assert result.players[3-owner].library == untouched
    assert bool(chosen in result.players[owner].battlefield) == find
    if find:
        assert result.cards[chosen].controller == result.cards[chosen].owner == owner
        assert result.cards[chosen].zone == Zone.BATTLEFIELD and result.cards[chosen].tapped
    else:
        assert chosen in result.players[owner].library
    assert result.cards[payload['__resolving_item']['source_card_id']].zone == Zone.GRAVEYARD
    restore(result)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('empty', [False, True])
def test_no_eligible_card_still_shuffles_once(seat, empty, monkeypatch):
    state, payload = position(seat)
    owner = 3-seat
    payload['target_player'] = owner
    for cid in list(state.players[owner].library):
        state.players[owner].library.remove(cid)
        state.cards[cid].move_to_zone(Zone.HAND)
        state.players[owner].hand.append(cid)
    if not empty:
        raw_card(state, raw('fertilid'), owner, Zone.LIBRARY)
    before = list(state.players[owner].library)
    seen = []
    import rules_engine.events as events
    emit = events.emit_event

    def spy(current, event, data):
        if event == 'shuffle':
            seen.append(deepcopy(data))
        return emit(current, event, data)

    monkeypatch.setattr(events, 'emit_event', spy)
    search_library(state, seat, payload)
    assert state.pending_mechanic_choice is None
    assert len(seen) == 1 and seen[0]['player_id'] == owner
    assert seen[0]['cause']['controller'] == seat
    assert state.players[owner].library == before
    restore(state)


@pytest.mark.parametrize('bad', [None, True, '2', 2.0, 0, 3, [], {}])
def test_invalid_target_rejected_before_mutation(bad):
    state, payload = position(1)
    before = snap(state)
    with pytest.raises(ValueError):
        search_library(state, 1, {**payload, 'target_player': bad})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['foreign', 'duplicate', 'stale_incarnation', 'too_many'])
def test_selected_card_validation_is_atomic(seat, bad):
    state, payload = position(seat)
    owner = 3-seat
    search_library(state, seat, {**payload, 'target_player': owner})
    pending = state.pending_mechanic_choice
    chosen = pending['options'][0]
    ids = [chosen]
    if bad == 'foreign':
        ids = [state.players[seat].library[0]]
    elif bad == 'duplicate':
        ids *= 2
    elif bad == 'too_many':
        ids = pending['options'][:2]
    else:
        state.cards[chosen].zone_change_sequence += 2
    before = snap(state)
    with pytest.raises(ValueError):
        search_library(state, owner, {**pending['effect_payload'], 'selected_card_ids': ids})
    assert snap(state) == before


def test_targeted_missing_frame_is_atomic_not_a_fabricated_shuffle_cause():
    state, payload = position(1)
    del payload['__resolving_item']
    before = snap(state)
    with pytest.raises(ValueError, match='genuine resolving item'):
        search_library(state, 1, {**payload, 'target_player': 2})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pay', [False, True])
def test_entry_pause_and_suffix_keep_original_controller(seat, pay):
    from effects.registry import resolve_effect
    state, payload = position(seat)
    owner = 3-seat
    card = raw_card(state, raw('breeding-pool'), owner, Zone.LIBRARY)
    payload.update(target_player=owner, contains='land', selected_card_ids=[card.id])
    life = {pid: player.life for pid, player in state.players.items()}
    resolve_effect(state, seat, 'effect_sequence', {'__resolving_item': payload['__resolving_item'],
        'effects': [{'effect_key': 'search_library', 'payload': payload},
                    {'effect_key': 'gain_life', 'payload': {'amount': 3}}]})
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'land_entry' and pending['player_id'] == owner
    assert pending['continuation_controller'] == seat
    assert card.id in state.players[owner].library
    state = restore(state)
    result = checked_action(state, RulesEngine(), owner, {
        'type': 'choose_mechanic', 'choice_id': 'pay_two_life' if pay else 'tapped'})
    assert result.players[owner].life == life[owner] - 2 * pay
    assert result.players[seat].life == life[seat] + 3
    assert result.cards[card.id].tapped and result.cards[card.id].controller == owner
    assert result.players[owner].battlefield.count(card.id) == 1
    assert sum('shuffles their library' in line for line in result.log) == 1
    restore(result)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_optional_search_prompt_owner_decline_and_continue(seat, accept):
    state, payload = position(seat)
    owner = 3-seat
    search_library(state, seat, {**payload, 'target_player': owner, 'optional': True})
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'optional_search' and pending['player_id'] == owner
    assert pending['continuation_controller'] == seat
    state = checked_action(restore(state), RulesEngine(), owner,
                           {'type': 'choose_mechanic', 'card_ids': ['search' if accept else 'decline']})
    if accept:
        assert state.pending_mechanic_choice['kind'] == 'search_library'
        assert state.pending_mechanic_choice['continuation_controller'] == seat
        state = checked_action(restore(state), RulesEngine(), owner,
                               {'type': 'choose_mechanic', 'card_ids': []})
    else:
        assert state.pending_mechanic_choice is None
    assert sum('shuffles their library' in line for line in state.log) == int(accept)
    restore(state)
