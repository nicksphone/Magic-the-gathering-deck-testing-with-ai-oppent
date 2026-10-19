"""Native codec and escape-budget protocols, not paid escape-game evidence."""
from copy import deepcopy
import json

import pytest

from game_state.serializers import serialize_match_snapshot
from rules_engine.spell_cost_witness import escape_payment_condition
from tests.test_forge_human_replacement_order import setup


@pytest.mark.parametrize('seat', [1, 2])
def test_extracted_card_codec_matches_complete_existing_snapshot(seat):
    from game_state.serializers import _card_snapshot, _card_from_snapshot
    state, _, _, _ = setup(seat)
    before = serialize_match_snapshot(state)
    for cid, card in state.cards.items():
        encoded = _card_snapshot(card)
        assert encoded == before['cards'][cid]
        clone = _card_from_snapshot(deepcopy(encoded), state.players)
        assert _card_snapshot(clone) == encoded
        assert clone is not card and clone.characteristic_record is not card.characteristic_record
        assert clone.counters is not card.counters and clone.knowledge_snapshot is not card.knowledge_snapshot
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_native_escape_export_retains_consumed_budget_pending_and_recipe(seat):
    from rules_engine.spell_cost_witness import export_payment_condition, restore_payment_condition
    state, _, source, _ = setup(seat)
    condition = escape_payment_condition(seat, source, 0, [], max_nodes=3)
    assert condition.visit() and condition.visit()
    pending = condition.with_pending([source])
    assert pending.budget is condition.budget
    record = export_payment_condition(pending)
    assert record['budget'] == {'nodes': 2, 'exhausted': False}
    assert record['max_nodes'] == 3 and record['selected'] == [] and record['pending'] == [source]
    restored = restore_payment_condition(json.loads(json.dumps(record)))
    assert restored(state) == pending(state)
    assert restored.visit() and not restored.visit()
    assert restored.budget == {'nodes': 3, 'exhausted': True}
    assert condition.budget == {'nodes': 2, 'exhausted': False}
    assert restored.with_pending([]).budget is restored.budget
    assert export_payment_condition(restored)['budget'] == restored.budget


@pytest.mark.parametrize('field,value', [
    ('kind', 'unknown'), ('max_nodes', True), ('valid', 1),
    ('pending', [3]), ('budget', {'nodes': False, 'exhausted': False}),
    ('budget', {'nodes': 4, 'exhausted': False}),
], ids=['unknown-kind', 'bool-max', 'int-valid', 'nonstring-pending', 'bool-nodes', 'over-budget'])
def test_native_escape_restore_rejects_malformed_recipe_or_budget(field, value):
    from rules_engine.spell_cost_witness import export_payment_condition, restore_payment_condition
    condition = escape_payment_condition(1, 'public-protocol-source', 0, [], max_nodes=3)
    record = export_payment_condition(condition)
    record[field] = value
    with pytest.raises(ValueError):
        restore_payment_condition(record)
    assert condition.budget == {'nodes': 0, 'exhausted': False}


def test_opaque_live_condition_is_not_serializable_native_authority():
    from rules_engine.spell_cost_witness import _BoundedPaymentPostcondition, export_payment_condition
    condition = _BoundedPaymentPostcondition(lambda state, pending: True)
    assert condition(None) is True
    with pytest.raises(ValueError):
        export_payment_condition(condition)
    assert condition(None) is True and condition.budget == {'nodes': 0, 'exhausted': False}
