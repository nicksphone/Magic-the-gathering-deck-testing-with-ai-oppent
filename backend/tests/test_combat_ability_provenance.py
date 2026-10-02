"""Canonical combat abilities; board fixtures are not fabricated competitive decks."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Step, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine import combat
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.continuous import effective_keyword_counts, effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.restrictions import card_cant_attack, card_cant_block, card_must_attack_if_able, card_cant_attack_alone, card_cant_block_alone
from rules_engine.targeting import player_target_immunity, spell_cant_be_countered
from rules_engine.stack_engine import add_to_stack
from tests.test_ai_recurring_engines import fixture, add as raw_add, resolve
from tests.test_ability_suppression import add as add_printed
from tests.test_api_input_contracts import game, persist

CARDS = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/combat_ability_provenance.json').read_text())}


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    card = raw_add(state, name, player, Zone.HAND if zone == Zone.STACK else zone, cards=CARDS)
    if zone == Zone.STACK:
        state.players[player].hand.remove(card.id)
        card.move_to_zone(Zone.STACK)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
        card.summoning_sick = False
    return card


def prepare_blocks(state, ids, player):
    state.active_player = player
    state.priority_player = 3-player
    state.step = Step.DECLARE_BLOCKERS
    state.attackers = list(ids)
    state.attackers_declared = True


def block(state, assignments, player=1):
    return checked_action(state, RulesEngine(), 3-player, {'type': 'block', 'blocks': assignments})


def lose(state, card):
    resolve_effect(state, 3-card.controller, 'temporary_ability_loss', {'target_card_id': card.id})


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name', ['Hand of Honor', 'Craw Giant', 'Benalish Cavalry'])
def test_canonical_keywords_are_counterable_stack_triggers_not_immediate_changes(player, name):
    state = fixture()
    attacker = add(state, name, player)
    a = add_printed(state, 'Llanowar Elves', 3-player)
    b = add_printed(state, 'Llanowar Elves', 3-player)
    prepare_blocks(state, [attacker.id], player)
    state = block(state, {attacker.id: [a.id, b.id]}, player)
    assert effective_power(state, attacker.id) == attacker.power
    assert effective_toughness(state, a.id) == 1
    expected = 2 if name == 'Benalish Cavalry' else 1
    assert len(state.stack) == expected
    assert all(item.payload['__trigger_event'] == 'block_declared' for item in state.stack)
    spell = add(state, 'Stifle', player, Zone.HAND)
    state.players[player].mana_pool['U'] = 1
    trigger_id = state.stack[-1].id
    state = checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': spell.id,
                           'targets': {'target_stack_id': trigger_id}})
    assert len(state.stack) == expected + 1
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert not state.stack
    assert effective_power(state, attacker.id) == attacker.power
    if name == 'Benalish Cavalry':
        assert sum(state.cards[cid].zone == Zone.GRAVEYARD for cid in (a.id, b.id)) == 1
    else:
        assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in (a.id, b.id))


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name,amount', [('Hand of Honor', 1), ('Craw Giant', 4), ('Benalish Cavalry', 0)])
def test_each_supported_keyword_resolves_through_priority_and_expires(player, name, amount):
    state = fixture()
    attacker = add(state, name, player)
    blockers = [add_printed(state, 'Llanowar Elves', 3-player) for _ in range(3)]
    prepare_blocks(state, [attacker.id], player)
    state = block(state, {attacker.id: [c.id for c in blockers]}, player)
    assert not any('__eot_power' in card.counters for card in state.cards.values())
    state = resolve(state)
    assert effective_power(state, attacker.id) == attacker.power + amount
    assert effective_toughness(state, attacker.id) == attacker.toughness + amount
    if name == 'Benalish Cavalry':
        assert all(state.cards[c.id].zone == Zone.GRAVEYARD for c in blockers)
    RulesEngine()._clear_marked_damage(state)
    assert effective_power(state, attacker.id) == attacker.power


@pytest.mark.parametrize('player', [1, 2])
def test_rampage_counts_remaining_original_blockers_at_resolution(player):
    state = fixture()
    attacker = add(state, 'Craw Giant', player)
    blockers = [add_printed(state, 'Llanowar Elves', 3-player) for _ in range(3)]
    prepare_blocks(state, [attacker.id], player)
    state = block(state, {attacker.id: [c.id for c in blockers]}, player)
    bolt = add(state, 'Lightning Bolt', player, Zone.HAND)
    state.players[player].mana_pool['R'] = 1
    state = checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': bolt.id,
                           'targets': {'target_card_id': blockers[0].id}})
    state = resolve(state)
    assert state.cards[blockers[0].id].zone == Zone.GRAVEYARD
    assert effective_power(state, attacker.id) == attacker.power + 2
    # Removing another blocker after resolution does not recompute the bonus.
    resolve_effect(state, player, 'destroy_permanent', {'target_card_id': blockers[1].id})
    assert effective_power(state, attacker.id) == attacker.power + 2


@pytest.mark.parametrize('player', [1, 2])
def test_intrinsic_instances_include_gained_keywords_and_do_not_duplicate_family_metadata(player):
    state = fixture()
    attacker = add(state, 'Hand of Honor', player)
    counts = effective_keyword_counts(state, attacker.id)
    assert counts['bushido 1'] == 1 and 'bushido' not in counts
    add_keyword_effect(state, attacker.id, ['bushido 2', 'bushido 1'])
    blockers = [add_printed(state, 'Llanowar Elves', 3-player) for _ in range(2)]
    prepare_blocks(state, [attacker.id], player)
    state = block(state, {attacker.id: [c.id for c in blockers]}, player)
    assert len(state.stack) == 3
    state = resolve(state)
    assert effective_power(state, attacker.id) == attacker.power + 4
    lose(state, state.cards[attacker.id])
    assert not any(k.startswith('bushido') for k in effective_keyword_counts(state, attacker.id))
    add_keyword_effect(state, attacker.id, ['bushido 2'])
    assert effective_keyword_counts(state, attacker.id)['bushido 2'] == 1


@pytest.mark.parametrize('player', [1, 2])
def test_multi_blocker_bushido_triggers_once_and_flanking_instances_remain_independent(player):
    state = fixture()
    a = add(state, 'Benalish Cavalry', player)
    b = add(state, 'Benalish Cavalry', player)
    guard = add(state, 'Palace Guard', 3-player)
    add_keyword_effect(state, a.id, ['flanking'])
    add_keyword_effect(state, guard.id, ['bushido 3'])
    prepare_blocks(state, [a.id, b.id], player)
    state = block(state, {a.id: [guard.id], b.id: [guard.id]}, player)
    assert len([t for t in state.stack if t.effect_key == 'bushido_buff']) == 1
    assert len([t for t in state.stack if t.effect_key == 'flanking_buff']) == 3
    # Non-active player's bushido resolves first under automatic APNAP ordering.
    state = resolve(state)
    assert state.cards[guard.id].zone == Zone.BATTLEFIELD
    assert effective_toughness(state, guard.id) == guard.toughness


@pytest.mark.parametrize('player', [1, 2])
def test_suppression_before_blocks_disables_keywords_but_not_existing_stack_instances(player):
    state = fixture()
    attacker = add(state, 'Hand of Honor', player)
    blocker = add_printed(state, 'Llanowar Elves', 3-player)
    lose(state, attacker)
    prepare_blocks(state, [attacker.id], player)
    state = block(state, {attacker.id: [blocker.id]}, player)
    assert not state.stack
    RulesEngine()._clear_marked_damage(state)
    state.blockers_declared = False
    state.priority_player = 3-player
    state = block(state, {attacker.id: [blocker.id]}, player)
    assert len(state.stack) == 1
    lose(state, state.cards[attacker.id])
    state = resolve(state)
    assert effective_power(state, attacker.id) == attacker.power + 1


@pytest.mark.parametrize('player', [1, 2])
def test_flanking_is_nontargeted_and_does_not_follow_a_blinked_blocker(player):
    state = fixture()
    attacker = add(state, 'Benalish Cavalry', player)
    blocker = add_printed(state, 'Llanowar Elves', 3-player)
    add_keyword_effect(state, blocker.id, ['hexproof', 'shroud'])
    prepare_blocks(state, [attacker.id], player)
    state = block(state, {attacker.id: [blocker.id]}, player)
    assert len(state.stack) == 1 and not state.stack[0].targets
    card = state.cards[blocker.id]
    card.move_to_zone(Zone.EXILE)
    card.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, card.id)
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert effective_toughness(state, blocker.id) == blocker.toughness


@pytest.mark.parametrize('player', [1, 2])
def test_flanking_blocker_does_not_trigger_and_nonmana_damage_action_cannot_skip_stack(player):
    state = fixture()
    attacker = add(state, 'Benalish Cavalry', player)
    blocker = add(state, 'Benalish Cavalry', 3-player)
    prepare_blocks(state, [attacker.id], player)
    state = block(state, {attacker.id: [blocker.id]}, player)
    assert not state.stack
    lose(state, state.cards[blocker.id])
    state.blockers_declared = False
    state.priority_player = 3-player
    state = block(state, {attacker.id: [blocker.id]}, player)
    assert len(state.stack) == 1
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, player, {'type': 'combat_damage'}, reject_invalid=True)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('player', [1, 2])
def test_printed_combat_constraints_and_requirements_expire_under_loss(player):
    state = fixture()
    stomper = add(state, 'Topiary Stomper', player)
    raider = add(state, 'Goblin Raider', player)
    slayer = add(state, 'Dauthi Slayer', player)
    flunkies = add(state, 'Mogg Flunkies', player)
    assert card_cant_attack(state, stomper.id) and card_cant_block(state, stomper.id)
    assert card_cant_block(state, raider.id)
    assert card_must_attack_if_able(state, slayer.id)
    assert card_cant_attack_alone(state, flunkies.id) and card_cant_block_alone(state, flunkies.id)
    for card in (stomper, raider, slayer, flunkies):
        lose(state, card)
    assert not card_cant_attack(state, stomper.id) and not card_cant_block(state, stomper.id)
    assert not card_cant_block(state, raider.id)
    assert not card_must_attack_if_able(state, slayer.id)
    assert not card_cant_attack_alone(state, flunkies.id) and not card_cant_block_alone(state, flunkies.id)
    add_keyword_effect(state, raider.id, ['decayed'])
    assert card_cant_block(state, raider.id)
    RulesEngine()._clear_marked_damage(state)
    assert card_cant_attack(state, stomper.id) and card_must_attack_if_able(state, slayer.id)


@pytest.mark.parametrize('player', [1, 2])
def test_mogg_flunkies_cannot_attack_or_block_alone_and_illegal_attack_does_not_tap(player):
    state = fixture()
    flunkies = add(state, 'Mogg Flunkies', player)
    state.active_player = player
    combat.declare_attackers(state, [flunkies.id])
    assert not state.attackers and not flunkies.tapped
    ally = add_printed(state, 'Llanowar Elves', player)
    combat.declare_attackers(state, [flunkies.id, ally.id])
    assert set(state.attackers) == {flunkies.id, ally.id}
    flunkies.tapped = ally.tapped = False
    attacker = add_printed(state, 'Llanowar Elves', 3-player)
    prepare_blocks(state, [attacker.id], 3-player)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        block(state, {attacker.id: [flunkies.id]}, 3-player)
    assert serialize_match_snapshot(state) == before
    state = block(state, {attacker.id: [flunkies.id, ally.id]}, 3-player)
    assert len(state.blocks[attacker.id]) == 2


@pytest.mark.parametrize('player', [1, 2])
def test_unblockable_blocker_restrictions_and_multi_block_capacity_follow_loss(player):
    state = fixture()
    stalker = add(state, 'Invisible Stalker', player)
    cloud = add(state, 'Cloud Elemental', 3-player)
    assert not combat._can_block_attacker(state, stalker, cloud)
    lose(state, stalker)
    assert not combat._can_block_attacker(state, stalker, cloud)  # Cloud still needs a flying attacker.
    lose(state, cloud)
    assert combat._can_block_attacker(state, stalker, cloud)
    guard = add(state, 'Palace Guard', 3-player)
    giant = add(state, 'Two-Headed Giant of Foriys', 3-player)
    colossus = add(state, 'Phyrexian Colossus', player)
    assert combat._max_attackers_blockable_by_creature(state, guard) == float('inf')
    assert combat._max_attackers_blockable_by_creature(state, giant) == 2
    assert combat._minimum_blockers_required(state, colossus.id) == 3
    for card in (guard, giant, colossus):
        lose(state, card)
    assert combat._max_attackers_blockable_by_creature(state, guard) == 1
    assert combat._max_attackers_blockable_by_creature(state, giant) == 1
    assert combat._minimum_blockers_required(state, colossus.id) == 1
    add_keyword_effect(state, colossus.id, ['menace'])
    assert combat._minimum_blockers_required(state, colossus.id) == 2


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name,immunity', [('True Believer', 'shroud'), ('Aegis of the Gods', 'hexproof')])
def test_player_immunity_sources_are_disabled_by_loss_not_permanent_type_change(player, name, immunity):
    state = fixture()
    source = add(state, name, player)
    assert player_target_immunity(state, player, 3-player) == immunity
    lose(state, source)
    assert player_target_immunity(state, player, 3-player) is None
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert player_target_immunity(restored, player, 3-player) is None
    RulesEngine()._clear_marked_damage(restored)
    assert player_target_immunity(restored, player, 3-player) == immunity


@pytest.mark.parametrize('player', [1, 2])
def test_suppressed_counter_protection_source_no_longer_protects_other_spells(player):
    state = fixture()
    source = add(state, 'Prowling Serpopard', player)
    spell = add(state, 'Hand of Honor', player, Zone.STACK)
    item = add_to_stack(state, spell.id, player, spell.name, 'noop', {})
    assert spell_cant_be_countered(state, item)
    resolve_effect(state, 3-player, 'counter_spell', {'target_stack_id': item.id})
    assert item in state.stack
    lose(state, source)
    assert not spell_cant_be_countered(state, item)
    resolve_effect(state, 3-player, 'counter_spell', {'target_stack_id': item.id})
    assert item not in state.stack and state.cards[spell.id].zone == Zone.GRAVEYARD
    # The Serpopard spell's own protection is independent of any battlefield loss.
    self_spell = add(state, 'Prowling Serpopard', player, Zone.STACK)
    own_item = add_to_stack(state, self_spell.id, player, self_spell.name, 'noop', {})
    assert spell_cant_be_countered(state, own_item)


@pytest.mark.parametrize('player', [1, 2])
def test_master_block_search_sees_bushido_before_discarding_a_profitable_block(player):
    state = fixture()
    attacker = add(state, 'Mogg Flunkies', 3-player)
    blocker = add(state, 'Hand of Honor', player)
    prepare_blocks(state, [attacker.id], 3-player)
    before = serialize_match_snapshot(state)
    choice = AIAgent('master')._search_block_assignments(state, [{'id': attacker.id}], [{'id': blocker.id}])
    assert choice and blocker.id in str(choice)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('player', [1, 2])
def test_http_block_trigger_snapshot_restore_and_priority_resolution(game, player):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    attacker = add(match.state, 'Hand of Honor', player)
    blocker = add_printed(match.state, 'Llanowar Elves', 3-player)
    prepare_blocks(match.state, [attacker.id], player)
    persist(match)
    response = client.post(f'/matches/{match.state.id}/action', json={
        'player_id': 3-player, 'action': {'type': 'block', 'blocks': {attacker.id: [blocker.id]}}})
    assert response.status_code == 200, response.text
    assert len(match.state.stack) == 1
    assert effective_power(match.state, attacker.id) == attacker.power
    match_id = match.state.id
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    match = main.ACTIVE_MATCHES[match_id]
    for _ in range(4):
        if not match.state.stack:
            break
        response = client.post(f'/matches/{match_id}/action', json={
            'player_id': match.state.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    assert not match.state.stack
    assert effective_power(match.state, attacker.id) == attacker.power + 1


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name', ['Aegis of the Gods', 'True Believer'])
def test_http_player_immunity_target_legality_follows_loss_and_cleanup(game, player, name):
    from tests.test_api_input_contracts import rejected
    client, match = game
    state = match.state
    source = add(state, name, player)
    bolt = add(state, 'Lightning Bolt', 3-player, Zone.HAND)
    state.active_player = state.priority_player = 3-player
    state.players[3-player].mana_pool['R'] = 2
    persist(match)
    action = {'type': 'cast_spell', 'card_id': bolt.id, 'targets': {'target_player': player}}
    rejected(client, match, action, player_id=3-player)
    state = match.state  # Rejection restores a detached authoritative snapshot.
    lose(state, state.cards[source.id])
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': 3-player, 'action': action})
    assert response.status_code == 200, response.text
    match.state = resolve(match.state)
    assert match.state.players[player].life == 17
    RulesEngine()._clear_marked_damage(match.state)
    assert player_target_immunity(match.state, player, 3-player) is not None


@pytest.mark.parametrize('player', [1, 2])
def test_keyword_effect_does_not_require_its_source_to_remain_in_play(player):
    state = fixture()
    attacker = add(state, 'Benalish Cavalry', player)
    blocker = add_printed(state, 'Llanowar Elves', 3-player)
    prepare_blocks(state, [attacker.id], player)
    state = block(state, {attacker.id: [blocker.id]}, player)
    resolve_effect(state, 3-player, 'destroy_permanent', {'target_card_id': attacker.id})
    assert state.cards[attacker.id].zone == Zone.GRAVEYARD
    state = resolve(state)
    assert state.cards[blocker.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('player', [1, 2])
def test_rampage_counts_new_current_blockers_and_rejects_stale_blinked_references(player):
    state = fixture()
    attacker = add(state, 'Craw Giant', player)
    first = add_printed(state, 'Llanowar Elves', 3-player)
    stale = add_printed(state, 'Llanowar Elves', 3-player)
    prepare_blocks(state, [attacker.id], player)
    state = block(state, {attacker.id: [first.id, stale.id]}, player)
    # Explicit effect-event fixture: a new object joins combat before Rampage resolves.
    extra = add_printed(state, 'Llanowar Elves', 3-player)
    state.blocks[attacker.id].append(extra.id)
    old = state.cards[stale.id]
    old.move_to_zone(Zone.EXILE)
    old.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, old.id)
    state = resolve(state)
    assert effective_power(state, attacker.id) == attacker.power + 2
