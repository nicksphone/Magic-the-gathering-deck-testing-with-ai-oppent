"""Canonical static combat clauses; board fixtures are not competitive decks."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine import combat
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.combat_constraints import combat_rule_view
from rules_engine.continuous import effective_power, continuous_layer_trace
from rules_engine.restrictions import card_cant_attack, card_cant_block
from tests.test_ai_recurring_engines import fixture, add as raw_add, resolve
from tests.test_ability_suppression import add as printed
from tests.test_api_input_contracts import game, persist, rejected

CARDS = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/conditional_combat.json').read_text())}


def add(state, name, player=1):
    card = raw_add(state, name, player, cards=CARDS)
    assign_static_order_on_battlefield_entry(state, card.id)
    card.summoning_sick = False
    return card


def lose(state, card):
    resolve_effect(state, 3-card.controller, 'temporary_ability_loss', {'target_card_id': card.id})


@pytest.mark.parametrize('player', [1, 2])
def test_attachment_restrictions_survive_recipient_loss_and_snapshot(player):
    state = fixture()
    creature = printed(state, 'Llanowar Elves', player)
    aura = add(state, 'Pacifism', 3-player)
    aura.attached_to = creature.id
    assert card_cant_attack(state, creature.id) and card_cant_block(state, creature.id)
    lose(state, creature)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert card_cant_attack(state, creature.id)
    trace = continuous_layer_trace(state, creature.id)
    assert trace['combat_constraints'][0]['source_id'] == aura.id
    assert not trace['unsupported_attachment_clauses']
    lose(state, state.cards[aura.id])
    assert not card_cant_attack(state, creature.id)


@pytest.mark.parametrize('player', [1, 2])
def test_bonds_otherwise_uses_recipient_type(player):
    state = fixture()
    human = add(state, 'Hinterland Drake', player)
    aura = add(state, 'Bonds of Faith', player)
    aura.attached_to = human.id
    assert card_cant_attack(state, human.id)
    # Explicit characteristic mutation tests the evaluator, not a fabricated card.
    human.type_line = 'Creature — Human'
    assert not card_cant_attack(state, human.id)
    assert effective_power(state, human.id) == human.power + 2


@pytest.mark.parametrize('player', [1, 2])
def test_counter_threshold_is_live_and_source_suppression_removes_it(player):
    state = fixture()
    dragon = add(state, 'Slumbering Dragon', player)
    for amount, prohibited in [(4, True), (5, False), (4, True)]:
        dragon.counters['+1/+1'] = amount
        assert card_cant_attack(state, dragon.id) == prohibited
        assert card_cant_block(state, dragon.id) == prohibited
    lose(state, dragon)
    assert not card_cant_attack(state, dragon.id)


@pytest.mark.parametrize('player', [1, 2])
def test_defending_and_global_land_conditions(player):
    state = fixture()
    sea = add(state, 'Sea Serpent', player)
    harbor = add(state, 'Harbor Serpent', player)
    assert card_cant_attack(state, sea.id) and card_cant_attack(state, harbor.id)
    # Existing canonical Island instances, not invented cards.
    for cid in state.players[3-player].library[:5]:
        land = state.cards[cid]
        land.name = 'Island'
        land.type_line = 'Basic Land — Island'
        state.players[3-player].library.remove(cid)
        land.move_to_zone(Zone.BATTLEFIELD)
        state.players[3-player].battlefield.append(cid)
    assert not card_cant_attack(state, sea.id)
    assert not card_cant_attack(state, harbor.id)


def test_power_restriction_uses_effective_not_printed_power():
    state = fixture()
    attacker = add(state, 'Steel Leaf Champion')
    blocker = printed(state, 'Llanowar Elves', 2)
    assert not combat._can_block_attacker(state, attacker, blocker)
    blocker.counters['+1/+1'] = 2
    assert combat._can_block_attacker(state, attacker, blocker)


def test_artifact_qualification_is_not_a_blanket_block_ban():
    state = fixture()
    blocker = add(state, 'Hinterland Drake', 2)
    attacker = add(state, 'Slumbering Dragon')
    assert not card_cant_block(state, blocker.id)
    assert combat._can_block_attacker(state, attacker, blocker)
    attacker.types.append('Artifact')  # synthetic characteristic-change boundary
    assert not combat._can_block_attacker(state, attacker, blocker)


@pytest.mark.parametrize('player', [1, 2])
def test_global_source_and_additive_block_capacity(player):
    state = fixture()
    creature = printed(state, 'Llanowar Elves', player)
    first = add(state, 'Brave the Sands', player)
    add(state, 'Brave the Sands', player)
    assert combat._max_attackers_blockable_by_creature(state, creature) == 3
    lose(state, first)
    assert combat._max_attackers_blockable_by_creature(state, creature) == 2
    bedlam = add(state, 'Bedlam', 3-player)
    lose(state, creature)
    assert card_cant_block(state, creature.id)
    lose(state, bedlam)
    assert not card_cant_block(state, creature.id)


def test_unknown_condition_is_diagnostic_not_unconditional_and_queries_are_pure():
    state = fixture()
    creature = add(state, 'Steel Leaf Champion')
    # Deliberately unsupported grammar fixture; never imported as a real card.
    creature.oracle_text = "As long as an unknown condition, this creature can't be blocked."
    before = serialize_match_snapshot(state)
    view = combat_rule_view(state, creature.id)
    assert not view['active'] and view['unsupported']
    assert continuous_layer_trace(state, creature.id)['unsupported_combat_clauses']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name', ['Pacifism', 'Bonds of Faith'])
def test_real_aura_cast_and_checked_attack_use_shared_restrictions(player, name):
    from game_state.state import Step
    state = fixture()
    state.active_player = state.priority_player = player
    creature = printed(state, 'Llanowar Elves', player)
    creature.summoning_sick = False
    aura = raw_add(state, name, player, Zone.HAND, cards=CARDS)
    state.players[player].mana_pool['W'] = 2
    state = checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': aura.id,
                           'targets': {'target_card_id': creature.id}})
    state = resolve(state)
    assert state.cards[aura.id].attached_to == creature.id
    state.step = Step.DECLARE_ATTACKERS
    state.priority_player = player
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), player, {'type': 'attack', 'attackers': [creature.id]})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('player', [1, 2])
def test_http_counter_gate_survives_sqlite_restore_and_rejection(game, player):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    from game_state.state import Step
    client, match = game
    state = match.state
    state.active_player = state.priority_player = player
    state.step = Step.DECLARE_ATTACKERS
    dragon = add(state, 'Slumbering Dragon', player)
    dragon.counters['+1/+1'] = 4
    persist(match)
    action = {'type': 'attack', 'attackers': [dragon.id]}
    rejected(client, match, action, player)
    match_id = match.state.id
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    restored = main.ACTIVE_MATCHES[match_id]
    rejected(client, restored, action, player)
    restored.state.cards[dragon.id].counters['+1/+1'] = 5
    persist(restored)
    response = client.post(f'/matches/{match_id}/action', json={'player_id': player, 'action': action})
    assert response.status_code == 200, response.text
    assert main.ACTIVE_MATCHES[match_id].state.attackers == [dragon.id]
