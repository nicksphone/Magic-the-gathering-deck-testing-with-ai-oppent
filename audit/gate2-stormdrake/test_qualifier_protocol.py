"""INTERNALPROTOCOL mutations; not real saved-game or paid-action certificates."""
from copy import deepcopy
import json

import pytest

import domain_paid_support as g
import test_paid_exchange_desired as original
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.targeting import stack_object_kind, validate_hexproof_shroud_targets
from rules_engine.protection import hexproof_variants


@pytest.mark.parametrize('suffix', [' and spells', ' while tapped', ' unless you pay {1}',
                                  '; draw a card', ' from unknown things', ' and from blue',
                                  '. Unknown audit instruction.', ', shroud'])
def test_complete_qualifier_unknown_suffix_is_not_partially_recognized(suffix):
    phrase = 'Hexproof from activated and triggered abilities'
    assert hexproof_variants(phrase) == [phrase.lower()]
    # Parser-negative input only; never assign fictional Oracle to a game card.
    assert hexproof_variants(phrase + suffix) == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['mana-only', 'partial-activation', 'conflicting-shapes',
                               'malformed-cast', 'malformed-activation', 'native-authoritative',
                               'malformed-native', 'copied-precedence', 'malformed-copy',
                               'trigger-precedence'])
def test_internal_protocol_kind_shapes_fail_closed_only_where_required(seat, case):
    filename = original.HERE / 'old-producer-captures' / f'old-native-activation-{seat}.json'
    state = deserialize_match_snapshot(json.loads(filename.read_bytes())['snapshot'])
    item = state.stack[-1]
    activation = deepcopy(item.payload)
    castfile = original.HERE / 'old-producer-captures' / f'old-native-spell-{seat}.json'
    oldcast = deserialize_match_snapshot(json.loads(castfile.read_bytes())['snapshot']).stack[-1].payload
    expected = 'legacy_unknown'
    rejected = False
    if case == 'mana-only':
        item.payload = {'mana_spent': 2}
    elif case == 'partial-activation':
        del item.payload['__activation_source_reference']
    elif case == 'conflicting-shapes':
        item.payload.update(oldcast)
    elif case == 'malformed-cast':
        item.payload = deepcopy(oldcast)
        item.payload['mana_spent'] = True
        rejected = True
    elif case == 'malformed-activation':
        item.payload['__activation_source_reference']['incarnation'] = True
        rejected = True
    elif case == 'native-authoritative':
        item.payload.update(oldcast)
        item.payload['__announced_stack_kind'] = 'activated'
        expected = 'activated'
    elif case == 'malformed-native':
        item.payload['__announced_stack_kind'] = True
        rejected = True
    elif case == 'copied-precedence':
        item.payload['__stack_copy_kind'] = 'spell'
        item.payload['__announced_stack_kind'] = 'activated'
        expected = 'spell'
    elif case == 'malformed-copy':
        item.payload['__stack_copy_kind'] = False
        rejected = True
    elif case == 'trigger-precedence':
        item.payload['__trigger_event'] = 'enters_battlefield'
        item.payload['__announced_stack_kind'] = 'activated'
        expected = 'triggered'
    before = serialize_match_snapshot(state)
    if rejected:
        with pytest.raises(ActionRejected):
            stack_object_kind(state, item)
    else:
        assert stack_object_kind(state, item) == expected
        facts = json.loads((original.HERE / 'qualifier-canonical.json').read_bytes())
        protected = g.add(state, facts, original.SOURCE, 3-seat)
        lawful = activation['target_card_id']
        assert validate_hexproof_shroud_targets(state, seat, {'target_card_id': lawful},
                                               source_kind=expected)[0]
        assert validate_hexproof_shroud_targets(state, seat, {'target_card_id': protected},
                                               source_kind=expected)[0] == (expected == 'spell')
        before = serialize_match_snapshot(state)
        assert stack_object_kind(state, item) == expected
    assert serialize_match_snapshot(state) == before
