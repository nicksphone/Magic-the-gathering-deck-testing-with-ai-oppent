"""Canonical small exact-search retention and dense bounded-shortlist tactics.

Three flying attackers keep the first eight exact reference searches <=32 intents.
The dense cases check native witnesses and bounded candidate search, not optimality.
Only runtime battlefield/life poses change; printed cards are never rewritten.
"""
from copy import deepcopy
import json
import pickle

import pytest

from ai.agent import AIAgent
from ai.block_search import block_intents
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.query_context import query_cache
from tests.combat_canonical_022 import canonical_card, canonical_entry, raw_card as combat_raw
from tests.test_linked_damage_targets import raw_card
from tests.test_training_choice_coverage import FIXTURES


def add(state, name, owner):
    if name == 'Goblin War Drums':
        raw = next(row for row in json.loads((FIXTURES / 'combat_coverage.json').read_text())
                   if row['name'] == name)
    elif name == 'Thalia, Guardian of Thraben':
        raw = next(row for line in (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_text().splitlines()
                   if (row := json.loads(line))['name'] == name)
    else:
        raw = combat_raw(name)
    assert raw['object'] == 'card' and raw['id'] and raw['oracle_id']
    if name in {'Goblin War Drums', 'Thalia, Guardian of Thraben'}:
        card = raw_card(state, raw, owner, Zone.BATTLEFIELD)
        card.summoning_sick = False
    else:
        card = canonical_card(name, id=state.allocate_object_id(), owner=owner,
                              controller=owner, zone=Zone.BATTLEFIELD, summoning_sick=False)
        state.cards[card.id] = card
        state.players[owner].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    assert (card.name, card.mana_cost, card.oracle_text, card.type_line) == tuple(
        raw[key] for key in ('name', 'mana_cost', 'oracle_text', 'type_line'))
    assert card.power == (int(raw['power']) if raw.get('power') is not None else None)
    assert card.toughness == (int(raw['toughness']) if raw.get('toughness') is not None else None)
    return card.id


def position(seat, case, *, dense=False):
    deck = [canonical_entry('Forest', 20)]
    state = MatchFactory.from_decks(deck, deck, seed=7201, game_id='block-tactical-frontier')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 8
    state.active_player = state.priority_player = 3-seat
    state.step = Step.DECLARE_ATTACKERS
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()
    state.players[seat].life = 20 if case == 'profitable_double' else 13
    if dense:
        state.players[seat].life = {'trample_lethal': 7, 'profitable_double': 20,
                                    'menace_deathtouch': 5, 'first_strike': 1}[case]
    threat = add(state, {'trample_lethal': 'Charging Monstrosaur',
                        'profitable_double': 'Hill Giant', 'menace_deathtouch': 'Typhoid Rats',
                        'first_strike': 'Typhoid Rats'}[case], 3-seat)
    other_attacker = ('Typhoid Rats' if case == 'first_strike' else 'Grizzly Bears') if dense else 'Serra Angel'
    attackers = [threat, *[add(state, other_attacker, 3-seat) for _ in range(3)]]
    if case == 'trample_lethal' and not dense:
        blockers = [add(state, 'Llanowar Elves', seat) for _ in range(5)]
    elif case == 'profitable_double' and dense:
        blockers = [add(state, name, seat) for name in ['Grizzly Bears'] * 2 + ['Centaur Courser'] * 3]
    elif case == 'first_strike':
        blockers = [add(state, 'Thalia, Guardian of Thraben', seat),
                    *[add(state, 'Grizzly Bears', seat) for _ in range(4)]]
    else:
        blockers = [add(state, 'Grizzly Bears', seat) for _ in range(5)]
    if case == 'menace_deathtouch':
        add(state, 'Goblin War Drums', 3-seat)
    state = checked_action(state, RulesEngine(), 3-seat, {
        'type': 'attack', 'attackers': attackers,
        'attack_targets': {cid: f'player:{seat}' for cid in attackers}})
    for _ in range(12):
        if state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat and not state.stack:
            break
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    else:
        raise AssertionError('Native declaration did not reach blockers')
    assert len(state.attackers) == len(attackers) == 4 and len(blockers) == 5
    return state, attackers, blockers


def finish(agent, state, seat, blocks):
    # Search returns singleton strings; the checked action boundary uses lists.
    normalized = {aid: [bids] if isinstance(bids, str) else list(bids) for aid, bids in blocks.items()}
    projected = checked_action(state, agent.engine, seat, {'type': 'block', 'blocks': normalized})
    assert agent._finish_combat_projection(projected, state)
    return projected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['trample_lethal', 'profitable_double', 'menace_deathtouch', 'first_strike'])
def test_four_attackers_five_blockers_retain_small_exact_tactics(seat, case):
    state, attacker_ids, blocker_ids = position(seat, case)
    agent = AIAgent(difficulty='master', archetype='Midrange')
    attackers = [{'id': cid, 'name': state.cards[cid].name} for cid in attacker_ids]
    blockers = [{'id': cid, 'name': state.cards[cid].name} for cid in blocker_ids]
    before, old_inputs = pickle.dumps(state, protocol=5), deepcopy((attackers, blockers))
    intents = block_intents(state, attacker_ids, blocker_ids)
    assert intents is not None and 1 <= len(intents) <= 32
    threat = attacker_ids[0]
    witness = {threat: blocker_ids if case == 'trample_lethal' else
               blocker_ids[:1] if case == 'first_strike' else blocker_ids[:2]}
    reference = finish(agent, state, seat, witness)
    assert reference.winner is None and reference.players[seat].life == (8 if case == 'profitable_double' else 1)
    if case != 'profitable_double':
        assert finish(agent, state, seat, {}).winner == 3-seat
    if case == 'menace_deathtouch':
        with pytest.raises(ActionRejected):
            checked_action(state, agent.engine, seat, {'type': 'block', 'blocks': {threat: blocker_ids[:1]}})
    chosen = agent._search_block_assignments(state, attackers, blockers, consider_next_combat=False)
    assert chosen is not None
    actual = finish(agent, state, seat, chosen)
    assert actual.winner is None and actual.players[seat].life == reference.players[seat].life
    assert actual.cards[threat].zone == Zone.GRAVEYARD
    group = chosen[threat]
    group = group if isinstance(group, list) else [group]
    if case == 'trample_lethal':
        assert set(group) == set(blocker_ids)
    elif case in {'profitable_double', 'menace_deathtouch'}:
        assert len(group) >= 2
        assert sum(actual.cards[cid].zone == Zone.GRAVEYARD for cid in blocker_ids) <= 1
    else:
        assert blocker_ids[0] in group
        assert all(actual.cards[cid].zone == Zone.BATTLEFIELD for cid in blocker_ids)
    assert (attackers, blockers) == old_inputs
    assert pickle.dumps(state, protocol=5) == before
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['trample_lethal', 'profitable_double', 'menace_deathtouch', 'first_strike'])
def test_dense_four_by_five_shortlist_preserves_native_tactics(seat, case, monkeypatch):
    from ai import block_search

    state, attacker_ids, blocker_ids = position(seat, case, dense=True)
    agent = AIAgent(difficulty='master', archetype='Midrange')
    attackers = [{'id': cid, 'name': state.cards[cid].name} for cid in attacker_ids]
    blockers = [{'id': cid, 'name': state.cards[cid].name} for cid in blocker_ids]
    before, old_inputs = pickle.dumps(state, protocol=5), deepcopy((attackers, blockers))
    if case == 'trample_lethal':
        witness = {attacker_ids[0]: blocker_ids[:3], attacker_ids[1]: blocker_ids[3:4],
                   attacker_ids[2]: blocker_ids[4:]}
    elif case == 'profitable_double':
        witness = {attacker_ids[0]: blocker_ids[:2],
                   **{aid: [bid] for aid, bid in zip(attacker_ids[1:], blocker_ids[2:])}}
    elif case == 'menace_deathtouch':
        witness = {attacker_ids[1]: blocker_ids[:2], attacker_ids[2]: blocker_ids[2:4]}
        with pytest.raises(ActionRejected):
            checked_action(state, agent.engine, seat, {
                'type': 'block', 'blocks': {attacker_ids[0]: blocker_ids[:1]}})
    else:
        witness = {aid: [bid] for aid, bid in zip(attacker_ids, blocker_ids)}
    reference = finish(agent, state, seat, witness)
    assert reference.winner is None
    assert reference.players[seat].life == {'trample_lethal': 5, 'profitable_double': 20,
                                          'menace_deathtouch': 2, 'first_strike': 1}[case]
    if case != 'profitable_double':
        assert finish(agent, state, seat, {}).winner == 3-seat
    else:
        assert all(reference.cards[cid].zone == Zone.GRAVEYARD for cid in attacker_ids)
        assert sum(reference.cards[cid].zone == Zone.GRAVEYARD for cid in blocker_ids) == 1

    sizes, projections = [], []
    native_shortlist = block_search.block_projection_intents
    native_finish = agent._finish_combat_projection

    def observed_shortlist(root, intents):
        old = deepcopy(intents)
        selected = native_shortlist(root, intents)
        assert intents == old and selected is not None
        assert all(row in intents for row in selected)
        sizes.append((len(intents), len(selected)))
        return selected

    def observed_finish(projected, root):
        projections.append(1)
        return native_finish(projected, root)

    with monkeypatch.context() as scoped:
        scoped.setattr(block_search, 'block_projection_intents', observed_shortlist)
        scoped.setattr(agent, '_finish_combat_projection', observed_finish)
        chosen = agent._search_block_assignments(state, attackers, blockers, consider_next_combat=False)
    assert sizes == [(405 if case == 'menace_deathtouch' else 3125, 16)]
    assert 1 <= len(projections) <= 16
    assert chosen is not None
    actual = finish(agent, state, seat, chosen)
    assert actual.winner is None and actual.players[seat].life > 0
    if case == 'profitable_double':
        assert actual.players[seat].life == 20
        assert all(actual.cards[cid].zone == Zone.GRAVEYARD for cid in attacker_ids)
        assert sum(actual.cards[cid].zone == Zone.GRAVEYARD for cid in blocker_ids) <= 1
        assert isinstance(chosen[attacker_ids[0]], list) and len(chosen[attacker_ids[0]]) >= 2
    elif case == 'menace_deathtouch':
        assert all(isinstance(group, list) and len(group) >= 2 for group in chosen.values())
    elif case == 'first_strike':
        assert all(actual.cards[cid].zone == Zone.GRAVEYARD for cid in attacker_ids)
        assert actual.cards[blocker_ids[0]].zone == Zone.BATTLEFIELD
        assert sum(actual.cards[cid].zone == Zone.BATTLEFIELD for cid in blocker_ids) >= 2
    assert (attackers, blockers) == old_inputs
    assert pickle.dumps(state, protocol=5) == before
    assert query_cache(state) is None
