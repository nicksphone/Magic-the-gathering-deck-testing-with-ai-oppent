"""Reviewed numeric metadata coverage; legacy scalar expectation stays strict."""
import pickle
import json
import os
from pathlib import Path
from dataclasses import field, make_dataclass
import pytest

from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine import graveyard_inventory as inventory
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_empty_hand_attack_witness import position, ROWS
from tests.test_linked_damage_targets import raw_card
from game_state.state import Zone, MatchState
from tests import test_numeric_prevention_receipts as numeric


def positive(seat):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    return state


def pure_inventory(state, seat):
    before = pickle.dumps(state, protocol=5)
    result = inventory.public_graveyard_inventory(state, seat)
    assert pickle.dumps(state, protocol=5) == before
    return result


@pytest.mark.parametrize('seat', [1, 2])
def test_default_empty_and_legacy_snapshot_omission_preserve_positive(seat):
    state = positive(seat)
    assert type(state.numeric_prevention_shields) is list
    assert state.numeric_prevention_shields == []
    result = pure_inventory(state, seat)
    assert result['status'] == 'inert'
    payload = serialize_match_snapshot(state)
    payload.pop('numeric_prevention_shields')
    restored = deserialize_match_snapshot(payload)
    assert restored.numeric_prevention_shields == []
    assert pure_inventory(restored, seat) == result
    assert pure_inventory(deserialize_match_snapshot(serialize_match_snapshot(state)), seat) == result


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_salve_and_spent_receipt_remain_context_veto(seat):
    state, target = numeric.shielded(seat)
    assert state.numeric_prevention_shields[0].remaining == 3
    result = pure_inventory(state, seat)
    assert result == {'status': 'unknown', 'reason': 'uncovered continuation/effect context', 'receipts': []}
    state, _ = numeric.base.cast(state, 'Lightning Bolt', seat, target)
    state = numeric.base.finish(numeric.prior.reload_exact(state))
    assert state.numeric_prevention_shields[0].remaining == 0
    assert not state.cards[target].counters.get('__prevent_damage_shield')
    assert pure_inventory(state, seat) == result
    assert pure_inventory(numeric.prior.reload_exact(state), seat) == result
    projected, _ = decision_view(state, seat, [])
    assert pure_inventory(projected, seat) == result


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_checked_turn_cleanup_removes_receipts_not_unrelated_vetoes(seat):
    state, target = numeric.shielded(seat)
    assert pure_inventory(state, seat)['reason'] == 'uncovered continuation/effect context'
    original_turn = state.turn
    for _ in range(64):
        if not state.numeric_prevention_shields:
            break
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    else:
        pytest.fail('Checked turn continuation did not reach receipt cleanup')
    assert state.turn >= original_turn
    assert not state.cards[target].counters.get('__prevent_damage_shield')
    assert all(player.prevent_damage_shield == 0 for player in state.players.values())
    # Salve's whole graveyard body is outside B coverage; cleanup is NOT certification.
    result = pure_inventory(numeric.prior.reload_exact(state), seat)
    assert result['status'] == 'unknown'
    assert result['reason'] != 'incomplete state metadata'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [None, (), {}, 0, False, ''], ids=['null','tuple','dict','int','bool','str'])
def test_malformed_numeric_container_fails_closed_without_root_mutation(seat, bad):
    state = positive(seat)
    state.numeric_prevention_shields = bad
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_numeric_field_fails_closed(seat):
    state = positive(seat)
    del state.numeric_prevention_shields
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['spent', 'expired', 'old-target', 'malformed-entry'])
def test_component_nonempty_metadata_never_filtered_to_inert(seat, kind):
    # Deliberate component metadata fault, not a fabricated canonical shield episode.
    state = positive(seat)
    state.numeric_prevention_shields = [{'boundary': kind}]
    assert pure_inventory(state, seat) == {
        'status': 'unknown', 'reason': 'uncovered continuation/effect context', 'receipts': []}


@pytest.mark.parametrize('seat', [1, 2])
def test_future_schema_field_and_runtime_field_stay_unknown(seat, monkeypatch):
    state = positive(seat)
    assert pure_inventory(state, seat)['status'] == 'inert'
    actual_fields = inventory.fields
    extra = make_dataclass('FutureMetadata', [('future_permission', list, field(default_factory=list))])
    monkeypatch.setattr(inventory, 'fields', lambda schema: actual_fields(schema) + actual_fields(extra)
                        if schema is MatchState else actual_fields(schema))
    assert pure_inventory(state, seat)['status'] == 'unknown'
    monkeypatch.setattr(inventory, 'fields', actual_fields)
    state.future_permission = []
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_identity_changes_do_not_change_default_inventory(seat):
    state = positive(seat)
    expected = pure_inventory(state, seat)
    assert expected['status'] == 'inert'
    for cid in state.players[3-seat].hand + state.players[3-seat].library:
        state.cards[cid].name = 'Private identity fault injection'
        state.cards[cid].oracle_text = 'Unknown private text, not an invented gameplay card.'
    assert pure_inventory(state, seat) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('recipient', [1, 2])
def test_legacy_nonzero_player_scalar_is_uncovered_context(seat, recipient):
    # Legacy component snapshot with anonymous scalar, NOT a synthetic paid Salve source.
    from rules_engine.prevention import add_player_prevention_shield
    state = positive(seat)
    add_player_prevention_shield(state, recipient, 3)
    payload = serialize_match_snapshot(state)
    payload.pop('numeric_prevention_shields')
    state = deserialize_match_snapshot(payload)
    assert state.numeric_prevention_shields == []
    assert state.players[recipient].prevent_damage_shield == 3
    result = pure_inventory(state, seat)
    if os.environ.get('MTG_NUMERIC_INVENTORY_EVIDENCE'):
        root = Path(os.environ['MTG_NUMERIC_INVENTORY_EVIDENCE'])
        root.mkdir(parents=True, exist_ok=True)
        (root / f'legacy-player-{seat}-{recipient}.json').write_text(json.dumps({
            'actor': seat, 'recipient': recipient, 'compatibility_helper': 'add_player_prevention_shield',
            'classification': result, 'snapshot': serialize_match_snapshot(state),
            'root_pickle_equal': True, 'scope': 'canonical board, anonymous legacy component shield'}, indent=2))
    assert result['status'] == 'unknown'
