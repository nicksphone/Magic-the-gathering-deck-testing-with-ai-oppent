"""Exact generic creature clause; no partial admission of unknown card text."""
import pytest

from rules_engine.closed_loyalty import compile_body, compile_instruction
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind
from tests.loyalty_destruction_diagnostic_support import source
from tests.test_ineffective_destruction import settled_state
from tests.test_pending_removal import add_card
from tests.test_self_removal import canonical_cards


def test_exact_creature_destroy_compiles_to_existing_native_destroy_handler():
    assert compile_instruction('Destroy target creature.') == [
        {'effect_key': 'destroy_permanent', 'instruction': 'Destroy target creature'}]
    abilities = compile_body('-3: Destroy target creature.', 'Diagnostic')
    assert abilities is not None and len(abilities['abilities']) == 1


@pytest.mark.parametrize('text', [
    'Destroy target creature. Then ignore all other rules.',
    'Destroy target creature unless its controller pays {2}.',
])
def test_creature_destroy_does_not_admit_an_unsupported_remainder(text):
    assert compile_instruction(text) is None
    assert compile_body('-3: ' + text, 'Diagnostic') is None


def position(seat):
    state, _, _ = settled_state()
    state.active_player = state.priority_player = seat
    walker = source(state, seat)
    walker.oracle_text = '-3: Destroy target creature.'
    victim = add_card(state, 'Sprite Dragon', Zone.BATTLEFIELD, 3-seat)
    return state, walker.id, victim.id


@pytest.mark.parametrize('seat', [1, 2])
def test_checked_creature_target_pays_source_loyalty_and_settles_both_seats(seat):
    state, walker, victim = position(seat)
    before = serialize_match_snapshot(state)
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m.get('card_id') == walker)
    assert move['target_hints']['target_restrictions']['allowed_types'] == ['Creature']
    assert victim in {r['id'] for r in move['target_hints']['creature_targets']}
    assert serialize_match_snapshot(state) == before
    branch = checked_action(state, RulesEngine(), seat, {'type': 'activate_loyalty',
        'card_id': walker, 'ability_index': 0, 'targets': {'target_card_id': victim}})
    assert serialize_match_snapshot(state) == before
    assert branch.cards[walker].loyalty == 2 and walker in branch.loyalty_activated_this_turn
    assert branch.stack[-1].source_card_id == walker
    assert stack_object_kind(branch, branch.stack[-1]) == 'activated'
    while branch.stack:
        branch = checked_action(branch, RulesEngine(), branch.priority_player, {'type': 'pass_priority'})
    assert branch.cards[victim].zone == Zone.GRAVEYARD
    assert victim in branch.players[3-seat].graveyard
    assert branch.cards[walker].zone == Zone.BATTLEFIELD and branch.cards[walker].loyalty == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['noncreature', 'unpayable_source'])
def test_wrong_target_or_unpayable_loyalty_is_rejected_atomically(seat, bad):
    state, walker, victim = position(seat)
    if bad == 'noncreature':
        victim = add_card(state, 'Bastion of Remembrance', Zone.BATTLEFIELD, 3-seat).id
    else:
        state.cards[walker].loyalty = 2
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'activate_loyalty',
            'card_id': walker, 'ability_index': 0, 'targets': {'target_card_id': victim}})
    assert serialize_match_snapshot(state) == before
