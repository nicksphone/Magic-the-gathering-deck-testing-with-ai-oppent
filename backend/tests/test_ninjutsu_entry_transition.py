"""Canonical S1 transition controls; departure is explicitly controlled setup."""
import pytest

from card_data.fallback_cards import fallback_card_payload
from game_state.state import CardInstance, Zone
from training.environment import TrainingEnvironment
from tests.test_linked_damage_targets import raw_card
from tests.test_ninjutsu_source_identity import relocate
from tests.test_training_environment import resolve
from tests.test_training_ninjutsu_intent_audit import scenario


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('movement', ['valid', 'reentered'])
def test_entry_uses_shared_transition_once_and_stale_guard_never_enters(monkeypatch, seat, movement):
    env, action, _, info = scenario(seat)
    env.step(action)
    source = env._state.cards[info['ninja']]
    initial = source.zone_change_sequence
    if movement == 'reentered':
        relocate(env._state, source.id, Zone.EXILE)
        relocate(env._state, source.id, Zone.HAND)
    before_resolution = env._state.cards[source.id].zone_change_sequence
    calls = []
    actual_move = CardInstance.move_to_zone

    def observed_move(card, destination):
        before = card.zone_change_sequence
        actual_move(card, destination)
        if card.id == source.id and destination == Zone.BATTLEFIELD:
            calls.append((before, card.zone_change_sequence))

    monkeypatch.setattr(CardInstance, 'move_to_zone', observed_move)
    resolve(env)
    result = env._state.cards[source.id]
    if movement == 'valid':
        assert calls == [(initial, initial + 1)]
        assert result.zone == Zone.BATTLEFIELD and result.tapped
        assert result.zone_change_sequence == initial + 1
        assert source.id in env._state.attackers
    else:
        assert calls == []
        assert result.zone == Zone.HAND and source.id not in env._state.attackers
        assert result.zone_change_sequence == before_resolution
    assert info['attackers'][1] in env._state.players[seat].hand
    assert all(env._state.cards[cid].tapped for cid in info['lands'])
    assert sum(env._state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_two_actual_pending_activations_do_not_follow_entered_then_returned_source(seat):
    env, first, _, info = scenario(seat)
    extra = [raw_card(env._state, fallback_card_payload('Island'), seat, Zone.BATTLEFIELD).id
             for _ in range(2)]
    initial = env._state.cards[info['ninja']].zone_change_sequence
    env.step(first)
    env.step({**first, 'return_card_id': info['attackers'][0]})
    assert len(env._state.stack) == 2
    assert all(item.effect_key == 'ninjutsu' and
               item.payload['__source_zone_sequence'] == initial for item in env._state.stack)
    assert all(cid in env._state.players[seat].hand for cid in info['attackers'])
    resolve(env)
    source = env._state.cards[info['ninja']]
    assert source.zone == Zone.BATTLEFIELD and source.zone_change_sequence == initial + 1
    assert len(env._state.stack) == 1
    relocate(env._state, source.id, Zone.HAND)
    env._state.attackers.remove(source.id)
    env._state.attack_targets.pop(source.id, None)
    assert env._state.cards[source.id].zone_change_sequence == initial + 2
    restored = TrainingEnvironment()
    restored.restore(env.snapshot())
    resolve(env)
    resolve(restored)
    assert env.snapshot() == restored.snapshot()
    assert env._state.cards[source.id].zone == Zone.HAND
    assert env._state.cards[source.id].zone_change_sequence == initial + 2
    assert source.id not in env._state.attackers and not env._state.stack
    assert all(env._state.cards[cid].tapped for cid in [*info['lands'], *extra])
    assert all(cid in env._state.players[seat].hand for cid in info['attackers'])
    assert sum(env._state.players[seat].mana_pool.values()) == 0
