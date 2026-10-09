"""Legacy/unknown synthetic protocol controls; not canonical paid grant episodes."""
from copy import deepcopy
import pytest
from game_state.serializers import serialize_match_snapshot as snap, deserialize_match_snapshot
from rules_engine.granted_target_triggers import _record_target_selection, _publish_grants
from rules_engine.ward import mark_stack_targets
from test_granted_target_publication import board, capture, announce, triggers
from tests.test_ward_resolution import cast_at

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['legacy_identity_missing', 'known_empty', 'malformed_supplied', 'ordinary_legacy_ward'])
def test_unknown_is_not_authoritative_empty(case, seat):
    if case == 'ordinary_legacy_ward':
        state, _, source = cast_at(player=seat)
        item = next(x for x in state.stack if x.source_card_id == source)
        item.payload.pop('__granted_target_capture', None)
        wards = len([x for x in state.stack if x.effect_key == 'ward_payment'])
        mark_stack_targets(state, item)
        assert len([x for x in state.stack if x.effect_key == 'ward_payment']) == wards == 1
        assert item.payload['__granted_target_capture']['reason'] == 'missing_capture'
        assert not state.trigger_once_seen_this_turn
        return
    state, cards = board(seat, grant=case != 'known_empty')
    packet = capture(state, cards['target'])
    item = announce(state, cards, packet)
    before_slots = deepcopy(state.trigger_once_seen_this_turn)
    before_triggers = len(triggers(state))
    if case == 'legacy_identity_missing':
        # Explicit legacy-copy protocol fixture; never turn a bare ID into a fresh ref.
        item.payload['__stack_copy_kind'] = 'ability'
        item.payload.pop('__announced_target_references')
        _record_target_selection(state, item)
        status = item.payload['__granted_target_capture']
        assert status == {'status':'unqualified','captured':False,'reason':'legacy_target_identity_missing'}
        assert _publish_grants(state, item) == []
        assert '__announced_target_references' not in item.payload
        restored = deserialize_match_snapshot(snap(state))
        same = next(x for x in restored.stack if x.id == item.id)
        assert same.payload['__granted_target_capture'] == status
        assert _publish_grants(restored, same) == []
    elif case == 'known_empty':
        status = item.payload['__granted_target_capture']
        assert status['status'] == 'captured' and status['captured'] is True
        assert status['target_refs'] and status['receipts'] == [] and 'reason' not in status
        assert _publish_grants(state, item) == []
    else:
        for bad in [None, [], {'captured': False}, {'captured': True, 'receipts': None},
                    {'status':'unqualified','captured':True,'reason':'missing_capture'}]:
            item.payload['__granted_target_capture'] = bad
            with pytest.raises(ValueError):_publish_grants(state, item)
    assert state.trigger_once_seen_this_turn == before_slots
    assert len(triggers(state)) == before_triggers
