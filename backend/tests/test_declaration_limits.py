"""Canonical declaration rules; fixtures are not fabricated tournament decks."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.declaration_policy import finalize_declaration
from game_state.state import Step, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine import combat
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.combat_requirements import best_required_blocks, requirement_weights
from rules_engine.declaration_limits import declaration_limit_view
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import fixture, add as raw_add
from tests.test_conditional_combat import lose
from tests.test_ability_suppression import add as printed
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/declaration_limits.json').read_text())}


def add(state, name, player=1):
    card = raw_add(state, name, player, cards=ROWS)
    assign_static_order_on_battlefield_entry(state, card.id)
    card.summoning_sick = False
    return card


def attack_step(state, player):
    state.active_player = state.priority_player = player
    state.step = Step.DECLARE_ATTACKERS


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name', ['Silent Arbiter', 'Dueling Grounds'])
def test_global_limits_reject_atomic_attack_and_block_declarations(player, name):
    state = fixture()
    source = add(state, name, 3-player)
    attackers = [printed(state, 'Llanowar Elves', player) for _ in range(2)]
    for card in attackers:
        card.summoning_sick = False
    attack_step(state, player)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), player, {'type': 'attack', 'attackers': [c.id for c in attackers]})
    assert serialize_match_snapshot(state) == before
    blockers = [printed(state, 'Llanowar Elves', 3-player) for _ in range(2)]
    state.attackers = [attackers[0].id]
    state.step = Step.DECLARE_BLOCKERS
    state.priority_player = 3-player
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-player, {'type': 'block', 'blocks': {attackers[0].id: [c.id for c in blockers]}})
    assert serialize_match_snapshot(state) == before
    lose(state, source)
    assert declaration_limit_view(state, 'block')['maximum'] is None
    state = checked_action(state, RulesEngine(), 3-player, {'type': 'block', 'blocks': {attackers[0].id: [c.id for c in blockers]}})
    assert len(state.blocks[attackers[0].id]) == 2


@pytest.mark.parametrize('player', [1, 2])
def test_crawlspace_player_scope_does_not_limit_planeswalker_attacks(player):
    state = fixture()
    add(state, 'Crawlspace', 3-player)
    attackers = [printed(state, 'Llanowar Elves', player) for _ in range(3)]
    for card in attackers:
        card.summoning_sick = False
    pw = add(state, 'Ugin, the Spirit Dragon', 3-player)
    pw.loyalty = int(ROWS[pw.name]['loyalty'])
    attack_step(state, player)
    ids = [c.id for c in attackers]
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), player, {'type': 'attack', 'attackers': ids})
    state = checked_action(state, RulesEngine(), player, {'type': 'attack', 'attackers': ids,
                           'attack_targets': {ids[2]: f'planeswalker:{pw.id}'}})
    assert len(state.attackers) == 3


def test_must_attack_requirements_respect_limits_and_are_weighted_per_source():
    state = fixture()
    add(state, 'Silent Arbiter', 2)
    masters = [add(state, 'Goblin Rabblemaster') for _ in range(2)]
    goblin = add(state, 'Raging Goblin')
    attack_step(state, 1)
    assert requirement_weights(state, [goblin.id], 'attack')[goblin.id] == 2
    for ids in ([], [masters[0].id]):
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': ids})
    state = checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': [goblin.id]})
    assert state.attackers == [goblin.id]


def test_raw_requirement_completion_never_exceeds_a_limit():
    state = fixture()
    add(state, 'Silent Arbiter', 2)
    for _ in range(3):
        add(state, 'Juggernaut')
    attack_step(state, 1)
    combat.declare_attackers(state, [])
    assert len(state.attackers) == 1


@pytest.mark.parametrize('player', [1, 2])
def test_menace_can_make_all_block_requirements_impossible(player):
    state = fixture()
    attacker = printed(state, 'Llanowar Elves', player)
    from rules_engine.keyword_effects import add_keyword_effect
    add_keyword_effect(state, attacker.id, ['menace'])
    add(state, 'Silent Arbiter')
    add(state, 'Invasion Plans')
    for _ in range(3):
        printed(state, 'Llanowar Elves', 3-player)
    state.active_player = player
    state.priority_player = 3-player
    state.step = Step.DECLARE_BLOCKERS
    state.attackers = [attacker.id]
    assert best_required_blocks(state) == {}
    state = checked_action(state, RulesEngine(), 3-player, {'type': 'block', 'blocks': {}})
    assert not state.blocks


def test_required_blocking_needs_legal_menace_groups():
    state = fixture()
    attacker = printed(state, 'Llanowar Elves', 1)
    from rules_engine.keyword_effects import add_keyword_effect
    add_keyword_effect(state, attacker.id, ['menace'])
    add(state, 'Invasion Plans')
    guards = [printed(state, 'Llanowar Elves', 2) for _ in range(2)]
    state.active_player = 1
    state.priority_player = 2
    state.step = Step.DECLARE_BLOCKERS
    state.attackers = [attacker.id]
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {}})
    combat.declare_blockers(state, {})
    assert set(state.blocks[attacker.id]) == {c.id for c in guards}


def test_any_number_blocker_can_support_two_required_menace_groups():
    state = fixture()
    from tests.test_combat_ability_provenance import add as combat_card
    from rules_engine.keyword_effects import add_keyword_effect
    ground = printed(state, 'Llanowar Elves')
    flyer = add(state, 'Raging Goblin')
    add_keyword_effect(state, ground.id, ['menace'])
    add_keyword_effect(state, flyer.id, ['menace', 'flying'])
    elf = printed(state, 'Llanowar Elves', 2)
    cloud = combat_card(state, 'Cloud Elemental', 2)
    guard = combat_card(state, 'Palace Guard', 2)
    add_keyword_effect(state, guard.id, ['flying'])
    add(state, 'Invasion Plans')
    state.active_player = 1
    state.priority_player = 2
    state.step = Step.DECLARE_BLOCKERS
    state.attackers = [ground.id, flyer.id]
    blocks = best_required_blocks(state)
    assert set(blocks[ground.id]) == {elf.id, guard.id}
    assert set(blocks[flyer.id]) == {cloud.id, guard.id}
    result = checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': blocks})
    assert result.blocks == blocks


def test_large_required_blocker_board_has_no_arbitrary_search_cap():
    state = fixture()
    attacker = printed(state, 'Llanowar Elves')
    add(state, 'Invasion Plans')
    guards = [printed(state, 'Llanowar Elves', 2) for _ in range(101)]
    state.active_player = 1
    state.attackers = [attacker.id]
    before = serialize_match_snapshot(state)
    blocks = best_required_blocks(state)
    assert len(blocks[attacker.id]) == len(guards)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_all_ai_paths_finalize_a_legal_limited_declaration(difficulty):
    state = fixture()
    add(state, 'Silent Arbiter', 2)
    cards = [add(state, 'Juggernaut') for _ in range(3)]
    attack_step(state, 1)
    before = serialize_match_snapshot(state)
    decision = AIAgent(difficulty).choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'attack'
    result = checked_action(state, RulesEngine(), 1, decision.action)
    assert len(result.attackers) == 1


def test_ai_preserves_tactical_intent_among_equal_weight_requirements():
    state = fixture()
    add(state, 'Silent Arbiter', 2)
    add(state, 'Juggernaut')
    add(state, 'Goblin Rabblemaster')
    goblin = add(state, 'Raging Goblin')
    attack_step(state, 1)
    before = serialize_match_snapshot(state)
    action = finalize_declaration(state, {'type': 'attack', 'attackers': [goblin.id]})
    assert action['attackers'] == [goblin.id]
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('player', [1, 2])
def test_http_limit_survives_restore_and_source_suppression(game, player):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    source = add(match.state, 'Silent Arbiter', 3-player)
    creatures = [printed(match.state, 'Llanowar Elves', player) for _ in range(2)]
    for card in creatures:
        card.summoning_sick = False
    attack_step(match.state, player)
    persist(match)
    action = {'type': 'attack', 'attackers': [c.id for c in creatures]}
    rejected(client, match, action, player)
    match_id = match.state.id
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    restored = main.ACTIVE_MATCHES[match_id]
    rejected(client, restored, action, player)
    report = client.get(f'/matches/{match_id}/rules-diagnostics').json()
    assert report['declaration_limits']['attack']['maximum'] == 1
    lose(restored.state, restored.state.cards[source.id])
    persist(restored)
    response = client.post(f'/matches/{match_id}/action', json={'player_id': player, 'action': action})
    assert response.status_code == 200, response.text
    assert len(main.ACTIVE_MATCHES[match_id].state.attackers) == 2


@pytest.mark.parametrize('field', ['pending_mechanic_choice', 'pending_replacement_choice', 'pending_trigger_order'])
def test_ai_declaration_finalization_never_bypasses_pending_choice(field):
    state = fixture()
    add(state, 'Juggernaut')
    attack_step(state, 1)
    setattr(state, field, {'kind': 'fixture_choice'})
    action = {'type': 'pass_priority'}
    before = serialize_match_snapshot(state)
    assert finalize_declaration(state, action) == action
    assert serialize_match_snapshot(state) == before
