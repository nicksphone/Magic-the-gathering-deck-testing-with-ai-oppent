"""L1 ownership controls; the prototype-only grammar witness is explicit protocol."""
from copy import deepcopy

import pytest

from game_state.state import CardInstance, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.copiable_values import values
from tests.test_entry_copy_native_936 import position, raw, cast, pending_steel
from tests.graveyard_batch_native_support_bf62 import place, choose


@pytest.mark.parametrize('seat', [1, 2])
def test_selected_face_proxy_retains_exact_new_face_without_aliasing_actual_card(seat):
    from rules_engine.card_faces import select_cast_face
    state = position(['Delver of Secrets // Insectile Aberration'],
                     ['Delver of Secrets // Insectile Aberration'], seat)
    card = next(card for card in state.cards.values() if card.owner == seat and card.card_faces)
    before = deepcopy(vars(card))
    selected = select_cast_face(card, 1)
    assert selected.name == values(selected)['name'] == 'Insectile Aberration'
    assert values(selected)['power'] == 3
    assert selected.characteristic_record is not card.characteristic_record
    assert selected.characteristic_record['physical'] is not card.characteristic_record['physical']
    assert vars(card) == before


def test_prototype_protocol_projection_is_copy_on_write_and_updates_only_active_values():
    from rules_engine.alternative_casts import spell_cast_view
    # Deliberately no real card name/RAW claim: full official prototype RAW is not in this packet.
    card = CardInstance('prototype-protocol', 'Prototype protocol', 1, 1, Zone.HAND,
        ['Artifact', 'Creature'], mana_cost='{7}', power=7, toughness=5,
        printed_power='7', printed_toughness='5', oracle_text='Prototype {1}{B}{B} - 3/3',
        type_line='Artifact Creature', colors=[])
    before = deepcopy(vars(card))
    projected = spell_cast_view(card, 'prototype')
    assert values(projected)['power'] == values(projected)['toughness'] == 3
    assert values(projected)['mana_cost'] == '{1}{B}{B}' and values(projected)['colors'] == ['B']
    assert projected.characteristic_record['physical']['power'] == 7
    assert projected.characteristic_record is not card.characteristic_record
    assert vars(card) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_bestow_view_does_not_alias_record_or_make_its_later_aura_type_copiable(seat):
    from rules_engine.bestow import bestow_cast_view
    state = position(['Springheart Nantuko'], ['Springheart Nantuko'], seat)
    card = next(c for c in state.cards.values() if c.owner == seat and c.name == 'Springheart Nantuko')
    before = deepcopy(vars(card))
    selected = bestow_cast_view(card)
    assert 'Aura' in selected.type_line and 'Creature' not in selected.types
    assert 'Creature' in values(selected)['types'] and 'Aura' not in values(selected)['type_line']
    assert selected.characteristic_record is not card.characteristic_record
    assert vars(card) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_lki_copy_descriptor_retains_initial_loyalty_not_live_counter_amount(seat):
    from rules_engine.counter_placement import put_counters
    from rules_engine.attached_token_payment import copiable_lki
    state = position(['Teferi, Hero of Dominaria'], ['Teferi, Hero of Dominaria'], seat)
    state, cid = cast(state, seat, 'Teferi, Hero of Dominaria')
    assert resolve_top_of_stack(state) and state.cards[cid].loyalty == 4
    put_counters(state, 'loyalty', 3, target_card_id=cid)
    before = serialize_match_snapshot(state)
    lki = copiable_lki(state, state.cards[cid])
    assert lki['descriptor']['loyalty'] == 4 and state.cards[cid].loyalty == 7
    lki['descriptor']['types'].append('protocol-mutation')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_missing_record_marks_lki_unavailable_but_real_noncopy_blink_still_completes(seat):
    from rules_engine.attached_token_payment import copiable_lki
    state = position(['Grizzly Bears', 'Cloudshift'], ['Grizzly Bears', 'Cloudshift'], seat)
    cid = place(state, 'Grizzly Bears', Zone.BATTLEFIELD, seat)
    old = serialize_match_snapshot(state)
    old['cards'][cid].pop('characteristic_record')  # Explicit legacy snapshot format.
    state = deserialize_match_snapshot(old)
    lki = copiable_lki(state, state.cards[cid])
    assert lki['descriptor'] is None and lki['unavailable'] == 'missing_copiable_characteristics'
    state, _ = cast(state, seat, 'Cloudshift', target_card_id=cid)
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].name == 'Grizzly Bears'
    assert not state.pending_mechanic_choice and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_metadata_is_not_silently_invented_or_filtered_at_actual_copy_boundary(seat):
    state, steel, target, _ = pending_steel(seat)
    old = serialize_match_snapshot(state)
    old['cards'][target].pop('characteristic_record')
    state = deserialize_match_snapshot(old)
    assert target in state.pending_mechanic_choice['options']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='retained physical'):
        choose(state, seat, target)
    assert serialize_match_snapshot(state) == before
    assert state.cards[steel].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_copiable_query_and_snapshot_are_independent_values_not_shared_physical_dicts(seat):
    state = position(['Sol Ring'], ['Sol Ring'], seat)
    card = next(c for c in state.cards.values() if c.owner == seat and c.name == 'Sol Ring')
    before = deepcopy(vars(card))
    value = values(card)
    value['types'].append('protocol-mutation')
    saved = serialize_match_snapshot(state)
    saved['cards'][card.id]['characteristic_record']['physical']['name'] = 'protocol-mutation'
    assert vars(card) == before


def test_existing_linked_copy_writer_updates_retained_values_and_preserves_physical_faces():
    # Existing normalized MDFC producer fixture, not a new full-RAW certification.
    from tests.test_modal_spell_faces import _valki_with_exiled_mystic
    state, source, target = _valki_with_exiled_mystic()
    physical_faces = deepcopy(state.cards[source].card_faces)
    state = checked_action(state, RulesEngine(), 1, {'type': 'activate_ability',
        'card_id': source, 'ability_index': 0, 'targets': {'x_value': 1}})
    assert not resolve_top_of_stack(state)
    state = checked_action(state, RulesEngine(), 1, {'type': 'choose_mechanic', 'card_ids': [target]})
    assert values(state.cards[source])['name'] == 'Elvish Mystic'
    assert state.cards[source].card_faces == physical_faces
