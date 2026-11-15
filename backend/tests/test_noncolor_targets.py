"""Native nonblack admission and supported live-color response behavior."""
from copy import deepcopy
import json

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.cast_choice import build_cast_hints
from rules_engine.colors import card_color_symbols
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_target_restrictions
from rules_engine.query_context import rule_query_scope
from tests.pending_permanent_fullraw import raw_card as canonical_row
from tests.test_ai_hybrid_cast_choices import canonical as canonical_seed_row
from tests.test_basic_land_layer_goldens import position
from tests.test_color_domain_audit import convert, reanimate
from tests.test_linked_damage_targets import raw_card


def add(state, name, seat, zone):
    row = canonical_seed_row(name) if name == 'Bloodtithe Harvester' else canonical_row(name)
    card = raw_card(state, row, seat, zone)
    assert card.oracle_text == row['oracle_text'] and card.colors == row['colors']
    if name == 'Doom Blade':
        assert card.oracle_text == 'Destroy target nonblack creature.'
    return card.id


def act(state, seat, action):
    before, rng = serialize_match_snapshot(state), state.rng.getstate()
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before and state.rng.getstate() == rng
    return result


def restore(state, enabled):
    before = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(json.loads(json.dumps(before))) if enabled else state
    assert serialize_match_snapshot(result) == before
    return result


def finish_top(state):
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    return state


def cast(state, seat, spell, target):
    return act(state, seat, {'type': 'cast_spell', 'card_id': spell,
        'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': target}})


def hints_and_moves(state, spell, seat):
    before, rng = serialize_match_snapshot(state), state.rng.getstate()
    with rule_query_scope(state):
        hints = build_cast_hints(state, state.cards[spell], seat)
        moves = RulesEngine().legal_moves(state, seat)
    assert serialize_match_snapshot(state) == before and state.rng.getstate() == rng
    return hints, moves


def ordinary(seat, name):
    state = position(seat)
    spell = add(state, 'Doom Blade', seat, Zone.HAND)
    target = add(state, name, 3-seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'B': 1, 'C': 1}
    return state, spell, target


def mixed(seat, restored):
    state, spell, mono = ordinary(seat, 'Blood Artist')
    multi = add(state, 'Bloodtithe Harvester', 3-seat, Zone.BATTLEFIELD)
    sprite = add(state, 'Sprite Dragon', 3-seat, Zone.BATTLEFIELD)
    myr = add(state, 'Darksteel Myr', 3-seat, Zone.BATTLEFIELD)
    return restore(state, restored), spell, mono, multi, sprite, myr


def converted(seat):
    state = position(seat)
    target = add(state, 'Blood Artist', seat, Zone.BATTLEFIELD)
    assert card_color_symbols(state.cards[target], state) == {'B'}
    state = reanimate(convert(state, target, seat), target, seat)
    assert state.cards[target].colors == ['B']
    assert card_color_symbols(state.cards[target], state) == set()
    song = next(card.id for card in state.cards.values()
                if card.name == 'Song of the Dryads' and card.attached_to == target)
    spell = add(state, 'Doom Blade', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'B': 1, 'C': 1}
    state = act(state, seat, {'type': 'pass_priority'})
    assert state.priority_player == 3-seat
    return state, spell, target, song


@pytest.mark.parametrize('seat', [1, 2])
def test_native_nonblack_spell_pays_and_destroys_the_announced_creature(seat):
    state, spell, target = ordinary(seat, 'Sprite Dragon')
    assert card_color_symbols(state.cards[target], state) == {'U', 'R'}
    paid = cast(state, seat, spell, target)
    assert paid.stack[-1].payload['mana_spent'] == 2
    assert sum(paid.players[seat].mana_pool.values()) == 0
    done = finish_top(restore(paid, True))
    assert not done.stack and done.cards[spell].zone == done.cards[target].zone == Zone.GRAVEYARD
    assert done.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['mono', 'multi'])
@pytest.mark.parametrize('restored', [False, True])
def test_black_creature_rejects_without_payment_or_caller_mutation(seat, kind, restored):
    state, spell, target = ordinary(seat, 'Blood Artist' if kind == 'mono' else 'Bloodtithe Harvester')
    state = restore(state, restored)
    assert 'B' in card_color_symbols(state.cards[target], state)
    before, rng = serialize_match_snapshot(state), state.rng.getstate()
    rejected = False
    try:
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell,
            'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': target}})
    except ActionRejected:
        rejected = True
    assert rejected
    assert serialize_match_snapshot(state) == before and state.rng.getstate() == rng
    hints, moves = hints_and_moves(state, spell, seat)
    assert target not in {x['id'] for x in hints.get('creature_targets', [])}
    assert not any(move.get('card_id') == spell and move['type'] == 'cast_spell' for move in moves)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
def test_colorless_indestructible_creature_remains_a_legal_human_target(seat, restored):
    state, spell, target = ordinary(seat, 'Darksteel Myr')
    state = restore(state, restored)
    assert card_color_symbols(state.cards[target], state) == set()
    hints, _ = hints_and_moves(state, spell, seat)
    assert target in {x['id'] for x in hints['creature_targets']}
    state = cast(state, seat, spell, target)
    assert state.stack[-1].payload['mana_spent'] == 2
    state = finish_top(restore(state, restored))
    assert not state.stack and state.cards[spell].zone == Zone.GRAVEYARD
    assert state.cards[target].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
def test_mixed_board_hints_keep_exact_nonblack_targets_without_query_mutation(seat, restored):
    state, spell, mono, multi, sprite, myr = mixed(seat, restored)
    for _ in range(2):
        hints, moves = hints_and_moves(state, spell, seat)
        assert {x['id'] for x in hints['creature_targets']} == {sprite, myr}
        assert hints['target_restrictions']['exclude_colors'] == ['black']
        move = next(move for move in moves if move.get('card_id') == spell and move['type'] == 'cast_spell')
        assert {x['id'] for x in move['target_hints']['creature_targets']} == {sprite, myr}
    assert {mono, multi}.isdisjoint({x['id'] for x in hints['creature_targets']})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
def test_actual_materializer_pays_for_the_productive_legal_nonblack_target(seat, restored):
    state, spell, mono, multi, sprite, myr = mixed(seat, restored)
    _, moves = hints_and_moves(state, spell, seat)
    move = next(move for move in moves if move.get('card_id') == spell and move['type'] == 'cast_spell')
    original, before, rng = deepcopy(move), serialize_match_snapshot(state), state.rng.getstate()
    action = AIAgent(difficulty='master', archetype='Control')._materialize_action(state, move, seat)
    assert action['targets']['target_card_id'] == sprite
    assert not action.get('_invalid_ai_choice')
    assert move == original and serialize_match_snapshot(state) == before and state.rng.getstate() == rng
    paid = act(state, seat, action)
    assert paid.stack[-1].payload['mana_spent'] == 2
    done = finish_top(restore(paid, restored))
    assert done.cards[sprite].zone == Zone.GRAVEYARD
    assert all(done.cards[cid].zone == Zone.BATTLEFIELD for cid in (mono, multi, myr))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
def test_supported_conversion_makes_printed_black_creature_a_legal_colorless_target(seat, restored):
    state, spell, target, _ = converted(seat)
    state = restore(state, restored)
    hints, _ = hints_and_moves(state, spell, 3-seat)
    assert target in {x['id'] for x in hints['creature_targets']}
    paid = cast(state, 3-seat, spell, target)
    assert paid.stack[-1].payload['mana_spent'] == 2
    done = finish_top(restore(paid, restored))
    assert not done.stack and done.cards[spell].zone == done.cards[target].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restored', [False, True])
def test_real_response_restores_black_and_same_object_target_makes_doom_fail_to_resolve(seat, restored):
    state, spell, target, song = converted(seat)
    response = add(state, 'Naturalize', seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'C': 1}
    identity = (object_incarnation(state.cards[target]), state.cards[target].zone_change_sequence)
    state = cast(state, 3-seat, spell, target)
    state = restore(state, restored)
    state = act(state, 3-seat, {'type': 'pass_priority'})
    assert state.priority_player == seat
    state = cast(state, seat, response, song)
    assert state.stack[-1].payload['mana_spent'] == 2
    state = finish_top(state)
    assert len(state.stack) == 1 and state.stack[0].source_card_id == spell
    assert state.cards[song].zone == Zone.GRAVEYARD
    assert card_color_symbols(state.cards[target], state) == {'B'}
    assert (object_incarnation(state.cards[target]), state.cards[target].zone_change_sequence) == identity
    state = restore(state, restored)
    done = finish_top(state)
    assert not done.stack and done.cards[spell].zone == Zone.GRAVEYARD
    assert done.cards[target].zone == Zone.BATTLEFIELD
    assert done.players[1].life == done.players[2].life == 20


@pytest.mark.parametrize('color', ['white', 'blue', 'black', 'red', 'green'])
def test_literal_single_creature_noncolor_grammar_is_reusable_not_a_card_name_policy(color):
    # Standalone instruction diagnostic, not fabricated canonical card facts.
    assert infer_target_restrictions(None, f'Destroy target non{color} creature.', 1) == {
        'allowed_types': ['Creature'], 'exclude_colors': [color]}


@pytest.mark.parametrize('case', ['unrelated', 'artifact', 'union', 'comma-union', 'unknown'])
def test_diagnostic_unrelated_unknown_and_compound_domains_are_not_promoted(case):
    # These protocol strings do not establish support for additional card bodies.
    text = {
        'unrelated': 'Nonblack creatures get +1/+1. Destroy target creature.',
        'artifact': 'Destroy target nonblack artifact.',
        'union': 'Destroy target nonblack creature or planeswalker.',
        'comma-union': 'Destroy target nonblack creature, artifact, or enchantment.',
        'unknown': 'Destroy target noncyan creature.',
    }[case]
    assert 'exclude_colors' not in infer_target_restrictions(None, text, 1)
