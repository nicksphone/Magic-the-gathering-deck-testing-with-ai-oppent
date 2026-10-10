"""Complete canonical paid actions; seeded boards are not earned gameplay."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.loyalty_instructions import card_reference
from test_soulless_jailer_action_goldens import (
    board, cast, history, rejected, resolve_top, seed,
)
from test_soulless_jailer_query_contract import rows
from test_soulless_jailer_typed_query import extra_rows


@pytest.fixture(scope='module')
def cremate():
    raw = (Path(__file__).parent / 'fixtures/kozilek_trigger_audit/cremate.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        '1c3e8c658013778a3930a61fda2ca9a4a3d8fe4b9f547f23079f73d80e61b481')
    return json.loads(raw)


@pytest.mark.parametrize('seat', (1, 2))
def test_paid_reanimate_cage_blocks_entry_not_independent_life_loss(extra_rows, history, seat):
    state = board(seat)
    cage = seed(state, extra_rows["Grafdigger's Cage"], 3 - seat, Zone.BATTLEFIELD)
    target = seed(state, extra_rows['Gravecrawler'], seat, Zone.GRAVEYARD)
    spell = seed(state, history['Reanimate'], seat, Zone.HAND)
    reference = card_reference(state, target)
    state = cast(state, seat, spell, targets={'target_card_id': target})
    assert state.stack[-1].payload['lose_life_equal_to_mana_value'] is True
    assert state.stack[-1].payload['mana_spent'] == 1
    assert state.players[seat].life == 20
    mana = deepcopy(state.players[seat].mana_pool)
    state = resolve_top(state)
    assert state.players[seat].life == 19
    assert state.players[3 - seat].life == 20
    assert state.players[seat].mana_pool == mana
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert card_reference(state, target) == reference
    assert state.players[seat].graveyard.count(target) == 1
    assert state.cards[cage].zone == Zone.BATTLEFIELD
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert not state.stack and state.pending_mechanic_choice is None
    assert state.pending_replacement_choice is None
    assert state.cards[target].oracle_text == extra_rows['Gravecrawler']['oracle_text']


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('blocked', (False, True))
def test_paid_reanimate_full_mana_value_eight_once(rows, history, seat, blocked):
    state = board(seat)
    if blocked:
        seed(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    target = seed(state, history['Griselbrand'], seat, Zone.GRAVEYARD)
    spell = seed(state, history['Reanimate'], seat, Zone.HAND)
    reference = card_reference(state, target)
    state = cast(state, seat, spell, targets={'target_card_id': target})
    assert state.stack[-1].payload['lose_life_equal_to_mana_value'] is True
    assert state.stack[-1].payload['mana_spent'] == 1
    assert state.players[seat].life == 20
    mana = deepcopy(state.players[seat].mana_pool)
    state = resolve_top(state)
    assert state.players[seat].life == 12
    assert state.players[3 - seat].life == 20
    assert state.players[seat].mana_pool == mana
    assert state.cards[target].zone == (Zone.GRAVEYARD if blocked else Zone.BATTLEFIELD)
    assert state.cards[target].zone_change_sequence == reference['sequence'] + (0 if blocked else 1)
    assert state.players[seat].graveyard.count(target) == int(blocked)
    assert state.players[seat].battlefield.count(target) == int(not blocked)
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert not state.stack and state.pending_mechanic_choice is None
    assert state.pending_replacement_choice is None
    assert state.cards[target].oracle_text == history['Griselbrand']['oracle_text']


@pytest.mark.parametrize('seat', (1, 2))
def test_paid_exile_response_fizzles_whole_reanimate_without_life_loss(
        extra_rows, history, cremate, seat):
    state = board(seat)
    target = seed(state, extra_rows['Gravecrawler'], seat, Zone.GRAVEYARD)
    spell = seed(state, history['Reanimate'], seat, Zone.HAND)
    response = seed(state, cremate, seat, Zone.HAND)
    drawn = seed(state, extra_rows['Forest'], seat, Zone.LIBRARY)
    reference = card_reference(state, target)
    state = cast(state, seat, spell, targets={'target_card_id': target})
    assert state.stack[-1].payload['mana_spent'] == 1
    retained = asdict(state.stack[-1])
    state = cast(state, seat, response, targets={'target_card_id': target})
    assert state.stack[-1].payload['mana_spent'] == 1
    assert asdict(state.stack[-2]) == retained
    state = resolve_top(state)
    assert state.cards[target].zone == Zone.EXILE
    assert target in state.players[seat].exile
    assert target not in state.players[seat].graveyard
    assert state.cards[target].zone_change_sequence == reference['sequence'] + 1
    assert drawn in state.players[seat].hand
    assert asdict(state.stack[-1]) == retained
    assert state.players[seat].life == 20
    mana = deepcopy(state.players[seat].mana_pool)
    state = resolve_top(state)
    assert state.players[seat].life == state.players[3 - seat].life == 20
    assert state.players[seat].mana_pool == mana
    assert state.cards[target].zone == Zone.EXILE
    assert target not in state.players[seat].battlefield
    assert state.cards[spell].zone == state.cards[response].zone == Zone.GRAVEYARD
    assert not state.stack and state.pending_mechanic_choice is None
    assert state.pending_replacement_choice is None


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('invalid', ('absent', 'noncreature'))
def test_invalid_reanimate_target_rejects_before_payment(extra_rows, history, seat, invalid):
    state = board(seat)
    target = seed(state, extra_rows['Forest'], seat, Zone.GRAVEYARD)
    spell = seed(state, history['Reanimate'], seat, Zone.HAND)
    chosen = 'absent-target' if invalid == 'absent' else target
    mana = deepcopy(state.players[seat].mana_pool)
    rejected(state, seat, {'type': 'cast_spell', 'card_id': spell,
                           'targets': {'target_card_id': chosen}})
    assert state.players[seat].life == state.players[3 - seat].life == 20
    assert state.players[seat].mana_pool == mana
    assert state.cards[spell].zone == Zone.HAND
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert not state.stack and state.pending_mechanic_choice is None
