"""A genuine resolved type grant survives transforming, but is not copied."""
import pytest

from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.card_faces import apply_transform_face
from rules_engine.copiable_values import values
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.type_effects import effective_types
from tests.graveyard_batch_native_support_bf62 import choose, place, snapshot
from tests.test_entry_copy_native_936 import cast, position


@pytest.mark.parametrize('seat', [1, 2])
def test_resolved_coating_before_real_face_transition_never_becomes_copiable(seat):
    names = ['Delver of Secrets // Insectile Aberration', 'Liquimetal Coating', 'Sculpting Steel']
    state = position(names, names, seat)
    target = next(c.id for c in state.cards.values() if c.owner == seat and c.card_faces)
    target = place(state, state.cards[target].name, Zone.BATTLEFIELD, seat)
    coating = place(state, 'Liquimetal Coating', Zone.BATTLEFIELD, seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': coating, 'ability_index': 0, 'targets': {'target_card_id': target}})
    assert resolve_top_of_stack(state) and 'Artifact' in effective_types(state, target)
    # Existing face-transition producer, not a claim of Delver upkeep resolution.
    apply_transform_face(state.cards[target], 1)
    assert state.cards[target].name == 'Insectile Aberration'
    assert 'Artifact' in effective_types(state, target)
    assert 'Artifact' not in values(state.cards[target])['types']
    state, steel = cast(snapshot(state), seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    assert target in state.pending_mechanic_choice['options']
    state = choose(snapshot(state), seat, target)
    assert state.cards[steel].name == 'Insectile Aberration'
    assert 'Artifact' not in effective_types(state, steel)
    assert state.cards[steel].card_faces == [] and state.cards[steel].owner == seat
    assert 'Artifact' in effective_types(state, target)
