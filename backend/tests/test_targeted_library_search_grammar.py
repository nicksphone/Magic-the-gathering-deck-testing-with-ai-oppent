"""Pure complete-body adversarial grammar; no Oracle-mutated game cards."""
import pytest

from rules_engine.oracle_effects import _infer_targeted_search_effect, inspect_target_hints
from rules_engine.action_validation import ActionRejected
from tests.test_targeted_library_search_compiler import ROWS, setup, act, snap
from tests.test_paid_counter_family_audit import extract_activated_abilities

BODY = 'Target player searches their library for a basic land card, puts it onto the battlefield tapped, then shuffles.'


@pytest.mark.parametrize('suffix', [
    ' Draw a card.', ' If you control a creature.', ' unless an opponent pays {1}.',
    ' Put zero +1/+1 counters on up to one target creature.',
    ' Put 0 +1/+1 counters on up to one target creature.',
    ' Put X +1/+1 counters on up to one target creature.',
    ' Put two +1/+1 counters on up to two target creatures.',
    ' Put two +1/+1 counters on up to one target creature. Draw a card.',
])
def test_new_targeted_prefix_unknown_suffix_has_diagnostic_no_partial_reward(suffix):
    key, payload = _infer_targeted_search_effect(BODY + suffix, {'target_player': 1})
    assert key == 'noop' and payload['__unsupported_targeted_search'] == BODY + suffix


@pytest.mark.parametrize('target', [1, 2])
@pytest.mark.parametrize('amount', ['a', 'two', '12'])
def test_complete_optional_counter_suffix_zero_selected_target_is_not_inferred(target, amount):
    body = BODY + f' Put {amount} +1/+1 counters on up to one target artifact or creature.'
    key, payload = _infer_targeted_search_effect(body, {'target_player': target})
    assert key == 'effect_sequence' and [x['effect_key'] for x in payload['effects']] == ['search_library', 'add_counters']
    assert payload['effects'][0]['payload']['target_player'] == target
    counters = payload['effects'][1]['payload']
    assert counters['target_card_id'] is None
    assert counters['amount'] == {'a': 1, 'two': 2, '12': 12}[amount]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Fertilid', "Fertilid's Favor"])
def test_qualified_hints_have_parsed_public_filter_and_explicit_player_no_private_library_ids(seat, name):
    state, source, target, lands = setup(name, seat)
    card = state.cards[source]
    if name == 'Fertilid':
        from copy import deepcopy
        card = deepcopy(card)
        card.oracle_text = extract_activated_abilities(card)[0]['text']
        card.card_faces = []
    before = snap(state)
    hints = inspect_target_hints(state, card, seat, {})
    assert snap(state) == before
    assert hints['library_search'] == {'contains': 'basic_land', 'destination': 'battlefield', 'max_count': 1, 'allow_zero': True}
    assert {x['id'] for x in hints['player_targets']} == {1, 2}
    import json
    assert not any(cid in json.dumps(hints) for ids in lands.values() for cid in ids)
    if name == "Fertilid's Favor":
        assert target in {x['id'] for x in hints['creature_targets']}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field,value', [('search_contains', 'creature'), ('search_count', 12),
                                       ('search_mv_max', None), ('search_card_ids', [])])
def test_actual_targeted_activation_rejects_client_search_overrides_root_pure(seat, field, value):
    state, source, _, _ = setup('Fertilid', seat)
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 0,
                         'targets': {'target_player': 3-seat, field: value}})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('targets', [{}, {'target_player': None}, {'target_player': 99}])
def test_missing_or_invalid_player_never_infers_own_or_opponent_before_cost(seat, targets):
    state, source, _, _ = setup('Fertilid', seat)
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 0, 'targets': targets})
    assert snap(state) == before
