"""Full canonical old-board combat poses; no saved private game or paid-birth claim."""
from copy import deepcopy
import random

import pytest

from ai.agent import AIAgent
from card_data.seed_cards import seed_card_payload
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_combat_stats
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.restrictions import card_cant_block
from rules_engine.type_effects import effective_types
from tests.ai_decisions_canonical_cdba import raw_card


PRINTED = {name: deepcopy(seed_card_payload(name) or raw_card(name)) for name in (
    'Forest', 'Arboreal Grazer', 'Topiary Stomper', 'Tarmogoyf',
    'Llanowar Elves', 'Opt', 'Cultivate',
)}


def position(seat, *, lands=7, elves=1):
    counts = {'Forest': 49, 'Arboreal Grazer': 1, 'Topiary Stomper': 1,
              'Tarmogoyf': 2, 'Llanowar Elves': elves + 1, 'Opt': 1, 'Cultivate': 1}
    deck = [{**PRINTED[name], 'card_name': name, 'quantity': count}
            for name, count in counts.items()]
    state = MatchFactory.from_decks(deck, deck, seed=383, game_id='unused-blocker-refill')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 14
    state.active_player = state.priority_player = 3-seat
    state.step = Step.DECLARE_ATTACKERS
    state.players[seat].life = 20
    state.players[3-seat].life = 16
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.library.extend(player.hand)
        player.hand.clear()
        player.mana_pool.clear()

    def place(name, owner, zone=Zone.BATTLEFIELD):
        player = state.players[owner]
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        card = state.cards[cid]
        card.move_to_zone(zone)
        card.summoning_sick = False
        card.entered_turn = 1
        getattr(player, zone.value).append(cid)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, cid)
        return cid

    for _ in range(lands):
        place('Forest', seat)
    # Four genuine graveyard card types give both unmodified Goyfs 4/5.
    for name in ('Forest', 'Opt', 'Cultivate', 'Llanowar Elves'):
        place(name, 3-seat, Zone.GRAVEYARD)
    goyfs = [place('Tarmogoyf', 3-seat) for _ in range(2)]
    elf_ids = [place('Llanowar Elves', 3-seat) for _ in range(elves)]
    grazer = place('Arboreal Grazer', seat)
    stomper = place('Topiary Stomper', seat)
    attackers = [*goyfs, *elf_ids]
    state = checked_action(state, RulesEngine(), 3-seat, {
        'type': 'attack', 'attackers': attackers,
        'attack_targets': {cid: f'player:{seat}' for cid in attackers}})
    for _ in range(16):
        if state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat and not state.stack:
            break
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat
    assert all(effective_combat_stats(state, cid) == (4, 5) for cid in goyfs)
    for cid in (*attackers, grazer, stomper):
        assert state.cards[cid].oracle_text == PRINTED[state.cards[cid].name]['oracle_text']
    return state, goyfs, elf_ids, grazer, stomper


def choose(state, seat, difficulty='strong'):
    before, rng = serialize_match_snapshot(state), random.getstate()
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'block')
    old_move = deepcopy(move)
    groups = AIAgent(difficulty=difficulty, archetype='Ramp')._choose_blocks(
        state, move['attackers'], move['blockers'])
    assert serialize_match_snapshot(state) == before and random.getstate() == rng
    assert move == old_move
    return {aid: [bids] if isinstance(bids, str) else list(bids) for aid, bids in groups.items()}


def finish(state, seat, blocks):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, {'type': 'block', 'blocks': blocks})
    saw_damage = False
    for _ in range(40):
        saw_damage |= result.combat_damage_resolved
        if result.turn > state.turn and result.step == Step.UPKEEP:
            assert result.winner is None and saw_damage
            assert serialize_match_snapshot(state) == before
            return result
        assert not (result.pending_mechanic_choice or result.pending_trigger_order
                    or result.pending_replacement_choice)
        result = checked_action(result, RulesEngine(), result.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Checked combat did not reach next upkeep before draw')


@pytest.mark.parametrize('seat', [1, 2])
def test_strong_refills_retained_stomper_into_the_unblocked_elf(seat):
    state, goyfs, elves, grazer, stomper = position(seat)
    assert 'seven or more lands' in PRINTED['Topiary Stomper']['oracle_text']
    assert sum('Land' in effective_types(state, cid) and state.cards[cid].controller == seat
               for cid in state.players[seat].battlefield) == 7
    assert not card_cant_block(state, stomper)
    blocks = choose(state, seat)
    assert blocks.get(elves[0]) == [stomper], 'Retained Stomper must not stay unused'
    result = finish(state, seat, blocks)
    old_line = finish(state, seat, {goyfs[0]: [grazer]})
    assert old_line.players[seat].life == 15
    assert old_line.cards[elves[0]].zone == Zone.BATTLEFIELD
    assert result.players[seat].life == result.players[3-seat].life == 16
    assert result.cards[grazer].zone == result.cards[elves[0]].zone == Zone.GRAVEYARD
    assert result.cards[stomper].zone == Zone.BATTLEFIELD
    assert result.cards[stomper].counters.get('__damage_marked', 0) == 0
    assert all(result.cards[cid].zone == Zone.BATTLEFIELD
               and effective_combat_stats(result, cid) == (4, 5) for cid in goyfs)
    assert result.players[seat].battlefield == old_line.players[seat].battlefield
    for pid in (1, 2):
        assert result.players[pid].hand == state.players[pid].hand
        assert result.players[pid].library == state.players[pid].library


@pytest.mark.parametrize('seat', [1, 2])
def test_full_printed_stomper_cannot_refill_before_seven_controlled_lands(seat):
    state, _, elves, _, stomper = position(seat, lands=6)
    assert card_cant_block(state, stomper)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'block', 'blocks': {elves[0]: [stomper]}})
    assert serialize_match_snapshot(state) == before
    assert all(stomper not in bids for bids in choose(state, seat).values())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['easy', 'normal'])
def test_weak_fallback_keeps_original_allocation_semantics(seat, difficulty):
    state, goyfs, elves, grazer, stomper = position(seat)
    blocks = choose(state, seat, difficulty)
    assert blocks == {goyfs[0]: [grazer], goyfs[1]: [stomper]}
    result = finish(state, seat, blocks)
    assert result.players[seat].life == 19
    assert result.cards[grazer].zone == result.cards[stomper].zone == Zone.GRAVEYARD
    assert result.cards[elves[0]].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_opponent_identities_and_library_order_do_not_change_refill(seat):
    state, _, _, _, _ = position(seat)
    original = choose(state, seat)
    changed = deepcopy(state)
    player = changed.players[3-seat]
    cid = next(cid for cid in player.library if changed.cards[cid].name == 'Topiary Stomper')
    player.library.remove(cid)
    changed.cards[cid].move_to_zone(Zone.HAND)
    player.hand.append(cid)
    for owner in changed.players.values():
        owner.library.reverse()
    assert choose(changed, seat) == original


@pytest.mark.parametrize('seat', [1, 2])
def test_refill_uses_real_checked_projections_with_a_fixed_small_board_budget(seat, monkeypatch):
    state, _, elves, _, stomper = position(seat)
    agent = AIAgent(difficulty='strong', archetype='Ramp')
    original = agent._finish_combat_projection
    observed = []

    def counted(sim, root):
        observed.append(deepcopy(sim.blocks))
        assert len(observed) <= 1 + 5 + 5 * 4
        return original(sim, root)

    monkeypatch.setattr(agent, '_finish_combat_projection', counted)
    before = serialize_match_snapshot(state)
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'block')
    groups = agent._choose_blocks(state, move['attackers'], move['blockers'])
    assert groups.get(elves[0]) == stomper
    assert any(row.get(elves[0]) == [stomper] for row in observed)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_refill_projection_keeps_the_known_incumbent(seat, monkeypatch):
    state, goyfs, elves, grazer, stomper = position(seat)
    agent = AIAgent(difficulty='strong', archetype='Ramp')
    original = agent._finish_combat_projection

    def reject_refill(sim, root):
        is_refill = elves[0] in sim.blocks
        resolved = original(sim, root)
        # Protocol failure control only: never fabricate a successful projection.
        return resolved and not is_refill

    monkeypatch.setattr(agent, '_finish_combat_projection', reject_refill)
    before = serialize_match_snapshot(state)
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'block')
    groups = agent._choose_blocks(state, move['attackers'], move['blockers'])
    assert groups == {goyfs[0]: [grazer]}
    result = finish(state, seat, {goyfs[0]: [grazer]})
    assert result.players[seat].life == 15
    assert result.cards[stomper].zone == result.cards[elves[0]].zone == Zone.BATTLEFIELD
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keyword', ['menace', 'flying'])
def test_refill_cannot_bypass_native_pairing_or_minimum_blocker_rules(seat, keyword):
    state, _, elves, _, stomper = position(seat)
    add_keyword_effect(state, elves[0], [keyword])
    blocks = choose(state, seat)
    assert elves[0] not in blocks
    result = finish(state, seat, blocks)
    assert result.players[seat].life == 15
    assert result.cards[stomper].zone == result.cards[elves[0]].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_large_strong_board_keeps_legacy_fallback_without_refill_probes(seat, monkeypatch):
    state, goyfs, elves, grazer, stomper = position(seat, elves=3)
    agent = AIAgent(difficulty='strong', archetype='Ramp')
    original = agent._finish_combat_projection
    calls = []

    def observed(sim, root):
        calls.append(1)
        return original(sim, root)

    monkeypatch.setattr(agent, '_finish_combat_projection', observed)
    before = serialize_match_snapshot(state)
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'block')
    assert agent._choose_blocks(state, move['attackers'], move['blockers']) == {
        goyfs[0]: grazer, goyfs[1]: stomper}
    assert not calls and serialize_match_snapshot(state) == before
    result = finish(state, seat, {goyfs[0]: [grazer], goyfs[1]: [stomper]})
    assert result.players[seat].life == 17
    assert all(result.cards[cid].zone == Zone.BATTLEFIELD for cid in elves)
