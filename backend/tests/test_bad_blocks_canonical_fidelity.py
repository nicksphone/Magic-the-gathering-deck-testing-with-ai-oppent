"""Qualify the existing dominated-chump metric, not general blocking quality.

Full pinned printed cards use declared old boards; outcomes use checked priority
actions. These fixtures do not claim paid creature births or AI strength.
"""
from copy import deepcopy

import pytest

from analytics.decision_quality import _validated_bad_blocks, build_trace_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_ai_terminal_draw_product import raw
from tests.test_task23_canonical_block_outcomes import (
    CARDS, blocked, position as deathtouch_position,
)
from tests.vraska_full.test_full_vraska import bare, add, act, Step, Zone


def position(defender, attacker_name='rumbling-baloth', blocker_name='grizzly-bears',
             *, life=20, hidden_order=('grizzly-bears', 'lightning-bolt')):
    root = bare(3 - defender)
    root.step = Step.DECLARE_ATTACKERS
    root.mechanic_choice_players = {1, 2}
    root.players[defender].life = life
    for player in root.players.values():
        player.mana_pool = {}
    attacker = add(root, raw(attacker_name), 3 - defender, Zone.BATTLEFIELD, old_board=True)
    printed = CARDS['Thalia, Guardian of Thraben'] if blocker_name == 'thalia' else raw(blocker_name)
    blocker = add(root, printed, defender, Zone.BATTLEFIELD, old_board=True)
    for name in hidden_order:
        add(root, raw(name), 3 - defender, Zone.HAND)
    root = act(root, 3 - defender, {'type': 'attack', 'attackers': [attacker.id],
               'attack_targets': {attacker.id: 'player:' + str(defender)}})
    for _ in range(40):
        if root.step == Step.DECLARE_BLOCKERS and root.priority_player == defender:
            break
        root = act(root, root.priority_player, {'type': 'pass_priority'})
    assert root.step == Step.DECLARE_BLOCKERS and root.priority_player == defender
    assert not root.stack and root.winner is None
    return root, attacker.id, blocker.id


def measured(root, defender, action):
    before = serialize_match_snapshot(root)
    request = deepcopy(action)
    rng = root.rng.getstate()
    value = _validated_bad_blocks(root, defender, action)
    payload = build_trace_payload(root, defender, RulesEngine().legal_moves(root, defender), action)
    assert payload['bad_blocks'] == value
    assert serialize_match_snapshot(root) == before
    assert root.rng.getstate() == rng and action == request
    restored = deserialize_match_snapshot(before)
    assert _validated_bad_blocks(restored, defender, action) == value
    return value


@pytest.mark.parametrize('defender', [1, 2])
@pytest.mark.parametrize('attacker_name,blocker_name,life,expected,attacker_zone,blocker_zone', [
    ('rumbling-baloth', 'grizzly-bears', 20, 1, Zone.BATTLEFIELD, Zone.GRAVEYARD),
    ('rumbling-baloth', 'grizzly-bears', 4, 0, Zone.BATTLEFIELD, Zone.GRAVEYARD),
    ('grizzly-bears', 'grizzly-bears', 20, 0, Zone.GRAVEYARD, Zone.GRAVEYARD),
    ('grizzly-bears', 'thalia', 20, 0, Zone.GRAVEYARD, Zone.BATTLEFIELD),
    ('rumbling-baloth', 'darksteel-sentinel', 20, 0, Zone.BATTLEFIELD, Zone.BATTLEFIELD),
])
def test_counter_agrees_with_independent_checked_combat(
        defender, attacker_name, blocker_name, life, expected, attacker_zone, blocker_zone):
    root, attacker, blocker = position(defender, attacker_name, blocker_name, life=life)
    action = {'type': 'block', 'blocks': {attacker: [blocker]}}
    chosen = blocked(root, defender, attacker, [blocker])
    no_block = blocked(root, defender, attacker, [])
    assert chosen.cards[attacker].zone == attacker_zone
    assert chosen.cards[blocker].zone == blocker_zone
    assert chosen.players[defender].life == life and chosen.winner is None
    assert (no_block.winner == 3 - defender) is (life == 4)
    assert measured(root, defender, action) == expected


@pytest.mark.parametrize('defender', [1, 2])
def test_no_block_and_non_block_actions_do_not_invent_losing_blocks(defender):
    root, _, _ = position(defender)
    assert measured(root, defender, {'type': 'block', 'blocks': {}}) == 0
    assert measured(root, defender, {'type': 'pass_priority'}) == 0


@pytest.mark.parametrize('defender', [1, 2])
def test_valid_legacy_single_id_block_matches_list_form(defender):
    root, attacker, blocker = position(defender)
    assert measured(root, defender, {'type': 'block', 'blocks': {attacker: blocker}}) == 1


@pytest.mark.parametrize('defender', [1, 2])
def test_private_hand_identity_permutation_does_not_change_metric(defender):
    roots = [position(defender, hidden_order=order) for order in (
        ('grizzly-bears', 'lightning-bolt'), ('lightning-bolt', 'grizzly-bears'))]
    assert roots[0][0].next_object_id == roots[1][0].next_object_id
    assert [root.cards[root.players[3 - defender].hand[0]].name for root, _, _ in roots] == [
        'Grizzly Bears', 'Lightning Bolt']
    assert [measured(root, defender, {'type': 'block', 'blocks': {attacker: [blocker]}})
            for root, attacker, blocker in roots] == [1, 1]


@pytest.mark.parametrize('defender', [1, 2])
def test_unresolved_native_damage_choice_remains_unavailable(defender):
    root, attacker, cheap, _, _ = deathtouch_position(defender, trample=True)
    chosen = blocked(root, defender, attacker, [cheap])
    assert chosen.players[defender].life == 14
    assert chosen.cards[cheap].zone == Zone.GRAVEYARD
    # The existing bounded observer does not answer native damage-allocation choices.
    assert measured(root, defender, {'type': 'block', 'blocks': {attacker: [cheap]}}) is None


@pytest.mark.parametrize('defender', [1, 2])
@pytest.mark.parametrize('invalid', [
    'wrong_priority', 'already_declared', 'missing_blocker', 'missing_attacker',
    'duplicate', 'tapped', 'flying_attacker',
])
def test_inadmissible_or_unresolved_measurement_is_not_zero(defender, invalid):
    root, attacker, blocker = position(defender)
    action = {'type': 'block', 'blocks': {attacker: [blocker]}}
    if invalid == 'wrong_priority':
        root.priority_player = 3 - defender
    elif invalid == 'already_declared':
        root.blockers_declared = True
    elif invalid == 'missing_blocker':
        action['blocks'][attacker] = ['absent-blocker']
    elif invalid == 'missing_attacker':
        action['blocks'] = {'absent-attacker': [blocker]}
    elif invalid == 'duplicate':
        action['blocks'][attacker] = [blocker, blocker]
    elif invalid == 'tapped':
        root.cards[blocker].tapped = True
    else:
        add_keyword_effect(root, attacker, ['flying'])
    assert measured(root, defender, action) is None
