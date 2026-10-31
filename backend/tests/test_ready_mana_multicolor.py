"""Canonical R1: marginal capacity must not erase an exact ready-board payment."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pickle
import random
import sys

import pytest

from ai.agent import AIAgent
from ai.action_contract import complete_action
import ai.mana_resource_policy as policy
from ai.information import decision_view
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine import costs as native_costs
from rules_engine.engine import RulesEngine

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'ready_mana_multicolor'


def fixture_rows():
    provenance = json.loads((FIXTURES / 'PROVENANCE.json').read_text())
    rows = {}
    for entry in provenance['rows']:
        raw = (FIXTURES / entry['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        row = json.loads(raw)
        assert row['object'] == 'card' and row['name'] == entry['name']
        assert row['oracle_id'] == entry['oracle_id']
        assert row['id'] == entry['scryfall_id']
        assert entry['http']['status'] == 200
        rows[row['name']] = row
    assert set(rows) == {'Azorius First-Wing', 'Azorius Guildgate', 'Duress',
                         'Hallowed Fountain', 'Mountain', 'Savage Lands'}
    return rows


ROWS = fixture_rows()


def position(seat):
    deck = [{**row, 'card_name': name, 'quantity': 1 if name != 'Mountain' else 15}
            for name, row in ROWS.items()]
    state = MatchFactory.from_decks(deck, deck, seed=131731, game_id=f'r1-canonical-seat-{seat}')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.turn, state.step = 5, Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.mana_pool.clear()
        player.snow_mana_pool.clear()
        player.restricted_mana_pool.clear()
    placed = {}
    for name in ROWS:
        card = next(state.cards[cid] for cid in state.players[seat].library if state.cards[cid].name == name)
        state.players[seat].library.remove(card.id)
        zone = Zone.BATTLEFIELD if name in ('Hallowed Fountain', 'Mountain') else Zone.HAND
        card.move_to_zone(zone)
        getattr(state.players[seat], zone.value).append(card.id)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, card.id)
            card.tapped = card.summoning_sick = False
        raw = ROWS[name]
        assert (card.name, card.oracle_text, card.type_line, card.mana_cost) == (
            raw['name'], raw['oracle_text'], raw['type_line'], raw['mana_cost'])
        assert card.printed_power == raw.get('power')
        assert card.printed_toughness == raw.get('toughness')
        placed[name] = card.id
    return state, placed


def digest(state):
    return hashlib.sha256(pickle.dumps(state, protocol=5)).hexdigest()


def available(state, seat, cid):
    card = state.cards[cid]
    options = native_costs.collect_cost_options(state, seat, card)
    assert len(options) == 1 and options[0].mana_cost == ROWS[card.name]['mana_cost']
    return native_costs.check_cost_option_available(state, seat, card, options[0])


@pytest.mark.parametrize('seat', [1, 2])
def test_tapped_land_override_retains_known_ready_multicolor_payment(seat, monkeypatch):
    state, ids = position(seat)
    rules, agent = RulesEngine(), AIAgent('strong', 'Midrange')
    legal = rules.legal_moves(state, seat)
    selected, alternative = [complete_action(next(move for move in legal
        if move['type'] == 'play_land' and move.get('card_id') == ids[name]))
        for name in ('Azorius Guildgate', 'Savage Lands')]
    choices = [selected, alternative]
    root_before, rng_before, state_rng_before = digest(state), random.getstate(), state.rng.getstate()
    choices_before = deepcopy(choices)
    agent_before = pickle.dumps(vars(agent), protocol=5)
    view, _ = decision_view(state, seat, legal)
    universe = policy._known_land_costs(view, seat)
    assert universe is not None
    assert {cid for cid, _ in universe[0]} == {ids['Azorius First-Wing'], ids['Duress']}
    assert universe[1] == {'W': 1, 'U': 1, 'B': 1, 'R': 0, 'G': 0, 'C': 0, 'S': 0, 'generic': 3}

    projected = [checked_action(view, rules, seat, action) for action in choices]
    for board, action in zip(projected, choices):
        assert board.cards[action['card_id']].zone == Zone.BATTLEFIELD
        assert board.cards[action['card_id']].tapped
        assert board.players[seat].life == view.players[seat].life
        assert not board.stack and not board.pending_mechanic_choice
        assert not board.pending_replacement_choice and not board.pending_trigger_order
        assert (board.turn, board.step, board.active_player, board.priority_player) == (
            view.turn, view.step, seat, seat)
    current_payments = [[available(board, seat, ids[name]) for name in ('Azorius First-Wing', 'Duress')]
                        for board in projected]
    ready = [policy._ready_board(board, seat) for board in projected]
    ready_payments = [[available(board, seat, ids[name]) for name in ('Azorius First-Wing', 'Duress')]
                      for board in ready]
    assert current_payments == [[False, False], [False, False]]
    assert ready_payments == [[True, False], [False, True]]

    cast = complete_action({'type': 'cast_spell', 'card_id': ids['Azorius First-Wing'], 'targets': {}})
    paid = checked_action(ready[0], rules, seat, cast)
    assert paid.stack[-1].source_card_id == ids['Azorius First-Wing']
    assert paid.stack[-1].payload['mana_spent'] == 2
    assert ready[0].cards[ids['Azorius First-Wing']].zone == Zone.HAND
    rejected_before = digest(ready[1])
    with pytest.raises(ActionRejected):
        checked_action(ready[1], rules, seat, cast)
    assert digest(ready[1]) == rejected_before
    duress = complete_action({'type': 'cast_spell', 'card_id': ids['Duress'], 'targets': {'target_player': 3-seat}})
    paid_black = checked_action(ready[1], rules, seat, duress)
    assert paid_black.stack[-1].source_card_id == ids['Duress']
    assert paid_black.stack[-1].payload['mana_spent'] == 1

    profiles = [policy._land_coverage(board, seat, *universe) for board in projected]
    assert all(profile is not None for profile in profiles)
    dominant = all(new >= old for old, new in zip(*profiles)) and any(new > old for old, new in zip(*profiles))
    calls = {'exact': 0, 'capacity': 0}
    exact_callers = {}
    real_exact, real_capacity = native_costs.check_cost_option_available, policy._can_pay

    def exact(resources, actor, card, option, *args, **kwargs):
        assert card is resources.cards[card.id], 'Exact option must use its own board card'
        calls['exact'] += 1
        caller = sys._getframe(1).f_code.co_name
        exact_callers[caller] = exact_callers.get(caller, 0) + 1
        return real_exact(resources, actor, card, option, *args, **kwargs)

    def capacity(*args, **kwargs):
        calls['capacity'] += 1
        return real_capacity(*args, **kwargs)

    with monkeypatch.context() as spy:
        spy.setattr(native_costs, 'check_cost_option_available', exact)
        spy.setattr(policy, '_can_pay', capacity)
        result = policy.prefer_nonregressive_land(agent, state, seat, selected, choices)
    assert digest(state) == root_before
    assert random.getstate() == rng_before and state.rng.getstate() == state_rng_before
    assert choices == choices_before and pickle.dumps(vars(agent), protocol=5) == agent_before
    assert result in choices
    assert result == selected, 'Ready WU payment must not be traded for marginal B access'

    assert not dominant
    assert exact_callers == {'available_cast_options_and_hints': 4, '_land_coverage': 8}
    assert calls == {'exact': 12, 'capacity': 48}
    assert exact_callers['_land_coverage'] + calls['capacity'] == 56 <= policy._LAND_PROFILE_MAX_PROBES
    assert len(profiles[0]) == len(profiles[1]) == 28
    # 55 would admit the old 52-probe estimate but must reject the new 56 probes.
    calls.update(exact=0, capacity=0)
    with monkeypatch.context() as spy:
        spy.setattr(policy, '_LAND_PROFILE_MAX_PROBES', 55)
        spy.setattr(native_costs, 'check_cost_option_available', exact)
        spy.setattr(policy, '_can_pay', capacity)
        assert policy.prefer_nonregressive_land(agent, state, seat, selected, choices) == selected
    assert calls == {'exact': 0, 'capacity': 0}
    exact_callers.clear()
    with monkeypatch.context() as spy:
        spy.setattr(policy, '_LAND_PROFILE_MAX_PROBES', 56)
        spy.setattr(native_costs, 'check_cost_option_available', exact)
        spy.setattr(policy, '_can_pay', capacity)
        assert policy.prefer_nonregressive_land(agent, state, seat, selected, choices) == selected
    assert calls == {'exact': 12, 'capacity': 48}
    assert exact_callers == {'available_cast_options_and_hints': 4, '_land_coverage': 8}
    assert digest(state) == root_before and state.rng.getstate() == state_rng_before
    assert random.getstate() == rng_before
    assert choices == choices_before and pickle.dumps(vars(agent), protocol=5) == agent_before
