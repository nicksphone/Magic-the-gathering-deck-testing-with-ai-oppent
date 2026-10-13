"""Real paid kernel events; trusted initial phase/pool/extra draws, not natural BO3."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone, draw_card
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from ai.sideboard_facts import held_unused_ids


RAW = {row['name']: row for row in map(json.loads,
    (Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_text().splitlines())}
BASICS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/sideboard_basics.json').read_text())}


def game(caster):
    deck = [{**RAW[name], 'card_name': name, 'quantity': 4}
            for name in ('Llanowar Elves', 'Elvish Mystic')]
    deck.append({**BASICS['Forest'], 'card_name': 'Forest', 'quantity': 52})
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=13)
    state.pregame_pending = False
    state.active_player = state.priority_player = caster
    state.step = Step.PRECOMBAT_MAIN
    state.players[caster].mana_pool = {'G': 20}  # Trusted existing resource fixture.
    for _ in range(len(state.players[caster].library)):
        draw_card(state, caster)  # Actual native draws, not an invented hand/event.
    return state


def act(state, player, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), player, action)
    assert serialize_match_snapshot(state) == before
    return result


def paid(state, caster):
    menu = RulesEngine().legal_moves(state, caster)
    move = next(move for move in menu if move['type'] == 'cast_spell'
                and 'Creature' in state.cards[move['card_id']].types)
    cid = move['card_id']
    state = act(state, caster, {'type': 'cast_spell', 'card_id': cid})
    assert state.stack[-1].source_card_id == cid
    assert state.stack[-1].payload['mana_spent'] == 1
    for _ in range(40):
        if not state.stack:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert not state.stack and state.cards[cid].zone == Zone.BATTLEFIELD
    return state, cid


@pytest.mark.parametrize('caster', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_six_paid_public_creatures_are_six_physical_ids_not_spell_entry_double_count(caster, roundtrip):
    state = game(caster)
    used = []
    for _ in range(6):
        state, cid = paid(state, caster)
        used.append(cid)
    if roundtrip:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert len(set(used)) == 6
    assert set(state.sideboard_facts['seats'][str(3-caster)]['observed_creatures']) == set(used)
    assert state.sideboard_facts['seats'][str(caster)]['observed_creatures'] == []
    assert set(state.sideboard_facts['seats'][str(caster)]['protected']) == set(used)
    assert state.players[caster].mana_pool['G'] == 14


@pytest.mark.parametrize('caster', [1, 2])
def test_actual_used_copy_protects_other_held_copies_of_original_inventory_entry(caster):
    state, used = paid(game(caster), caster)
    key = state.sideboard_facts['inventory'][used]['stock_key']
    remaining = [cid for cid in state.players[caster].hand
                 if state.sideboard_facts['inventory'][cid]['stock_key'] == key]
    assert len(remaining) == 3
    assert used in state.sideboard_facts['seats'][str(caster)]['protected']
    assert not set(remaining) & set(held_unused_ids(state, caster))


@pytest.mark.parametrize('caster', [1, 2])
def test_rejected_unfunded_real_creature_cast_cannot_publish_fact_updates(caster):
    from rules_engine.action_validation import ActionRejected
    state = game(caster)
    state.players[caster].mana_pool = {}
    source = next(cid for cid in state.players[caster].hand if 'Creature' in state.cards[cid].types)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), caster, {'type': 'cast_spell', 'card_id': source})
    assert serialize_match_snapshot(state) == before
    assert state.sideboard_facts['seats'][str(3-caster)]['observed_creatures'] == []
