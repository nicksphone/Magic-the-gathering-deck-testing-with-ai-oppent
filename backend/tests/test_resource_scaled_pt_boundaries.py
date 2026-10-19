"""Closed compiler probes and typed internal mocks are not invented playable cards."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from card_data.token_definitions import named_artifact_token
from effects import handlers
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import effective_combat_stats
from rules_engine.oracle_effects import _infer_resource_scaled_target_pt, infer_effect_from_oracle
from tests import test_bloodtithe_resource_debuff_audit as original

BODY = original.RAW['oracle_text'].split('{T}, Sacrifice this creature: ', 1)[1]
KEY = 'resource_scaled_temporary_pt_buff'


@pytest.mark.parametrize('subtype', ['Blood', 'Food', 'Treasure'])
def test_generic_complete_compiler_descriptor_not_named_card(subtype):
    # Compiler grammar probe only; no modified Oracle installed into gameplay.
    body = BODY.replace('Blood tokens', subtype + ' tokens')
    key, data = _infer_resource_scaled_target_pt(body, {'target_card_id': 'declared'})
    assert key == KEY
    assert data == {'target_card_id': 'declared', 'token_subtype': subtype.lower(),
                    'power_per_token': -2, 'toughness_per_token': -2}
    assert 'x_value' not in data and 'count' not in data and 'controller' not in data


@pytest.mark.parametrize('body', [
    BODY + ' Draw a card.', BODY + ' Gain 2 life.',
    BODY.replace('you control', 'an opponent controls'),
    BODY.replace('Blood tokens', 'UnknownSubtype tokens'),
    BODY.replace('twice the number', 'three times the number'),
    BODY.replace('until end of turn', 'permanently'),
    BODY.replace('you control.', 'you control if you have seven cards.'),
    BODY.replace('as a sorcery.', 'during your upkeep.'),
    BODY.replace('-X/-X', '+X/+X'),
])
def test_candidate_unknown_complete_body_returns_diagnostic_not_partial_reward(body):
    key, payload = _infer_resource_scaled_target_pt(body, {'target_card_id': 'declared'})
    assert key == 'noop' and payload == {'__unsupported_instruction': body}


@pytest.mark.parametrize('body', [original.RAW['oracle_text'], 'Create a Blood token.',
                                  'Target creature gets +3/+3 until end of turn.'])
def test_other_full_bodies_do_not_enter_new_family(body):
    assert _infer_resource_scaled_target_pt(body, {}) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_native_descriptor_snapshot_and_numeric_delegation_preserve_receipts(request, monkeypatch, seat):
    state, source, target = original.ready(seat)
    before = original.snap(state)
    key, data = infer_effect_from_oracle(state, SimpleNamespace(
        name=original.RAW['name'], id=source, oracle_text=BODY, mana_cost=''), seat,
        {'target_card_id': target, 'x_value': 97}, report_unsupported=False)
    assert key == KEY and 'x_value' not in data and original.snap(state) == before
    state = original.activate(request, state, seat, source, target)
    frame = next(item for item in state.stack if item.source_card_id == source)
    assert frame.effect_key == KEY and frame.controller == seat
    native = {key: deepcopy(frame.payload[key]) for key in (
        '__announced_targets', '__announced_target_references', '__activation_source_reference',
        '__source_lki', '__ability_target_text')}
    assert state.cards[source].zone == Zone.GRAVEYARD
    packets = []
    numeric = handlers.temporary_pt_buff
    def spy(current, controller, payload):
        packets.append((controller, deepcopy(payload)))
        return numeric(current, controller, payload)
    monkeypatch.setattr(handlers, 'temporary_pt_buff', spy)
    state = original.drain(original.restore(state))
    assert len(packets) == 1 and packets[0][0] == seat
    assert all(packets[0][1][key] == value for key, value in native.items())
    assert packets[0][1]['power'] == packets[0][1]['toughness'] == -2
    assert effective_combat_stats(state, target) == (4, 4)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_suppression_after_announcement_does_not_counter_ability(request, seat):
    state, source, target = original.ready(seat)
    state = original.activate(request, state, seat, source, target)
    state, _ = original.cast(state, 3-seat, 'Dress Down')
    state = original.drain(original.restore(state))
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert effective_combat_stats(state, target) == (4, 4)


@pytest.mark.parametrize('seat', [1, 2])
def test_wrong_actor_rejection_is_atomic_on_actual_paid_position(seat):
    state, source, target = original.ready(seat)
    before = original.snap(state)
    with pytest.raises(ActionRejected):
        original.act(state, 3-seat, original.activation(state, source, target))
    assert original.snap(state) == before


@pytest.mark.parametrize('case,expected', [
    ('canonical', 1), ('opponent', 0), ('non_token', 0), ('lost_artifact', 0),
    ('departed', 0), ('name_only', 0), ('extra_subtype', 1), ('substring', 0),
])
def test_internal_typed_resource_filter_and_metadata_delegation(monkeypatch, case, expected):
    # Minimal typed interface unit mock from canonical token definition, NOT a
    # constructed gameplay episode or claimed paid subtype-changing action.
    definition = named_artifact_token('Blood')
    card = SimpleNamespace(id='token', controller=1, zone=Zone.BATTLEFIELD,
        is_token=True, type_line=definition['type_line'], name=definition['name'])
    types = ['Artifact']
    if case == 'opponent': card.controller = 2
    if case == 'non_token': card.is_token = False
    if case == 'lost_artifact': types = ['Creature']
    if case == 'departed': card.zone = Zone.GRAVEYARD
    if case == 'name_only': card.type_line = 'Token Artifact'
    if case == 'extra_subtype': card.type_line += ' Food'
    if case == 'substring': card.type_line = 'Token Artifact - Bloodstone'
    state = SimpleNamespace(players={1: SimpleNamespace(battlefield=['token'])}, cards={'token': card})
    monkeypatch.setattr(handlers, 'effective_types', lambda state, card: types)
    monkeypatch.setattr('rules_engine.land_types.effective_type_line', lambda state, card: card.type_line)
    packets = []
    monkeypatch.setattr(handlers, 'temporary_pt_buff', lambda state, controller, payload: packets.append((controller, payload)))
    payload = {'target_card_id': 'explicit', 'token_subtype': 'blood',
               'power_per_token': -2, 'toughness_per_token': -2,
               '__announced_target_references': {'untouched': 'unit-boundary-marker'}}
    before = deepcopy(payload)
    handlers.resource_scaled_temporary_pt_buff(state, 1, payload)
    assert payload == before and len(packets) == 1
    assert packets[0][0] == 1 and packets[0][1] == {**before, 'power': -2*expected, 'toughness': -2*expected}
