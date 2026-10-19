"""Manual/bulk completion; existing canonical projection, no new RAW intake."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from tests.test_forge_human_replacement_order import act, choose, finish_stack, fingerprint, setup
from tests.test_linked_mana_damage import request


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['native', 'bulk'])
def test_offturn_completion_returns_the_original_actor_priority(seat, route):
    state, sources, _, _ = setup(seat)
    state.active_player = 3-seat
    result = act(state, seat, request(state.cards[sources[0]], 'W', route))
    assert result.pending_replacement_choice
    result = choose(deserialize_match_snapshot(serialize_match_snapshot(result)),
                    seat, result.numeric_prevention_shields[0].receipt_id)
    assert result.priority_player == seat
    assert not result.mana_continuation and not result.pending_replacement_choice
    assert result.players[seat].mana_pool['W'] == 1


def with_growth(seat, monkeypatch, *, furnaces=0):
    path = Path(__file__).parent/'fixtures/additive_mana.json'
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == '007c02feda85d778b3114e4e349ae1cad771b8436897c900975149623e7216b3'
    row = next(row for row in json.loads(data) if row['name'] == 'Wild Growth')
    assert row['oracle_text'] == (
        'Enchant land\nWhenever enchanted land is tapped for mana, '
        'its controller adds an additional {G}.')
    normalized = ScryfallSyncService._normalize_payload(row, '/card-images/foundation-growth.jpg')
    entry = {**row, **normalized, 'card_name': row['name'], 'quantity': 1,
             'card_faces': json.loads(normalized['card_faces_json']), 'colors': row['colors']}
    extra = [entry]
    if furnaces:
        path = Path(__file__).parent/'fixtures/linked_damage/furnace-of-rath.json'
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == '4a2feca3b6b9bb2da4e59bc5172b94c84505d74ffcb64598f697b9570143252a'
        raw = json.loads(data)
        assert raw['object'] == 'card' and raw['name'] == 'Furnace of Rath'
        from tests.test_forge_human_replacement_order import card_entry
        extra.append(card_entry(raw, furnaces))
    original_factory = MatchFactory.from_decks

    def born_with_growth(a, b, **kwargs):
        return original_factory([*a, *deepcopy(extra)], [*b, *deepcopy(extra)], **kwargs)

    # Add the complete committed printed projection BEFORE the real Factory capture.
    with monkeypatch.context() as birth:
        birth.setattr(MatchFactory, 'from_decks', staticmethod(born_with_growth))
        state, sources, _, _ = setup(seat)
    growth = next(card for card in state.cards.values()
                  if card.owner == seat and card.name == row['name'])
    player = state.players[seat]
    getattr(player, growth.zone.value).remove(growth.id)
    growth.move_to_zone(Zone.HAND)
    player.hand.append(growth.id)
    player.mana_pool['G'] = 1
    state = act(state, seat, {'type': 'cast_spell', 'card_id': growth.id,
                'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': sources[0]}})
    state = finish_stack(state)
    assert state.cards[growth.id].attached_to == sources[0]
    assert state.cards[growth.id].zone == Zone.BATTLEFIELD
    assert state.players[seat].mana_pool['G'] == 0
    return state, sources, growth.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['native', 'bulk'])
def test_genuine_tap_bonus_finishes_once_before_the_owner_sba(seat, route, monkeypatch):
    state, sources, growth = with_growth(seat, monkeypatch)
    from rules_engine import state_based_actions
    original_sba = state_based_actions.apply_state_based_actions
    observations = []

    def observe(candidate):
        observations.append((candidate, candidate.players[seat].mana_pool['G'],
                             bool(candidate.pending_replacement_choice)))
        return original_sba(candidate)

    monkeypatch.setattr(state_based_actions, 'apply_state_based_actions', observe)
    paused = act(state, seat, request(state.cards[sources[0]], 'W', route))
    assert paused.players[seat].mana_pool['G'] == 0
    assert not [row for row in observations if row[0] is paused]
    captured = paused.mana_continuation['frames'][-1]['captured_bonus']
    assert len(captured) == 1 and captured[0][1] == growth and captured[0][4] == {'G': 1}
    for viewer in [1, 2]:
        public = serialize_match(paused, look_players={viewer})
        assert 'mana_continuation' not in public
    paused = deserialize_match_snapshot(json.loads(json.dumps(serialize_match_snapshot(paused))))
    result = choose(paused, seat, paused.numeric_prevention_shields[0].receipt_id)
    assert result.players[seat].mana_pool['W'] == result.players[seat].mana_pool['G'] == 1
    assert not result.mana_continuation and not result.pending_replacement_choice
    committed = [(green, pending) for candidate, green, pending in observations if candidate is result]
    assert committed == [(1, False)], 'one completed activation has one post-bonus SBA boundary'


@pytest.mark.parametrize('mutation', [
    'cursor', 'source_reference', 'ability_bool', 'color', 'row_extra', 'return_priority',
    'extra_owner',
])
def test_bulk_snapshot_rejects_roster_or_completion_rebinding(mutation):
    state, sources, _, _ = setup(1)
    result = act(state, 1, {**request(state.cards[sources[0]], 'W', 'bulk'), 'count': 2})
    snapshot = deepcopy(serialize_match_snapshot(result))
    owner = snapshot['mana_continuation']['frames'][0]['data']
    if mutation == 'cursor':
        owner['cursor'] = 1
    elif mutation == 'source_reference':
        owner['roster'][0]['source']['incarnation'] += 1
    elif mutation == 'ability_bool':
        owner['roster'][0]['ability_index'] = True
    elif mutation == 'color':
        owner['roster'][0]['color'] = 'C'
    elif mutation == 'row_extra':
        owner['roster'][0]['ignored'] = True
    elif mutation == 'extra_owner':
        frames = snapshot['mana_continuation']['frames']
        frames.insert(0, deepcopy(frames[0]))
        snapshot['mana_continuation']['waiting']['frame_index'] += 1
    else:
        owner['return_priority'] = 2
    before = fingerprint(result)
    with pytest.raises((ValueError, ActionRejected)):
        deserialize_match_snapshot(snapshot)
    assert fingerprint(result) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_damage_chain_lifelink_and_bonus_finish_before_lethal_sba(seat, monkeypatch):
    state, sources, _ = with_growth(seat, monkeypatch, furnaces=3)
    from game_state.state import assign_static_order_on_battlefield_entry
    furnaces = [card for card in state.cards.values()
                if card.owner == 3-seat and card.name == 'Furnace of Rath']
    assert len(furnaces) == 3
    for card in furnaces:
        player = state.players[card.owner]
        getattr(player, card.zone.value).remove(card.id)
        card.move_to_zone(Zone.BATTLEFIELD)
        player.battlefield.append(card.id)
        assign_static_order_on_battlefield_entry(state, card.id)
    # Explicit runtime effect pose, not a claim that printed Forge has lifelink.
    from effects.handlers import grant_keyword
    grant_keyword(state, seat, {'target_card_id': sources[0], 'keyword': 'lifelink',
                               '__source_card_id': sources[0]})
    state.players[seat].life = 1
    result = act(state, seat, request(state.cards[sources[0]], 'W'))
    for card in furnaces:
        assert result.pending_replacement_choice and result.winner is None
        assert card.id in {o['source_id'] for o in result.pending_replacement_choice['options']}
        result = deserialize_match_snapshot(json.loads(json.dumps(serialize_match_snapshot(result))))
        result = act(result, seat, {'type': 'choose_replacement', 'replacement_source_id': card.id})
    # Native damage is now8; the two real paid Salves absorb3 each, then2 is dealt.
    while result.pending_replacement_choice:
        options = result.pending_replacement_choice['options']
        selected = next(o['source_id'] for o in options if o['source_id'].startswith('numeric-prevention:'))
        result = act(result, seat, {'type': 'choose_replacement', 'replacement_source_id': selected})
    assert result.players[seat].life == 1 and result.winner is None
    assert result.players[seat].mana_pool['W'] == result.players[seat].mana_pool['G'] == 1
    assert not result.mana_continuation and not result.stack
    assert result.players[seat].prevent_damage_shield == 0
