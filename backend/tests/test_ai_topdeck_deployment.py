"""Canonical own-list expectations; no historical opponent secrets in fixtures."""
import json
from math import comb
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, is_unknown, topdeck_deployment_value
from ai.pending_effects import planning_copy, settled_public_position
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add
from tests.test_ai_strategic_pass import STYLES


ROWS = json.loads((Path(__file__).parent / 'fixtures/holding_spells/canonical.json').read_text())


def position(seat, name='Storm the Festival', remaining='Black Knight', lands=7):
    deck = [{**ROWS[key], 'card_name': key, 'quantity': count}
            for key, count in [('Forest', 20), ('Swamp', 4),
                               ('Ugin, the Spirit Dragon', 2), (name, 4), (remaining, 30)]]
    state = MatchFactory.from_decks(deck, deck, seed=351)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 19
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.players[seat].life = 9
    for player in state.players.values():
        player.library.extend(player.hand)
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.hand.clear()
    player = state.players[seat]
    for key, zone, count in [(name, Zone.HAND, 1), ('Ugin, the Spirit Dragon', Zone.HAND, 1),
                             ('Forest', Zone.BATTLEFIELD, min(5, lands)),
                             ('Swamp', Zone.BATTLEFIELD, max(0, lands-5))]:
        for _ in range(count):
            cid = next(cid for cid in player.library if state.cards[cid].name == key)
            player.library.remove(cid)
            state.cards[cid].move_to_zone(zone)
            getattr(player, zone.value).append(cid)
    spell = next(state.cards[cid] for cid in player.hand if state.cards[cid].name == name)
    return state, spell


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Storm the Festival', 'Collected Company'])
@pytest.mark.parametrize('style', STYLES)
def test_shared_planner_deploys_affordable_topdeck_spells(seat, name, style):
    state, spell = position(seat, name)
    rules = RulesEngine()
    legal = rules.legal_moves(state, seat)
    assert any(m.get('card_id') == spell.id for m in legal)
    before = serialize_match_snapshot(state)
    view, _ = decision_view(state, seat, legal)
    assert all(is_unknown(view.cards[cid]) for player in view.players.values() for cid in player.library)
    action = AIAgent(difficulty='master', archetype=style).choose_action(state, legal, seat).action
    assert action['type'] == 'cast_spell' and action['card_id'] == spell.id
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['master', 'master_plus'])
def test_deterministic_reload_and_hidden_identity_order_invariance(seat, difficulty):
    state, spell = position(seat)
    before = serialize_match_snapshot(state)
    def choose(s):
        return AIAgent(difficulty=difficulty, archetype='Ramp').choose_action(
            s, RulesEngine().legal_moves(s, seat), seat).action
    expected = choose(state)
    assert expected['card_id'] == spell.id
    assert choose(state) == choose(deserialize_match_snapshot(before)) == expected
    for player in state.players.values():
        player.library.reverse()
        for cid in player.library:
            card = state.cards[cid]
            card.name = 'Counterspell'
            card.types = ['Instant']
            card.mana_cost = '{U}{U}'
            card.oracle_text = 'Counter target spell.'
            card.power = card.toughness = 99
    mutated = serialize_match_snapshot(state)
    assert choose(state) == expected
    assert serialize_match_snapshot(state) == mutated


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('control', ['whiff', 'unpayable', 'prohibited'])
def test_no_forced_deployment_without_benefit_or_payment(seat, control):
    state, spell = position(seat, 'Collected Company',
                            remaining='Ugin, the Spirit Dragon' if control == 'whiff' else 'Black Knight',
                            lands=3 if control == 'unpayable' else 7)
    if control == 'prohibited':
        add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
    rules = RulesEngine()
    legal = rules.legal_moves(state, seat)
    before = serialize_match_snapshot(state)
    assert AIAgent(difficulty='master', archetype='Ramp').choose_action(state, legal, seat).action['type'] == 'pass_priority'
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_expected_hit_cap_matches_hypergeometric_not_library_order(seat):
    state, spell = position(seat, 'Collected Company')
    view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    announced = planning_copy(view)
    RulesEngine().take_action(announced, seat, {'type': 'cast_spell', 'card_id': spell.id}, reject_invalid=True)
    before = serialize_match_snapshot(announced)
    n = len(announced.players[seat].library)
    expected_hits = sum(min(k, 2) * comb(30, k) * comb(n-30, 6-k) / comb(n, 6) for k in range(7))
    assert topdeck_deployment_value(announced, seat) == pytest.approx(.95 * (2*1.35+2*.55+.25) * expected_hits)
    assert settled_public_position(announced, seat, opaque_draw_counts=True) is None
    assert topdeck_deployment_value(announced, 3-seat) == 0
    assert serialize_match_snapshot(announced) == before
    announced.starting_decks[seat] = []
    assert topdeck_deployment_value(announced, seat) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_two_color_hybrid_mana_value_exceeds_canonical_storm_cap(seat):
    from rules_engine.mana import mana_value
    state, spell = position(seat, remaining='Reaper King')
    # Printed {2/color} symbols have MV 2, even when payable with one mana.
    assert ROWS['Reaper King']['mana_cost'] == '{2/W}{2/U}{2/B}{2/R}{2/G}'
    assert mana_value(ROWS['Reaper King']['mana_cost']) == 10
    view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    RulesEngine().take_action(view, seat, {'type': 'cast_spell', 'card_id': spell.id}, reject_invalid=True)
    assert view.stack[-1].effect_key == 'topdeck_put_permanents_battlefield'
    assert view.stack[-1].payload['mv_max'] == 5
    before = serialize_match_snapshot(view)
    n = len(view.players[seat].library)
    # Only the 17 remaining lands qualify; neither MV-10 Reaper nor MV-8 Ugin.
    expected = sum(min(k, 2) * comb(17, k) * comb(n-17, 5-k) / comb(n, 5) for k in range(6))
    assert topdeck_deployment_value(view, seat) == pytest.approx(.95 * .12 * expected)
    assert serialize_match_snapshot(view) == before
    view.players[seat].library.reverse()
    assert topdeck_deployment_value(view, seat) == pytest.approx(.95 * .12 * expected)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Ramp', 'Tokens', 'Drain'])
def test_beneficial_card_selection_still_deploys_without_known_draws(seat, style):
    state, spell = position(seat, 'Memory Deluge')
    state.players[seat].mana_pool = {'U': 2, 'C': 2}
    for cid in state.players[seat].battlefield:
        state.cards[cid].tapped = True
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty='master', archetype=style).choose_action(
        state, RulesEngine().legal_moves(state, seat), seat).action
    assert action['type'] == 'cast_spell' and action['card_id'] == spell.id
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_topdeck_instant_does_not_erase_counter_reservation(seat):
    state, spell = position(seat, 'Collected Company')
    state.active_player = 3-seat
    state.step = Step.UPKEEP
    state.players[seat].mana_pool = {'G': 1, 'U': 2, 'C': 1}
    add(state, 'Counterspell', seat, Zone.HAND, cards=ROWS)
    state.starting_decks[seat].append({**ROWS['Counterspell'], 'card_name': 'Counterspell', 'quantity': 1})
    # A positive but modest deployment expectation must not spend the answer.
    for _ in range(26):
        cid = next(cid for cid in state.players[seat].library if state.cards[cid].name == 'Black Knight')
        state.players[seat].library.remove(cid)
        state.cards[cid].move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(cid)
    # Exactly four mana can pay Company, consuming the two blue mana.
    for cid in state.players[seat].battlefield:
        state.cards[cid].tapped = True
    rules = RulesEngine()
    move = next(m for m in rules.legal_moves(state, seat) if m.get('card_id') == spell.id)
    agent = AIAgent(difficulty='master', archetype='Control')
    before = serialize_match_snapshot(state)
    view, _ = decision_view(state, seat, rules.legal_moves(state, seat))
    rules.take_action(view, seat, {'type': 'cast_spell', 'card_id': spell.id}, reject_invalid=True)
    assert 0 < topdeck_deployment_value(view, seat) < 6
    assert agent._instant_value_reservation(state, move, seat) < 0
    assert agent.choose_action(state, rules.legal_moves(state, seat), seat).action['type'] == 'pass_priority'
    assert serialize_match_snapshot(state) == before
