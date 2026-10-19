"""Native dataclass compatibility with the immutable936 positional ABI."""
from copy import deepcopy
from dataclasses import fields, replace
import inspect
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.copiable_values import values
from tests.graveyard_batch_native_support_bf62 import choose, snapshot
from tests.test_entry_copy_native_936 import pending_steel, position


ABI = json.loads((Path(__file__).parent /
    'fixtures/entry_copy_layout641/CARDINSTANCE936_POSITIONAL_ABI.json').read_text())


def test_native_constructor_and_match_args_equal_all_original936_slots():
    parameters = inspect.signature(CardInstance).parameters
    positional = [name for name, p in parameters.items()
                  if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD]
    assert positional == ABI['old_positional_names']
    assert list(CardInstance.__match_args__) == ABI['old_match_args']
    assert parameters['characteristic_record'].kind == inspect.Parameter.KEYWORD_ONLY
    assert fields(CardInstance)[-1].name == 'knowledge_snapshot'
    assert next(f for f in fields(CardInstance) if f.name == 'characteristic_record').kw_only


def test_old_final_positional_knowledge_slot_works_but_record_is_not_new_positional_slot():
    state = position(['Sol Ring'], ['Sol Ring'], 1)
    card = next(c for c in state.cards.values() if c.owner == 1 and c.name == 'Sol Ring')
    args = [deepcopy(getattr(card, name)) for name in ABI['old_positional_names']]
    birth = CardInstance(*args)
    assert birth.knowledge_snapshot == args[-1]
    assert values(birth) == values(card)
    explicit = CardInstance(*args, characteristic_record=deepcopy(card.characteristic_record))
    assert explicit.characteristic_record == card.characteristic_record
    with pytest.raises(TypeError):
        CardInstance(*args, {})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('record', ['adequate', 'explicit_null'])
def test_keyword_record_replace_snapshot_and_real_copy_keep_birth_and_unavailable_distinct(seat, record):
    state, steel, target, _ = pending_steel(seat)
    source = state.cards[steel]
    before = deepcopy(vars(source))
    cloned = replace(source, characteristic_record=deepcopy(source.characteristic_record))
    assert values(cloned) == values(source)
    cloned.characteristic_record['values']['name'] = 'Independent replacement value'
    assert vars(source) == before
    assert replace(source).characteristic_record == source.characteristic_record
    saved = serialize_match_snapshot(state)
    if record == 'explicit_null':
        saved['cards'][target]['characteristic_record'] = None
    state = deserialize_match_snapshot(saved)
    assert state.cards[steel].zone == Zone.STACK and target in state.pending_mechanic_choice['options']
    if record == 'explicit_null':
        before_choice = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            choose(state, seat, target)
        assert serialize_match_snapshot(state) == before_choice
        assert state.cards[target].characteristic_record == {}
    else:
        state = choose(snapshot(state), seat, target)
        assert state.cards[steel].name == 'Sol Ring' and state.cards[steel].owner == seat
        assert values(state.cards[steel])['name'] == 'Sol Ring'
        assert state.cards[steel].characteristic_record['physical']['name'] == 'Sculpting Steel'
        assert snapshot(state).cards[steel].characteristic_record == state.cards[steel].characteristic_record
