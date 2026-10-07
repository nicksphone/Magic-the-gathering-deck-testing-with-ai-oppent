"""Paid canonical return with an old Channel pending; no compiler extension."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from ai.information import decision_view, is_unknown
from game_state.observations import public_card_ids, remembered_hand_card
from game_state.state import Zone
from tests import pending_source_privacy_support as original


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_public_return_pending_channel_uses_authorized_memory(seat):
    state, source, target, spells = original.setup(seat, 'sniper')
    state, channel, ref = original.announce(state, source, target, seat)
    state = original.reenter(state, seat, 'sniper', source, channel, spells)
    canonical = deepcopy(state.cards[source])
    assert canonical.zone == Zone.BATTLEFIELD and source in public_card_ids(state)
    state, response = original.cast(state, spells['Unsummon'], seat,
                                    {'target_card_id': source})
    paid = next(item for item in state.stack if item.id == response)
    assert paid.source_card_id == spells['Unsummon'] and paid.controller == seat
    assert paid.effect_key == 'return_permanent_to_hand'
    assert paid.payload['target_card_id'] == source and paid.payload['mana_spent'] == 1
    assert state.cards[spells['Unsummon']].oracle_text == original.ROWS['Unsummon']['oracle_text']
    state = original.until(state, lambda s: all(item.id != response for item in s.stack))
    state = original.reload_exact(state)
    card = state.cards[source]
    assert card.zone == Zone.HAND and source in state.players[seat].hand
    assert card.zone_change_sequence == canonical.zone_change_sequence + 1
    assert source not in public_card_ids(state)
    assert next(item for item in state.stack if item.id == channel).payload['__activation_source_reference'] == ref
    before = original.serialize_match_snapshot(state)
    frames = [asdict(item) for item in state.stack]
    for viewer in (1, 2):
        record = state.card_observations[viewer][source]
        assert record['zone'] == Zone.HAND.value
        assert record['zone_change_sequence'] == card.zone_change_sequence
        for key in ('id', 'owner', 'name', 'oracle_text'):
            assert record[key] == getattr(canonical, key)
        assert remembered_hand_card(state, viewer, card) is not None
        view, _ = decision_view(state, viewer, [])
        assert [asdict(item) for item in view.stack] == frames
        assert view.cards[source].name == canonical.name
        for player in state.players.values():
            assert all(is_unknown(view.cards[cid]) for cid in player.library)
        assert all(cid == source or is_unknown(view.cards[cid])
                   for cid in state.players[3-viewer].hand)
    # Internal information-flow probe, not a lawful hidden new-print episode.
    probe = deepcopy(state)
    probe.cards[source].name = 'Unobserved hidden identity'
    probe.cards[source].oracle_text = 'Unobserved hidden text'
    probe.players[seat].hand.reverse()
    for player in probe.players.values():
        player.library.reverse()
    opponent, _ = decision_view(original.reload_exact(probe), 3-seat, [])
    owned, _ = decision_view(probe, seat, [])
    assert opponent.cards[source].name == canonical.name
    assert opponent.cards[source].oracle_text == canonical.oracle_text
    assert owned.cards[source].name == probe.cards[source].name
    assert source not in public_card_ids(probe)
    assert original.serialize_match_snapshot(state) == before
