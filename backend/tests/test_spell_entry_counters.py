"""Canonical entry fixtures; named counters and zone moves are core-state setups."""
import json
from pathlib import Path
import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.continuous import effective_combat_stats
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from tests.test_ai_recurring_engines import add as add_card
from tests.test_counter_prohibitions import source as permanent
from tests.test_counter_replacements import source as modifier, choose
from tests.test_restricted_mana import clean
from tests.test_saga_counter_events import saga


ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/spell_entry_counters.json').read_text())}


def spell(state, card, **payload):
    state.players[card.controller].battlefield.remove(card.id)
    card.move_to_zone(Zone.STACK)
    add_to_stack(state, card.id, card.controller, card.name, 'noop', payload)
    resolve_top_of_stack(state)


@pytest.mark.parametrize('name,controller,expected', [
    ('Doubling Season', 1, 8), ('Vorinclex, Monstrous Raider', 1, 8),
    ('Vorinclex, Monstrous Raider', 2, 2), ("Lae'zel, Vlaakith's Champion", 1, 5),
    ('Winding Constrictor', 1, 4), ('Solemnity', 1, 4),
])
def test_initial_loyalty_is_a_replaced_entry_counter_event(name, controller, expected):
    state = clean()
    card = permanent(state, "Elspeth, Sun's Champion")
    (permanent if name == 'Solemnity' else modifier)(state, name, controller)
    spell(state, card)
    assert card.zone == Zone.BATTLEFIELD and card.loyalty == expected
    assert card.printed_characteristics['loyalty'] == 4


@pytest.mark.parametrize('name,expected', [('Doubling Season', 2), ('Vorinclex, Monstrous Raider', 2), ('Solemnity', 0)])
def test_intrinsic_saga_lore_on_entry_triggers_crossed_chapters(name, expected):
    state = clean()
    card = saga(state)
    (permanent if name == 'Solemnity' else modifier)(state, name)
    spell(state, card)
    assert card.zone == Zone.BATTLEFIELD and card.counters.get('__lore', 0) == expected
    assert sorted(item.payload['__chapter_number'] for item in state.stack) == list(range(1, expected+1))


@pytest.mark.parametrize('first,expected', [('add', 20), ('double', 18)])
def test_competing_entry_modifiers_pause_off_battlefield_and_resume_once(first, expected):
    state = clean()
    card = permanent(state, "Elspeth, Sun's Champion")
    for name in ('Doubling Season', 'Vorinclex, Monstrous Raider', "Lae'zel, Vlaakith's Champion"):
        modifier(state, name)
    spell(state, card)
    assert card.zone == Zone.STACK and card.id not in state.players[1].battlefield
    assert state.pending_replacement_choice['counter_effect'] == 'permanent_spell_entry'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, first)
    while state.pending_replacement_choice:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = choose(state, 'double' if first == 'add' else 'add')
    assert state.cards[card.id].loyalty == expected
    assert state.players[1].battlefield.count(card.id) == 1
    assert sum(line == f'{card.name} resolves.' for line in state.log) == 1


def test_x_and_one_shot_entry_counters_form_one_supported_same_kind_event():
    state = clean()
    card = add_card(state, 'Walking Ballista', cards=ROWS)
    state.pending_entry_counters = [{'controller': 1, 'counter': '+1/+1', 'amount': 1, 'expires_turn': state.turn}]
    modifier(state, 'Doubling Season')
    constrictor = modifier(state, 'Winding Constrictor')
    spell(state, card, x_value=2)
    assert card.zone == Zone.STACK and state.pending_entry_counters
    packet = serialize_match_snapshot(state)['pending_entry_counters']
    for role in ('one_shot', 'intrinsic', 'constrictor'):
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        assert state.cards[card.id].zone == Zone.STACK
        assert state.cards[card.id].counters.get('+1/+1', 0) == 0
        assert state.pending_entry_counters == packet
        before = serialize_match_snapshot(state)
        option = next(o for o in state.pending_replacement_choice['options'] if (
            o.get('next_entry_producer') if role == 'one_shot' else
            o.get('intrinsic_entry') if role == 'intrinsic' else
            o['operation'] == 'add' and not o.get('entry_producer')
            and o.get('source_card_id') == constrictor.id))
        updated = checked_action(state, RulesEngine(), 1, {
            'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
        assert serialize_match_snapshot(state) == before
        state = updated
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].counters['+1/+1'] == 8
    assert effective_combat_stats(state, card.id) == (8, 8)
    assert not state.pending_entry_counters


def test_blocked_zero_zero_entry_dies_only_after_it_enters():
    state = clean()
    card = add_card(state, 'Walking Ballista', cards=ROWS)
    permanent(state, 'Solemnity')
    spell(state, card, x_value=4)
    assert card.zone == Zone.GRAVEYARD and card.id in state.players[1].graveyard


def test_incoming_self_counter_ban_applies_before_entry():
    state = clean()
    card = permanent(state, 'Tatterkite')
    modifier(state, 'Doubling Season')
    state.pending_entry_counters = [{'controller': 1, 'counter': '+1/+1', 'amount': 2, 'expires_turn': state.turn}]
    spell(state, card)
    assert card.zone == Zone.BATTLEFIELD and '+1/+1' not in card.counters
    assert not state.pending_replacement_choice


def test_incoming_global_modifier_does_not_double_its_own_entry():
    state = clean()
    card = modifier(state, 'Vorinclex, Monstrous Raider')
    state.pending_entry_counters = [{'controller': 1, 'counter': '+1/+1', 'amount': 1, 'expires_turn': state.turn}]
    spell(state, card)
    assert card.counters['+1/+1'] == 1


@pytest.mark.parametrize('chosen,expected', [('1', [2]), ('2', []), ('3', [])])
def test_read_ahead_choice_survives_snapshot_and_requires_exact_replaced_lore(chosen, expected):
    state = clean(2)
    card = add_card(state, 'The Phasing of Zhalfir', 2, cards=ROWS)
    modifier(state, 'Doubling Season', 2)
    spell(state, card)
    assert card.zone == Zone.STACK and state.pending_mechanic_choice['kind'] == 'saga_entry'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 2, {'type': 'choose_mechanic', 'choice_id': chosen})
    assert sorted(item.payload['__chapter_number'] for item in state.stack) == expected
    if expected:
        assert state.cards[card.id].zone == Zone.BATTLEFIELD
        assert state.cards[card.id].counters['__lore'] == int(chosen)*2
    else:
        assert state.cards[card.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('entry_turn,expected', [(True, [2]), (False, [1, 2])])
def test_read_ahead_restriction_applies_to_later_counter_events_only_on_entry_turn(entry_turn, expected):
    from rules_engine.counter_placement import put_counters
    state = clean()
    card = add_card(state, 'The Phasing of Zhalfir', cards=ROWS)
    card.entered_turn = state.turn if entry_turn else state.turn - 1
    card.counters['__lore'] = 0
    put_counters(state, 'lore', 2, target_card_id=card.id)
    assert sorted(item.payload['__chapter_number'] for item in state.stack) == expected


def test_invalid_read_ahead_choice_preserves_original_state():
    state = clean()
    card = add_card(state, 'The Phasing of Zhalfir', cards=ROWS)
    spell(state, card)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'choose_mechanic', 'choice_id': '4'})
    assert serialize_match_snapshot(state) == before


def test_ai_executes_legal_value_preserving_read_ahead_choice_with_explicit_gaps():
    from ai.agent import AIAgent
    from rules_engine.coverage import known_unsupported_mechanics
    from rules_engine.move_generator import legal_moves
    state = clean(2)
    card = add_card(state, 'The Phasing of Zhalfir', 2, cards=ROWS)
    spell(state, card)
    decision = AIAgent('master').choose_action(state, legal_moves(state, 2), 2)
    assert decision.action['choice_id'] == '1'
    state = checked_action(state, RulesEngine(), 2, decision.action)
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].counters['__lore'] == 1
    gaps = known_unsupported_mechanics(card.oracle_text)
    assert 'phasing' in gaps and 'read ahead entry route fidelity' in gaps
