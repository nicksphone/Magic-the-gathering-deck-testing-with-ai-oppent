"""Printed planeswalker costs use the same resumable counter event as effects."""
import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_counter_prohibitions import source as permanent
from tests.test_counter_replacements import choose, source as modifier
from tests.test_restricted_mana import clean
from tests.test_ward_resolution import add


def activate(state, walker, index=0):
    return checked_action(state, RulesEngine(), 1, {
        'type': 'activate_loyalty', 'card_id': walker.id, 'ability_index': index,
    })


@pytest.mark.parametrize('name,controller,expected', [
    ('Doubling Season', 1, 5),
    ('Vorinclex, Monstrous Raider', 1, 6),
    ('Vorinclex, Monstrous Raider', 2, 4),
    ("Lae'zel, Vlaakith's Champion", 1, 6),
    ('Winding Constrictor', 1, 5),
])
def test_positive_loyalty_cost_is_not_initially_an_effect(name, controller, expected):
    state = clean()
    walker = permanent(state, "Elspeth, Sun's Champion")
    modifier(state, name, controller)
    state = activate(state, walker)
    assert state.cards[walker.id].loyalty == expected
    assert len(state.stack) == 1 and not state.pending_replacement_choice
    assert walker.id in state.loyalty_activated_this_turn
    assert state.priority_player == 1 and not state.trigger_staging
    # A replacement reducing the +1 cost to zero still pays that cost.
    resolve_top_of_stack(state)
    assert len([cid for cid in state.players[1].battlefield if state.cards[cid].is_token]) == (6 if name == 'Doubling Season' else 3)


@pytest.mark.parametrize('name', ['Doubling Season', 'Vorinclex, Monstrous Raider', "Lae'zel, Vlaakith's Champion"])
def test_negative_cost_is_removal_not_counter_placement(name):
    state = clean()
    walker = permanent(state, "Elspeth, Sun's Champion")
    modifier(state, name)
    state = activate(state, walker, 1)
    assert state.cards[walker.id].loyalty == 1
    assert len(state.stack) == 1 and not state.pending_replacement_choice


def test_replacement_makes_cost_eligible_for_effect_only_doubling():
    state = clean()
    walker = permanent(state, "Elspeth, Sun's Champion")
    modifier(state, 'Doubling Season')
    modifier(state, 'Vorinclex, Monstrous Raider')
    state = activate(state, walker)
    assert state.cards[walker.id].loyalty == 8
    assert len(state.stack) == 1 and not state.pending_replacement_choice


@pytest.mark.parametrize('first,expected', [('add', 12), ('double', 9)])
def test_cost_choice_resume_announces_and_pays_exactly_once(first, expected):
    state = clean()
    walker = permanent(state, "Elspeth, Sun's Champion")
    modifier(state, 'Doubling Season')
    modifier(state, 'Vorinclex, Monstrous Raider')
    modifier(state, "Lae'zel, Vlaakith's Champion")
    state = activate(state, walker)
    assert state.cards[walker.id].loyalty == 4
    assert len(state.stack) == 1 and state.trigger_staging
    assert state.pending_replacement_choice['activation_controller'] == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, first)
    if state.pending_replacement_choice:
        assert state.pending_replacement_choice['activation_controller'] == 1
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = choose(state, 'double')
    assert state.cards[walker.id].loyalty == expected
    assert len(state.stack) == 1 and not state.trigger_staging
    assert state.priority_player == 1
    with pytest.raises(ActionRejected):
        activate(state, state.cards[walker.id])
    resolve_top_of_stack(state)
    assert len([cid for cid in state.players[1].battlefield if state.cards[cid].is_token]) == 6


def test_target_ward_waits_until_positive_cost_is_fully_paid():
    from card_data.fallback_cards import fallback_card_payload
    from tests.test_ai_recurring_engines import add as add_card
    state = clean(2)
    raw = {'power': None, 'toughness': None, 'keywords': [], 'colors': [],
           **fallback_card_payload('Ugin, the Spirit Dragon')}
    walker = add_card(state, raw['name'], 2, cards={raw['name']: raw})
    walker.loyalty = int(raw['loyalty'])
    target = add(state, 'Tolarian Terror', 1)
    modifier(state, 'Doubling Season', 2)
    modifier(state, 'Vorinclex, Monstrous Raider', 2)
    modifier(state, "Lae'zel, Vlaakith's Champion", 2)
    state = checked_action(state, RulesEngine(), 2, {
        'type': 'activate_loyalty', 'card_id': walker.id, 'ability_index': 0,
        'targets': {'target_card_id': target.id},
    })
    assert len(state.stack) == 1 and state.staged_triggers
    assert state.cards[walker.id].loyalty == 7
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'add', 2)
    state = choose(state, 'double', 2)
    assert state.cards[walker.id].loyalty == 19
    assert len(state.stack) == 2 and state.stack[-1].effect_key == 'ward_payment'
    assert not state.trigger_staging and not state.staged_triggers
    assert state.priority_player == 2
