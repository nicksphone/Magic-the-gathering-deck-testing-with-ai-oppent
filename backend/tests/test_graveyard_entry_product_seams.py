"""Supplementary pure seam controls, not substitute legal-entry qualification."""
from copy import copy

import pytest

from effects.handlers import shuffle_graveyard_into_library
from game_state.state import Zone
from rules_engine.events import _collect_graveyard_entry_triggers
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.test_kozilek_graveyard_trigger_audit import KOZILEK, start
from tests.test_self_graveyard_replacement_audit import ROWS, snap


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_canonical_complete_instruction_compiles_without_mutating_source(seat):
    state, cid, _, _, _ = start(seat, 'discard')
    card = state.cards[cid]
    assert card.oracle_text == ROWS[KOZILEK]['oracle_text']
    clause = next(line for line in card.oracle_text.splitlines()
                  if 'is put into a graveyard from anywhere' in line)
    proxy = copy(card)
    proxy.oracle_text = clause.split(', ', 1)[1]
    proxy.card_faces, proxy.types = [], []
    before = snap(state)
    assert infer_effect_from_oracle(state, proxy, seat, report_unsupported=False) == (
        'shuffle_graveyard_into_library', {'graveyard_owner': seat})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suffix', [' Draw a card.', ' Then gain 1 life.'])
def test_partial_owner_shuffle_compounds_are_not_accepted_by_new_route(seat, suffix):
    state, cid, _, _, _ = start(seat, 'discard')
    proxy = copy(state.cards[cid])
    proxy.oracle_text = 'Its owner shuffles their graveyard into their library.' + suffix
    proxy.card_faces, proxy.types = [], []
    before = snap(state)
    key, _ = infer_effect_from_oracle(state, proxy, seat, report_unsupported=False)
    assert key != 'shuffle_graveyard_into_library'
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_hand_source_and_incomplete_entry_are_not_a_graveyard_trigger(seat):
    state, cid, _, _, _ = start(seat, 'discard')
    assert state.cards[cid].zone == Zone.HAND
    before = snap(state)
    for payload in ({}, {'card_id': cid}, {'card_id': cid, 'owner': seat}):
        assert _collect_graveyard_entry_triggers(state, payload) == []
        assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payload', [{}, {'graveyard_owner': 99}, {'graveyard_owner': 1}])
def test_missing_real_resolution_context_rejected_before_any_mutation(seat, payload):
    state, _, _, _, _ = start(seat, 'discard')
    before = snap(state)
    with pytest.raises(ValueError):
        shuffle_graveyard_into_library(state, seat, payload)
    assert snap(state) == before
