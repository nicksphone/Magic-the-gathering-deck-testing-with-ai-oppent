"""Bounded canonical cost search, including the independently reviewed C(30,15)."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from ai.action_contract import complete_action
from ai.casting_resources import complete_fixed_cost_choice
from game_state.state import MatchFactory, Step, Zone
from rules_engine import costs, spell_cost_witness
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_joint_cast_resources import ROWS, snapshot


def large_position(seat, lands=2):
    rows = json.loads((Path(__file__).parent / 'fixtures/variable_spell_costs.json').read_bytes())
    spell = next(row for row in rows if row['name'] == 'Sickening Dreams')
    entries = [{**row, 'quantity': quantity, 'card_name': row['name'], 'image_uri': None}
               for row, quantity in [(spell, 3), (ROWS['Island'], 40), (ROWS['Swamp'], 4)]]
    state = MatchFactory.from_decks(entries, entries, seed=61103)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    state.turn = 5
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
    player = state.players[seat]
    def place(name, zone):
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        getattr(player, zone.value).append(cid)
        state.cards[cid].move_to_zone(zone)
        state.cards[cid].tapped = state.cards[cid].summoning_sick = False
        return cid
    cid = place('Sickening Dreams', Zone.HAND)
    hand = [place('Island', Zone.HAND) for _ in range(30)]
    mana = [place('Swamp', Zone.BATTLEFIELD) for _ in range(lands)]
    assert state.cards[cid].oracle_text == spell['oracle_text']
    action = {'type': 'cast_spell', 'card_id': cid, 'targets': {'x_value': 15},
              'cost_choice': {'id': 'base', 'discard_card_ids': hand[:15]}}
    return state, action, hand, mana


def observe(monkeypatch, agent):
    counts = {'native_yields': 0, 'rank': 0, 'selections': 0}
    original = spell_cost_witness.fixed_cost_selections
    def bounded(*args, **kwargs):
        for choice in original(*args, **kwargs):
            counts['native_yields'] += 1
            assert counts['native_yields'] <= 64, 'Subset enumeration exceeded the declared AI budget'
            yield choice
    select = costs.additional_cost_selection
    def selections(*args, **kwargs):
        counts['selections'] += 1
        assert counts['selections'] <= 70, 'Native validation visits must be bounded'
        return select(*args, **kwargs)
    rank = agent._hand_retention_value
    def ranked(*args, **kwargs):
        counts['rank'] += 1
        assert counts['rank'] <= 30, 'Rank each relevant hand card at most once'
        return rank(*args, **kwargs)
    monkeypatch.setattr(spell_cost_witness, 'fixed_cost_selections', bounded)
    monkeypatch.setattr(costs, 'additional_cost_selection', selections)
    monkeypatch.setattr(agent, '_hand_retention_value', ranked)
    return counts


def complete(state, action, seat, explicit=None):
    before = snapshot(state)
    rng, local = random.getstate(), state.rng.getstate()
    original = deepcopy(action)
    result = complete_fixed_cost_choice(ACTIVE_AGENT, state, action, seat,
                                        {'discard_x': True}, explicit)
    assert snapshot(state) == before and action == original
    assert random.getstate() == rng and state.rng.getstate() == local
    return result


@pytest.fixture(autouse=True)
def agent():
    global ACTIVE_AGENT
    ACTIVE_AGENT = AIAgent('master', 'Control')
    return ACTIVE_AGENT


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fixed', [False, True])
@pytest.mark.parametrize('branch', [
    {'resource_payment': {'improvise': ['unavailable']}},
    {'resource_payment': []},
    {'hybrid_choices': []},
])
def test_invariant_invalid_explicit_branch_never_searches_subsets(monkeypatch, agent, seat, fixed, branch):
    state, action, hand, mana = large_position(seat)
    if isinstance(branch.get('resource_payment'), dict):
        branch = {'resource_payment': {'improvise': [mana[0]]}}
    action.update(deepcopy(branch))
    counts = observe(monkeypatch, agent)
    result = complete(state, action, seat, deepcopy(action['cost_choice']) if fixed else None)
    assert result.get('_invalid_ai_choice')
    assert not result.get('_ai_cost_search_exhausted')
    assert all(result[key] == value for key, value in action.items())
    assert counts['native_yields'] == counts['rank'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_malformed_partial_explicit_cost_is_rejected_before_ranking(monkeypatch, agent, seat):
    state, action, hand, mana = large_position(seat)
    fixed = {'id': 'base', 'sacrifice_card_ids': ['missing']}
    action['cost_choice'].update(fixed)
    counts = observe(monkeypatch, agent)
    result = complete(state, action, seat, fixed)
    assert result.get('_invalid_ai_choice')
    assert result['cost_choice'] == action['cost_choice']
    assert counts['native_yields'] == counts['rank'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_fully_explicit_infeasible_payment_never_searches_subsets(monkeypatch, agent, seat):
    state, action, hand, mana = large_position(seat, lands=1)
    counts = observe(monkeypatch, agent)
    result = complete(state, action, seat, deepcopy(action['cost_choice']))
    assert result.get('_invalid_ai_choice') and not result.get('_ai_cost_search_exhausted')
    assert result['cost_choice'] == action['cost_choice']
    assert counts['native_yields'] == counts['rank'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_large_payable_preference_is_preserved_without_search(monkeypatch, agent, seat):
    state, action, hand, mana = large_position(seat)
    counts = observe(monkeypatch, agent)
    assert complete(state, action, seat) == action
    assert counts['native_yields'] == counts['rank'] == 0
    checked_action(state, RulesEngine(), seat, complete_action(action))


@pytest.mark.parametrize('seat', [1, 2])
def test_large_fallback_returns_first_ranked_native_payable_witness(monkeypatch, agent, seat):
    state, action, hand, mana = large_position(seat)
    action['cost_choice']['discard_card_ids'] = []
    counts = observe(monkeypatch, agent)
    result = complete(state, action, seat)
    assert not result.get('_invalid_ai_choice')
    assert result['cost_choice']['discard_card_ids'] == hand[:15]
    assert counts['native_yields'] <= 1 and counts['selections'] <= 4
    assert counts['rank'] <= 30
    after = checked_action(state, RulesEngine(), seat, complete_action(result))
    assert after.stack[-1].payload['mana_spent'] == 2
    assert len(after.players[seat].graveyard) == 15
