"""Canonical group keyword grants: object membership, layers and real casts."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.extra_sequence_support import position
from tests.test_linked_damage_targets import raw_card
from tests.test_api_input_contracts import game, persist
from tests.test_selected_mana_http import restart
import main

FIXTURES = Path(__file__).parent / 'fixtures/permanent_keyword_grants'
SEED = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_text())['cards']
PERMANENTS = ('Island', 'Torrential Gearhulk', "Witch's Oven", 'Up the Beanstalk', 'Ugin, the Spirit Dragon')


def board(seat, name):
    state = position(seat)
    allies = [raw_card(state, SEED[n], seat, Zone.BATTLEFIELD).id for n in PERMANENTS]
    enemies = [raw_card(state, SEED[n], 3-seat, Zone.BATTLEFIELD).id for n in PERMANENTS]
    raw = json.loads((FIXTURES / ('boros-charm.json' if name == 'Boros Charm' else 'heroic-intervention.json')).read_text())
    source = raw_card(state, raw, seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1, 'W': 1, 'G': 1, 'C': 1}
    targets = {} if name == 'Heroic Intervention' else {
        'mode_text': raw['oracle_text'].splitlines()[2].removeprefix(chr(8226) + ' ').rstrip('.')}
    return state, source.id, allies, enemies, targets


def granted(seat, name):
    state, source, allies, enemies, targets = board(seat, name)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source, 'targets': targets})
    while state.stack:
        assert resolve_top_of_stack(state)
    assert state.cards[source].zone == Zone.GRAVEYARD
    return state, source, allies, enemies


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Boros Charm', 'Heroic Intervention'])
def test_canonical_group_grants_apply_to_all_current_permanent_types_and_survive_restore(seat, name):
    state, source, allies, enemies = granted(seat, name)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    stamps = set()
    for cid in allies:
        assert has_keyword(state, cid, 'indestructible')
        assert has_keyword(state, cid, 'hexproof') == (name == 'Heroic Intervention')
        stamps.update(effect['timestamp'] for effect in state.cards[cid].keyword_effects)
        assert all(effect['source_card_id'] == source for effect in state.cards[cid].keyword_effects)
        resolve_effect(state, 3-seat, 'destroy_permanent', {'target_card_id': cid})
        assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert len(stamps) == 1
    assert all(not has_keyword(state, cid, 'indestructible') for cid in enemies)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Boros Charm', 'Heroic Intervention'])
def test_group_recipient_set_does_not_follow_new_objects_and_expires_at_cleanup(seat, name):
    state, _, allies, _ = granted(seat, name)
    late = raw_card(state, SEED['Torrential Gearhulk'], seat, Zone.BATTLEFIELD)
    assert not has_keyword(state, late.id, 'indestructible')
    cid = allies[0]
    state.players[seat].battlefield.remove(cid)
    state.cards[cid].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(cid)
    state.players[seat].exile.remove(cid)
    state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(cid)
    assert not has_keyword(state, cid, 'indestructible')
    RulesEngine()._finish_cleanup(state)
    assert all(not has_keyword(state, target, 'indestructible') for target in allies)


@pytest.mark.parametrize('seat', [1, 2])
def test_heroic_intervention_hexproof_rejects_real_opponent_spell_without_costs(seat):
    state, _, allies, _ = granted(seat, 'Heroic Intervention')
    bolt = raw_card(state, SEED['Lightning Bolt'], 3-seat, Zone.HAND)
    state.priority_player = 3-seat
    state.players[3-seat].mana_pool = {'R': 1}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat,
                       {'type': 'cast_spell', 'card_id': bolt.id, 'targets': {'target_card_id': allies[1]}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_later_layer_six_loss_overrides_then_later_grant_restores_keyword(seat):
    state, _, allies, _ = granted(seat, 'Boros Charm')
    target = allies[1]
    resolve_effect(state, seat, 'grant_keyword', {'target_card_id': target, 'keyword': 'indestructible',
                                               'operation': 'remove', 'until_end_of_turn': True})
    assert not has_keyword(state, target, 'indestructible')
    resolve_effect(state, seat, 'grant_keyword', {'target_card_id': target, 'keyword': 'indestructible',
                                               'until_end_of_turn': True})
    assert has_keyword(state, target, 'indestructible')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Boros Charm', 'Heroic Intervention'])
def test_real_http_group_grant_and_durable_keyword_restore(game, seat, name):
    client, controller = game
    state, source, allies, enemies, targets = board(seat, name)
    state.id = controller.state.id
    controller.state = state
    controller.controllers = {1: 'human', 2: 'human'}
    persist(controller)
    def post(player, action, label):
        current = main.ACTIVE_MATCHES[state.id]
        response = client.post(f'/matches/{state.id}/action',
                               json={'player_id': player, 'action': action},
                               headers={'Idempotency-Key': label, 'X-Match-Revision': str(current.revision)})
        assert response.status_code == 200, response.text
    post(seat, {'type': 'cast_spell', 'card_id': source, 'targets': targets}, 'grant-cast')
    restart(state.id)
    while main.ACTIVE_MATCHES[state.id].state.stack:
        player = main.ACTIVE_MATCHES[state.id].state.priority_player
        current = main.ACTIVE_MATCHES[state.id]
        post(player, {'type': 'pass_priority'}, f'grant-pass-{current.revision}')
    restored = restart(state.id).state
    assert restored.cards[source].zone == Zone.GRAVEYARD
    assert all(has_keyword(restored, cid, 'indestructible') for cid in allies)
    assert all(not has_keyword(restored, cid, 'indestructible') for cid in enemies)
    assert all(has_keyword(restored, cid, 'hexproof') == (name == 'Heroic Intervention') for cid in allies)
