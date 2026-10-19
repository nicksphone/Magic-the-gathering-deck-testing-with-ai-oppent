"""Unmodified policy observations, genuine checked actions, trusted initial boards."""
from copy import deepcopy
import json

import pytest

from ai.agent import AIAgent
from ai.heuristics import evaluate_board
from game_state.serializers import serialize_match_snapshot
from knowledge.service import estimate_for
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_task23_checked_removal_baseline import DIVINATION, add_profiled
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.vraska_full import test_full_vraska as rules


def position(seat, name):
    state = rules.bare(seat)
    state.turn = 6
    state.players[seat].mana_pool = {'B': 1, 'U': 1, 'C': 4}
    removal = add_profiled(state, RAW['Go for the Throat'], seat, rules.Zone.HAND)
    value = add_profiled(state, DIVINATION, seat, rules.Zone.HAND)
    engine = add_profiled(state, RAW[name], 3 - seat, rules.Zone.BATTLEFIELD)
    vanilla = add_profiled(state, rules.BEAR, 3 - seat, rules.Zone.BATTLEFIELD)
    # Trusted initial counter, not a natural/paid counter-placement certificate.
    vanilla.counters['-1/-1'] = 1
    assert (effective_power(state, engine.id), effective_toughness(state, engine.id)) == (1, 1)
    assert (effective_power(state, vanilla.id), effective_toughness(state, vanilla.id)) == (1, 1)
    return state, removal.id, value.id, engine.id, vanilla.id


def choose_and_record(state, seat, removal, value, engine, vanilla, label):
    legal = RulesEngine().legal_moves(state, seat)
    offered = {m['card_id'] for m in legal if m['type'] == 'cast_spell'}
    assert {removal, value} <= offered
    before = serialize_match_snapshot(state)
    actor = AIAgent(difficulty='strong', archetype='Control')
    scores = {cid: actor._creature_threat_score(state, cid, seat) for cid in (engine, vanilla)}
    biases = {m['card_id']: actor._cast_bias(state, m, seat) for m in legal
              if m['type'] == 'cast_spell' and m['card_id'] in {removal, value}}
    decision = actor.choose_action(state, legal, seat)
    assert serialize_match_snapshot(state) == before
    print('NUMERIC_BASELINE=' + json.dumps({'case': label, 'seat': seat,
        'tier': estimate_for(state.cards[engine]).tier, 'threat_scores': scores,
        'cast_biases': biases, 'action': decision.action}, sort_keys=True))
    result = rules.act(state, seat, decision.action)
    if decision.action['type'] == 'cast_spell':
        spent = 2 if decision.action['card_id'] == removal else 3
        assert result.stack[-1].payload['mana_spent'] == spent
    result = rules.settle(result)
    assert result.winner is None and serialize_match_snapshot(state) == before
    return decision, result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Zulaport Cutthroat', 'Llanowar Elves'])
def test_same_effective_pt_engine_full_menu_actual_paid_choice_baseline(seat, name):
    state, removal, value, engine, vanilla = position(seat, name)
    choose_and_record(state, seat, removal, value, engine, vanilla, name)


@pytest.mark.parametrize('seat', [1, 2])
def test_only_low_tier_target_full_menu_paid_resolution_baseline(seat):
    state, removal, value, engine, vanilla = position(seat, 'Llanowar Elves')
    # Remove the mana creature from this explicitly declared starting board.
    state.players[3 - seat].battlefield.remove(engine)
    state.players[3 - seat].library.append(engine)
    state.cards[engine].move_to_zone(rules.Zone.LIBRARY)
    assert estimate_for(state.cards[vanilla]).tier == 1
    choose_and_record(state, seat, removal, value, vanilla, vanilla, 'only tier1 vanilla')


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_paid_noncreature_growth_same_pt_checked_counterfactuals(seat):
    state, removal, _, engine, vanilla = position(seat, 'Sprite Dragon')
    # Equalize current evasion through the existing object-bound layer seam;
    # this is not a paid/natural animation or keyword-grant episode.
    add_keyword_effect(state, vanilla, ['flying', 'haste'])
    bolt = add_profiled(state, RAW['Lightning Bolt'], 3 - seat, rules.Zone.HAND)
    state.active_player = state.priority_player = 3 - seat
    state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': bolt.id,
                                      'targets': {'target_player': seat}})
    assert state.stack[0].payload['mana_spent'] == 1
    assert len(state.stack) == 2 and state.stack[-1].source_card_id == engine
    state = rules.act(state, 3 - seat, {'type': 'pass_priority'})
    assert state.priority_player == seat
    before = serialize_match_snapshot(state)
    actor = AIAgent(difficulty='strong', archetype='Control')
    legal = RulesEngine().legal_moves(state, seat)
    menu = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == removal)
    assert {engine, vanilla} <= {t['id'] for t in menu['target_hints']['creature_targets']}
    scores = {cid: actor._creature_threat_score(state, cid, seat) for cid in (engine, vanilla)}
    decision = actor.choose_action(state, legal, seat)
    endpoints = {}
    for target in (engine, vanilla):
        result = rules.act(state, seat, {'type': 'cast_spell', 'card_id': removal,
                                        'targets': {'target_card_id': target}})
        assert result.stack[-1].payload['mana_spent'] == 2
        result = rules.settle(result)
        assert result.cards[target].zone == rules.Zone.GRAVEYARD
        assert result.players[seat].life == 17 and result.winner is None
        endpoints[target] = evaluate_board(result, seat)
    assert endpoints[engine] > endpoints[vanilla]
    assert serialize_match_snapshot(state) == before
    print('NUMERIC_BASELINE=' + json.dumps({'case': 'actual pending growth', 'seat': seat,
        'tiers': {cid: estimate_for(state.cards[cid]).tier for cid in (engine, vanilla)},
        'threat_scores': scores, 'checked_endpoints': endpoints, 'action': decision.action}, sort_keys=True))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('high', [True, False])
def test_midrange_original_plan_high_low_removal_versus_value_bias(seat, high):
    state, removal, value, engine, vanilla = position(seat, 'Zulaport Cutthroat')
    if not high:
        state.players[3 - seat].battlefield.remove(engine)
        state.players[3 - seat].library.append(engine)
        state.cards[engine].move_to_zone(rules.Zone.LIBRARY)
    legal = RulesEngine().legal_moves(state, seat)
    moves = {m['card_id']: m for m in legal if m['type'] == 'cast_spell'}
    assert {removal, value} <= set(moves)
    before = serialize_match_snapshot(state)
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    biases = {cid: actor._cast_bias(state, moves[cid], seat) for cid in (removal, value)}
    decision = actor.choose_action(state, legal, seat)
    result = rules.act(state, seat, decision.action)
    result = rules.settle(result)
    assert result.winner is None and serialize_match_snapshot(state) == before
    print('NUMERIC_BASELINE=' + json.dumps({'case': 'Midrange high' if high else 'Midrange low',
        'seat': seat, 'cast_biases': biases, 'action': decision.action}, sort_keys=True))
    if high:
        assert biases[removal] > biases[value]
    else:
        # Original Task2.3 acceptance, not a new fixed winner/target preference.
        assert biases[removal] < biases[value]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['opaque', 'stale', 'counters', 'Humility'])
def test_printed_advice_does_not_replace_current_state_or_legacy_fallback(seat, kind):
    from ai.information import decision_view
    from game_state.state import assign_static_order_on_battlefield_entry
    from rules_engine.continuous import printed_abilities_suppressed

    state, removal, value, engine, vanilla = position(seat, 'Zulaport Cutthroat')
    if kind == 'opaque':
        state.players[3 - seat].battlefield.remove(engine)
        state.players[3 - seat].hand.append(engine)
        state.cards[engine].move_to_zone(rules.Zone.HAND)
        view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
        assert estimate_for(view.cards[engine]) is None
        assert not view.cards[engine].knowledge_snapshot
    elif kind == 'stale':
        state.cards[engine].oracle_text += '\n'
        assert estimate_for(state.cards[engine]) is None
        legacy = deepcopy(state)
        for card in legacy.cards.values():
            card.knowledge_snapshot = {}
        legal = RulesEngine().legal_moves(state, seat)
        original = serialize_match_snapshot(state)
        actor = AIAgent(difficulty='strong', archetype='Control')
        fallback = AIAgent(difficulty='strong', archetype='Control')
        assert actor._creature_threat_score(state, engine, seat) == fallback._creature_threat_score(legacy, engine, seat)
        assert actor.choose_action(state, legal, seat).action == fallback.choose_action(legacy, legal, seat).action
        assert serialize_match_snapshot(state) == original
    elif kind == 'counters':
        state.cards[vanilla].counters['+1/+1'] = 4
        assert estimate_for(state.cards[vanilla]).tier == 1
        assert (effective_power(state, vanilla), effective_toughness(state, vanilla)) == (5, 5)
        actor = AIAgent(difficulty='strong', archetype='Control')
        assert actor._creature_threat_score(state, vanilla, seat) > actor._creature_threat_score(state, engine, seat)
    else:
        cards = json.loads((rules.ROOT.parent / 'fixtures/ability_suppression.json').read_bytes())
        humility = next(raw for raw in cards if raw['name'] == 'Humility')
        # This legacy helper expects absent/string PT, not official nullable PT.
        # Adapt only its constructor input; full canonical RAW/Oracle stay intact.
        constructor = humility | {key: humility.get(key) or '' for key in ('power', 'toughness', 'loyalty')}
        added = rules.add(state, constructor, 3 - seat, rules.Zone.BATTLEFIELD, old_board=True)
        assert added.oracle_text == humility['oracle_text']
        assign_static_order_on_battlefield_entry(state, added.id)
        assert printed_abilities_suppressed(state, engine)
        assert estimate_for(state.cards[engine]).tier == 3
        actor = AIAgent(difficulty='strong', archetype='Control')
        # Humility sets base PT; the vanilla's declared -1/-1 counter remains.
        # Neither printed tier nor a false equal-PT premise can override it.
        assert (effective_power(state, engine), effective_toughness(state, engine)) == (1, 1)
        assert (effective_power(state, vanilla), effective_toughness(state, vanilla)) == (0, 0)
        assert actor._creature_threat_score(state, engine, seat) == pytest.approx(1.55)
        assert actor._creature_threat_score(state, vanilla, seat) == 0
        legal = RulesEngine().legal_moves(state, seat)
        assert {removal, value} <= {m['card_id'] for m in legal if m['type'] == 'cast_spell'}
        before = serialize_match_snapshot(state)
        decision = actor.choose_action(state, legal, seat)
        result = rules.settle(rules.act(state, seat, decision.action))
        assert result.winner is None and serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_low_tier_actual_choice_causal_return_path_without_policy_patching(seat):
    import sys

    state, removal, value, engine, vanilla = position(seat, 'Llanowar Elves')
    state.players[3 - seat].battlefield.remove(engine)
    state.players[3 - seat].library.append(engine)
    state.cards[engine].move_to_zone(rules.Zone.LIBRARY)
    actor = AIAgent(difficulty='strong', archetype='Control')
    original = serialize_match_snapshot(state)
    returned = []
    code = AIAgent._forced_sweeper_stabilization_line.__code__

    def trace(frame, event, value):
        if frame.f_code is code and event == 'return':
            returned.append(None if value is None else (value.get('type'), value.get('card_id')))

    previous = sys.getprofile()
    sys.setprofile(trace)
    try:
        decision = actor.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    finally:
        sys.setprofile(previous)
    assert returned == [('cast_spell', removal)]
    assert decision.action['card_id'] == removal
    assert 'stabil' in decision.reasoning.lower()
    assert serialize_match_snapshot(state) == original
    print('NUMERIC_CAUSAL_RETURN=' + json.dumps({'seat': seat, 'function': code.co_name,
        'returned': returned, 'reason': decision.reasoning}, sort_keys=True))
