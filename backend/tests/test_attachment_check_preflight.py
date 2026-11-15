"""Canonical attachment controls plus one explicitly abstract Fortification case."""
import hashlib
import json
from pathlib import Path
import pickle
from unittest.mock import patch

import pytest

from game_state.state import CardInstance, MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine import basic_land_layer, state_based_actions as sba
from rules_engine.action_validation import ActionRejected
from rules_engine.attachments import attach_if_legal
from rules_engine.bestow import begin_bestow, is_bestowed
from rules_engine.query_context import query_cache
from tests.browser_positive83_canonical import entry, raw_card as browser_raw
from tests.test_linked_damage_targets import raw_card as add_raw


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES = {
    'Rancor': ('attached_characteristics/rancor.json',
               '44cb142c9d39c679da519460c6fd44cbafcac76ea6dd4e3c04b267dd14c5cd88'),
    'Leafcrown Dryad': ('announced_target_references/leafcrown-dryad.json',
                      '3856e760893caeb982eb5e720fa39674ab62acffda8080c64fc8317cb15ed63f'),
    'Bonesplitter': ('static_global_keywords/canonical.json',
                    'c7b76c9c901d1f584bcb0791c4ee677f88eca6d95845638d5a48a0d66fb87ece'),
}


def add(state, name, seat):
    if name in SOURCES:
        filename, digest = SOURCES[name]
        data = (FIXTURES / filename).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
        raw = json.loads(data)
        if name == 'Bonesplitter':
            raw = raw[name]
        assert raw['object'] == 'card' and raw['name'] == name and raw['id'] and raw['oracle_id']
    else:
        raw = browser_raw(name)
    card = add_raw(state, raw, seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


def board(seat, count=0):
    deck = [entry('Forest', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=1108)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    for index in range(count):
        add(state, 'Forest' if index % 2 else 'Grizzly Bears', 1 + index % 2)
    state.log.append('Retained fixture history')
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 16, 31])
def test_no_attachment_work_uses_one_battlefield_scan_and_preserves_root(seat, count):
    state = board(seat, count)
    before = pickle.dumps(state, protocol=5)
    function = basic_land_layer._printed_layer_four_effect
    with patch.object(basic_land_layer, '_printed_layer_four_effect', wraps=function) as calls:
        sba._apply_attachment_state_checks(state)
    assert calls.call_count <= count, 'Classification repeated a complete battlefield scan per permanent'
    assert pickle.dumps(state, protocol=5) == before and query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Rancor', 'Bonesplitter'])
def test_legal_attached_permanents_remain_unchanged(seat, name):
    state = board(seat)
    host = add(state, 'Grizzly Bears', seat)
    source = add(state, name, seat)
    assert attach_if_legal(state, source.id, host.id)
    before = pickle.dumps(state, protocol=5)
    sba._apply_attachment_state_checks(state)
    assert pickle.dumps(state, protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target', [None, 'missing-fixture-target'])
def test_unattached_or_invalid_aura_still_leaves_battlefield(seat, target):
    state = board(seat)
    aura = add(state, 'Rancor', seat)
    aura.attached_to = target  # Explicit invalid runtime pose; printed facts unchanged.
    sba._apply_attachment_state_checks(state)
    assert aura.zone == Zone.GRAVEYARD and aura.id in state.players[seat].graveyard
    assert aura.id not in state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_nonattachment_with_retained_target_still_detaches(seat):
    state = board(seat)
    host = add(state, 'Grizzly Bears', seat)
    source = add(state, 'Grizzly Bears', seat)
    source.attached_to = host.id  # Structural invalid pose, not a card ability.
    sba._apply_attachment_state_checks(state)
    assert source.attached_to is None and source.zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_equipment_with_noncreature_target_detaches_without_departure(seat):
    state = board(seat)
    land = add(state, 'Forest', seat)
    source = add(state, 'Bonesplitter', seat)
    source.attached_to = land.id
    sba._apply_attachment_state_checks(state)
    assert source.attached_to is None and source.zone == Zone.BATTLEFIELD


def test_abstract_fortification_category_uses_existing_detachment_path():
    state = board(1)
    creature = add(state, 'Grizzly Bears', 1)
    source = CardInstance(state.allocate_object_id(), 'Unit Fortification', 1, 1,
                          Zone.BATTLEFIELD, ['Artifact'], type_line='Artifact — Fortification')
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    source.attached_to = creature.id
    sba._apply_attachment_state_checks(state)
    assert source.attached_to is None and source.zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_bestow_reverts_when_host_has_left(seat):
    state = board(seat)
    host = add(state, 'Grizzly Bears', seat)
    source = add(state, 'Leafcrown Dryad', seat)
    printed_text = source.oracle_text
    begin_bestow(source)
    assert attach_if_legal(state, source.id, host.id)
    state.players[seat].battlefield.remove(host.id)
    host.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(host.id)
    sba._apply_attachment_state_checks(state)
    assert not is_bestowed(source) and source.attached_to is None
    assert source.zone == Zone.BATTLEFIELD and 'Creature' in source.types
    assert source.oracle_text == printed_text


@pytest.mark.parametrize('seat', [1, 2])
def test_replacement_preflight_failure_is_atomic(seat):
    state = board(seat)
    add(state, 'Rancor', seat)
    before = pickle.dumps(state, protocol=5)
    with patch('rules_engine.replacement.select_graveyard_entry_plan',
               side_effect=ActionRejected('fixture preflight unavailable')):
        with pytest.raises(ActionRejected, match='fixture preflight unavailable'):
            sba._apply_attachment_state_checks(state)
    assert pickle.dumps(state, protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_classification_scope_is_fresh_after_earlier_aura_departure(seat):
    state = board(seat)
    early = add(state, 'Rancor', seat)
    later = add(state, 'Grizzly Bears', seat)
    marker = object()
    observed = []
    original = sba.is_aura

    def inspect(card, root):
        cache = query_cache(root)
        assert cache is not None
        if card.id == early.id:
            cache[marker] = True
        elif card.id == later.id:
            assert marker not in cache and early.zone == Zone.GRAVEYARD
            observed.append(card.id)
        return original(card, root)

    with patch.object(sba, 'is_aura', side_effect=inspect):
        sba._apply_attachment_state_checks(state)
    assert observed == [later.id] and query_cache(state) is None
