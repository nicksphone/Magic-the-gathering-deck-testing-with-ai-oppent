"""Canonical printing through native model/copy/restore, not lifecycle acceptance.

Missing defense, copied live counters/protector, invented physical back faces,
lost copy history and silently accepted legacy Battle metadata are the breaks.
All positions below are declared model inputs; no causal cast/combat is claimed.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from game_state.serializers import _card_snapshot, _card_from_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.copiable_values import values, apply, project, expire_temporary_copies
from rules_engine.card_faces import select_cast_face, apply_transform_face
from rules_engine.alternative_casts import restore_printed_characteristics
from tests.test_conditional_graveyard_self_copy import row as ordinary_row, place
from tests.stage_metadata import mark as _stage_metadata

BATTLE = 'Invasion of Zendikar // Awakened Skyclave'


def position(seat):
    path = Path(__file__).parent / 'fixtures/battle_full_printing/invasion-of-zendikar-mom-194.json'
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == '1e49bb006e579e3a88052ab773f5974f761e4a8fedd6fda669768d92f2b82d74'
    raw = json.loads(data)
    assert raw['object'] == 'card' and len(raw) == 60 and raw['name'] == BATTLE
    counts = Counter({'Forest': 58, 'Shifting Woodland': 1, BATTLE: 1})
    deck = [{**raw, 'card_name': name, 'quantity': count} if name == BATTLE
            else ordinary_row(name, count) for name, count in counts.items()]
    state = MatchFactory.from_decks(deck, deck, seed=71203)
    battle = next(c for c in state.cards.values() if c.owner == seat and 'Battle' in c.types)
    land = next(c for c in state.cards.values() if c.owner == seat and c.name == 'Shifting Woodland')
    forest = next(c for c in state.cards.values() if c.owner == seat and c.name == 'Forest')
    return state, battle, land, forest


def mark(label):
    _stage_metadata(label)


def require_model(card):
    mark('canonical-Factory-Battle-printed-defense-assertion-reached')
    assert getattr(card, 'printed_defense', None) == '3'
    assert hasattr(card, 'battle_protector')


def rejected(operation):
    flag = False
    try:
        operation()
    except (ActionRejected, ValueError):
        flag = True
    assert flag


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_factory_retains_defense_without_fabricated_live_counters(seat):
    state, battle, land, _ = position(seat)
    require_model(battle)
    assert battle.battle_protector is None and not battle.counters
    assert values(battle)['printed_defense'] == '3'
    assert battle.characteristic_record['version'] == 3
    assert battle.characteristic_record['effects'] == []
    assert battle.characteristic_record['values'] == battle.characteristic_record['base']
    assert 'printed_defense' not in values(land) and land.characteristic_record['version'] == 1
    mark('canonical-Factory-Battle-characteristics-passed')


@pytest.mark.parametrize('seat', [1, 2])
def test_face_selection_clears_back_defense_without_changing_physical_front(seat):
    _, battle, _, _ = position(seat)
    require_model(battle)
    back = select_cast_face(battle, 1)
    assert back.name == 'Awakened Skyclave' and back.printed_defense is None
    assert values(back)['printed_defense'] is None
    assert battle.printed_defense == '3' and battle.name == 'Invasion of Zendikar'
    assert back.characteristic_record['physical']['printed_defense'] == '3'
    apply_transform_face(battle, 1)
    assert battle.printed_defense is None and values(battle)['printed_defense'] is None
    restore_printed_characteristics(battle)
    assert battle.name == 'Invasion of Zendikar' and battle.printed_defense == '3'


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_preserves_live_counters_protector_and_single_faced_identity(seat):
    _, battle, land, _ = position(seat)
    require_model(battle)
    land.zone = Zone.BATTLEFIELD
    land.counters = {'defense': 2, '+1/+1': 1}
    land.battle_protector = 3 - seat
    apply(land, values(battle), until_end_of_turn=True)
    assert land.name == 'Invasion of Zendikar' and land.printed_defense == '3'
    assert land.counters == {'defense': 2, '+1/+1': 1} and land.battle_protector == 3 - seat
    assert not land.card_faces and land.layout == 'normal'
    restore_printed_characteristics(land)
    assert land.name == 'Shifting Woodland' and land.printed_defense is None
    assert land.counters == {'defense': 2, '+1/+1': 1} and land.battle_protector == 3 - seat
    assert land.characteristic_record['physical']['name'] == 'Shifting Woodland'


@pytest.mark.parametrize('seat', [1, 2])
def test_projection_is_detached_and_copy_values_queries_are_pure(seat):
    _, battle, land, _ = position(seat)
    require_model(battle)
    before = _card_snapshot(land)
    descriptor = values(battle)
    candidate = project(land, descriptor)
    candidate.counters['defense'] = 4
    descriptor['printed_defense'] = '9'
    assert candidate.printed_defense == '3' and values(battle)['printed_defense'] == '3'
    assert _card_snapshot(land) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_temporary_copy_expiry_survives_native_snapshot_round_trip(seat):
    state, battle, land, _ = position(seat)
    require_model(battle)
    land.zone = Zone.BATTLEFIELD
    land.counters['defense'] = 2
    land.battle_protector = 3 - seat
    apply(land, values(battle), until_end_of_turn=True)
    restored = _card_from_snapshot(_card_snapshot(land), state.players)
    assert restored.printed_defense == '3' and values(restored)['printed_defense'] == '3'
    state.cards[land.id] = restored
    expire_temporary_copies(state)
    assert restored.name == 'Shifting Woodland' and restored.printed_defense is None
    assert restored.counters == {'defense': 2} and restored.battle_protector == 3 - seat
    before = _card_snapshot(restored)
    expire_temporary_copies(state)
    assert _card_snapshot(restored) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_permanent_battle_copy_reappears_after_later_temporary_normal_copy(seat):
    state, battle, land, forest = position(seat)
    require_model(battle)
    land.zone = Zone.BATTLEFIELD
    apply(land, values(battle))
    apply(land, values(forest), until_end_of_turn=True)
    assert land.name == 'Forest' and land.printed_defense is None
    expire_temporary_copies(state)
    assert land.name == 'Invasion of Zendikar' and land.printed_defense == '3'
    restore_printed_characteristics(land)
    assert land.name == 'Shifting Woodland' and land.printed_defense is None and not land.card_faces


@pytest.mark.parametrize('seat', [1, 2])
def test_battle_physical_front_returns_after_normal_copy_expiry(seat):
    state, battle, _, forest = position(seat)
    require_model(battle)
    battle.zone = Zone.BATTLEFIELD
    battle.counters['defense'] = 1
    apply(battle, values(forest), until_end_of_turn=True)
    assert battle.printed_defense is None
    expire_temporary_copies(state)
    assert battle.name == 'Invasion of Zendikar' and battle.printed_defense == '3'
    assert battle.counters == {'defense': 1} and len(battle.card_faces) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_face_form_changes_preserve_active_copy_and_new_underlying_base(seat):
    state, battle, _, forest = position(seat)
    require_model(battle)
    battle.zone = Zone.BATTLEFIELD
    apply(battle, values(forest), until_end_of_turn=True)
    back = select_cast_face(battle, 1)
    assert back.name == 'Forest' and back.printed_defense is None
    state.cards[battle.id] = back
    expire_temporary_copies(state)
    assert back.name == 'Awakened Skyclave' and back.printed_defense is None


@pytest.mark.parametrize('seat', [1, 2])
def test_malformed_v3_history_is_rejected_without_changing_card(seat):
    state, battle, land, _ = position(seat)
    require_model(battle)
    land.zone = Zone.BATTLEFIELD
    apply(land, values(battle), until_end_of_turn=True)
    good = _card_snapshot(land)
    variants = []
    for value in (True, -1, 'x', '3.0'):
        raw = deepcopy(good)
        raw['characteristic_record']['effects'][0]['values']['printed_defense'] = value
        variants.append(raw)
    raw = deepcopy(good); raw['characteristic_record']['values']['printed_defense'] = '4'; variants.append(raw)
    raw = deepcopy(good); raw['characteristic_record']['effects'][0]['until_end_of_turn'] = 1; variants.append(raw)
    raw = deepcopy(good); raw['characteristic_record']['physical'].pop('printed_defense'); variants.append(raw)
    raw = deepcopy(good); raw['characteristic_record']['base']['types'] = ['Battle']; variants.append(raw)
    for raw in variants:
        rejected(lambda: _card_from_snapshot(raw, state.players))
        assert _card_snapshot(land) == good


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_battle_copy_records_remain_unknown_and_do_not_rebind(seat):
    _, battle, land, _ = position(seat)
    require_model(battle)
    from rules_engine.copiable_values import FIELDS, PHYSICAL
    old_values = {key: deepcopy(getattr(battle, key)) for key in FIELDS}
    old_physical = {key: deepcopy(getattr(battle, key)) for key in PHYSICAL}
    for version in (1, 2):
        record = {'version': version, 'physical': old_physical, 'values': old_values}
        if version == 2:
            record.update(base=deepcopy(old_values), effects=[{'values': deepcopy(old_values),
                          'until_end_of_turn': True}], added_printed_fields=[])
        battle.characteristic_record = deepcopy(record)
        before = _card_snapshot(battle)
        rejected(lambda: values(battle))
        rejected(lambda: apply(land, old_values))
        assert _card_snapshot(battle) == before and land.name == 'Shifting Woodland'


@pytest.mark.parametrize('seat', [1, 2])
def test_ordinary_v1_v2_copy_snapshot_shapes_remain_compatible(seat):
    state, battle, land, forest = position(seat)
    require_model(battle)
    assert set(land.characteristic_record) == {'version', 'physical', 'values'}
    raw = _card_snapshot(land)
    assert 'printed_defense' not in raw and 'battle_protector' not in raw
    assert _card_snapshot(_card_from_snapshot(raw, state.players)) == raw
    land.zone = Zone.BATTLEFIELD
    apply(land, values(forest), until_end_of_turn=True)
    assert land.characteristic_record['version'] == 2
    assert 'printed_defense' not in values(land)
    expire_temporary_copies(state)
    assert land.name == 'Shifting Woodland' and land.characteristic_record['version'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_snapshot_metadata_rejects_boolean_and_unknown_protector(seat):
    state, battle, _, _ = position(seat)
    require_model(battle)
    good = _card_snapshot(battle)
    for key, value in (('battle_protector', True), ('battle_protector', 9),
                       ('battle_protector', '1'), ('printed_defense', 3),
                       ('printed_defense', True), ('printed_defense', '-1')):
        raw = deepcopy(good); raw[key] = value
        rejected(lambda: _card_from_snapshot(raw, state.players))
    legacy = deepcopy(good)
    legacy.pop('printed_defense'); legacy.pop('battle_protector', None)
    legacy['characteristic_record'] = {}
    restored = _card_from_snapshot(legacy, state.players)
    assert restored.printed_defense is None and restored.battle_protector is None
    rejected(lambda: values(restored))


@pytest.mark.parametrize('seat', [1, 2])
def test_protector_persists_through_face_change_but_clears_on_zone_change(seat):
    _, battle, _, _ = position(seat)
    require_model(battle)
    battle.zone = Zone.BATTLEFIELD
    battle.battle_protector = 3 - seat
    apply_transform_face(battle, 1)
    assert battle.battle_protector == 3 - seat
    battle.move_to_zone(Zone.GRAVEYARD)
    assert battle.battle_protector is None


@pytest.mark.parametrize('seat', [1, 2])
def test_native_spell_copy_candidate_propagates_printed_defense(seat):
    _, battle, _, _ = position(seat)
    require_model(battle)
    from rules_engine.entry_copy import _native_copy_candidate
    copied = {**values(battle), 'card_faces': deepcopy(battle.card_faces), 'layout': 'transform'}
    frame = {'controller': seat, 'payload': {'__copied_card': copied}}
    candidate = _native_copy_candidate(frame, 'declared-spell-copy-candidate', 5)
    assert candidate.printed_defense == '3' and values(candidate)['printed_defense'] == '3'
    assert candidate.battle_protector is None and candidate.counters == {}
    mark('canonical-Battle-characteristics-whole-module-passed')
