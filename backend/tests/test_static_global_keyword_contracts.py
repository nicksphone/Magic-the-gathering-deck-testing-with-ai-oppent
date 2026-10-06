"""Ordinary strict contracts; static-global failures are not release PASS."""
import pickle

import pytest

from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.attachments import attach_if_legal
from rules_engine.combat import _can_block_attacker
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.state_based_actions import apply_state_based_actions
from tests.static_global_keyword_support import FAMILIES, add, board, cast, zone_seam
from tests.test_api_input_contracts import game, persist, snapshot
from tests.test_selected_mana_http import restart
import main


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_paid_source_grants_both_players_and_late_creatures_after_restore(seat, name, color):
    state, source, targets = board(seat, name)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    late = [add(state, 'Grizzly Bears', owner).id for owner in (1, 2)]
    assert all(has_keyword(state, cid, 'protection from '+color) for cid in targets+late)
    assert not has_keyword(state, source, 'protection from '+color)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
@pytest.mark.parametrize('owner', [1, 2])
def test_paid_matching_spell_rejected_atomically_for_either_controller(seat, name, color, owner):
    state, _, targets = board(seat, name)
    spell = add(state, 'Lightning Bolt' if color == 'red' else 'Doom Blade', seat, Zone.HAND)
    state.priority_player = seat
    state.players[seat].mana_pool = dict.fromkeys(('R', 'B', 'C'), 10)
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id,
                       'targets': {'target_card_id': targets[owner-1]}})
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_damage_consumer_observes_global_grant(seat, name, color):
    state, _, targets = board(seat, name)
    enemy = add(state, 'Goblin Piker' if color == 'red' else 'Walking Corpse', 3-seat)
    # Existing damage primitive with an authentic source; not a claimed paid
    # untargeted spell, nor a protection-bypassing targeted cast.
    resolve_effect(state, 3-seat, 'deal_damage', {'target_card_id': targets[seat-1],
                   'amount': 1, '__source_card_id': enemy.id})
    assert state.cards[targets[seat-1]].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_block_consumer_observes_global_grant(seat, name, color):
    state, _, targets = board(seat, name)
    enemy = add(state, 'Goblin Piker' if color == 'red' else 'Walking Corpse', 3-seat)
    assert not _can_block_attacker(state, state.cards[targets[seat-1]], enemy)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_checked_block_rejects_matching_quality_without_mutation(seat, name, color):
    state, _, targets = board(seat, name)
    blocker = add(state, 'Goblin Piker' if color == 'red' else 'Walking Corpse', 3-seat)
    attacker = targets[seat-1]
    state.step = Step.DECLARE_BLOCKERS
    state.active_player = seat
    state.priority_player = 3-seat
    state.attackers = {attacker: f'player:{3-seat}'}
    state.attackers_declared = True
    state.blockers_declared = False
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {attacker: [blocker.id]}})
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_matching_aura_rejected_and_old_attachment_removed_at_sba(seat, name, color):
    state, source, targets = board(seat, name, resolve_source=False)
    zone_seam(state, source, Zone.HAND)
    aura = add(state, 'Firebreathing' if color == 'red' else 'Unholy Strength', seat)
    assert attach_if_legal(state, aura.id, targets[seat-1])
    zone_seam(state, source, Zone.BATTLEFIELD)
    apply_state_based_actions(state)
    assert state.cards[aura.id].zone == Zone.GRAVEYARD
    fresh = add(state, aura.name, seat)
    assert not attach_if_legal(state, fresh.id, targets[seat-1])


@pytest.mark.parametrize('seat', [1, 2])
def test_black_equipment_cannot_equip_but_colorless_can(seat):
    state, _, targets = board(seat, 'Absolute Grace')
    black = add(state, 'Vorpal Sword', seat)
    neutral = add(state, 'Bonesplitter', seat)
    assert attach_if_legal(state, neutral.id, targets[seat-1])
    assert not attach_if_legal(state, black.id, targets[seat-1])


@pytest.mark.parametrize('seat', [1, 2])
def test_checked_black_equip_rejected_atomically(seat):
    state, _, targets = board(seat, 'Absolute Grace')
    sword = add(state, 'Vorpal Sword', seat)
    state.players[seat].mana_pool = {'B': 2}
    state.priority_player = seat
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'equip', 'card_id': sword.id,
                       'target_card_id': targets[seat-1]})
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_black_equipment_unattaches_but_stays_on_battlefield(seat):
    state, source, targets = board(seat, 'Absolute Grace', resolve_source=False)
    zone_seam(state, source, Zone.HAND)
    sword = add(state, 'Vorpal Sword', seat)
    assert attach_if_legal(state, sword.id, targets[seat-1])
    zone_seam(state, source, Zone.BATTLEFIELD)
    apply_state_based_actions(state)
    assert sword.attached_to is None
    assert sword.zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_checked_matching_aura_rejected_before_payment(seat, name, color):
    state, _, targets = board(seat, name)
    aura = add(state, 'Firebreathing' if color == 'red' else 'Unholy Strength', seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1, 'B': 1}
    state.priority_player = seat
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': aura.id,
                       'targets': {'target_card_id': targets[seat-1]}})
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_static_grant_follows_actual_phase_entry_and_cleanup_without_new_stamp(seat, name, color):
    state, source, targets = board(seat, name)
    stamp = state.cards[source].effect_timestamp
    engine = RulesEngine()
    seen = set()
    for _ in range(len(Step)+4):
        seen.add(state.step)
        assert state.cards[source].effect_timestamp == stamp
        assert all(has_keyword(state, cid, 'protection from '+color) for cid in targets)
        if state.step == Step.CLEANUP:
            break
        engine.next_step(state)
    assert Step.CLEANUP in seen


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_paid_source_departure_and_controlled_reentry_recompute(seat, name, color):
    state, source, targets = board(seat, name)
    state, _ = cast(state, 'Disenchant', seat, {'target_card_id': source})
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert all(not has_keyword(state, cid, 'protection from '+color) for cid in targets)
    zone_seam(state, source, Zone.BATTLEFIELD)
    assert all(has_keyword(state, cid, 'protection from '+color) for cid in targets)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_real_ovinize_later_loss_cleanup_and_reentered_source_timestamp(seat, name, color):
    state, source, targets = board(seat, name)
    target = targets[seat-1]
    stamp = state.cards[source].effect_timestamp
    state, _ = cast(state, 'Ovinize', seat, {'target_card_id': target})
    assert not has_keyword(state, target, 'protection from '+color)
    assert state.cards[target].keyword_effects
    assert min(e['timestamp'] for e in state.cards[target].keyword_effects) > stamp
    zone_seam(state, source, Zone.HAND)
    zone_seam(state, source, Zone.BATTLEFIELD)
    assert has_keyword(state, target, 'protection from '+color)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine()._finish_cleanup(state)
    assert has_keyword(state, target, 'protection from '+color)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', FAMILIES)
def test_actual_http_source_restore_then_matching_target_atomic_rejection(game, seat, name, color):
    client, controller = game
    state, source, targets = board(seat, name)
    spell = add(state, 'Lightning Bolt' if color == 'red' else 'Doom Blade', seat, Zone.HAND)
    state.players[seat].mana_pool = dict.fromkeys(('R', 'B', 'C'), 10)
    state.priority_player = seat
    state.id = controller.state.id
    controller.state = state
    controller.controllers = {1: 'human', 2: 'human'}
    persist(controller)
    controller = restart(state.id)
    before = snapshot(controller)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat,
                           'action': {'type': 'cast_spell', 'card_id': spell.id,
                                      'targets': {'target_card_id': targets[3-seat-1]}}})
    assert response.status_code in (403, 422), response.text
    assert snapshot(controller) == before
