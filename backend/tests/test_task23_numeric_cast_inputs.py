"""Profile inputs in actual cast bias; no new weights or target permissions."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from knowledge import service
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_ai_knowledge_profile_consumer import RAW, position as factory_position
from tests.test_task23_checked_removal_baseline import add_profiled
from tests.test_task23_numeric_priority_baseline import position
from tests.vraska_full import test_full_vraska as rules


def removal_move(state, seat, cid):
    return next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'cast_spell' and m['card_id'] == cid)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_cast_bias_reads_validated_numeric_carrier_and_replaces_low_premium(seat, monkeypatch):
    state, removal, _, engine, vanilla = position(seat, 'Zulaport Cutthroat')
    state.players[3 - seat].battlefield.remove(engine)
    state.players[3 - seat].library.append(engine)
    state.cards[engine].move_to_zone(rules.Zone.LIBRARY)
    move = removal_move(state, seat, removal)
    reads = []
    original = service.estimate_for

    def observed(card):
        result = original(card)
        reads.append((card.id, None if result is None else result.tier))
        return result

    monkeypatch.setattr(service, 'estimate_for', observed)
    before = serialize_match_snapshot(state)
    assert AIAgent(difficulty='strong', archetype='Midrange')._cast_bias(state, move, seat) == 0
    assert (vanilla, 1) in reads
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['missing', 'malformed', 'stale', 'suppressed', 'typechange'])
def test_unavailable_priority_is_none_and_entire_legacy_cast_branch_is_exact(seat, kind):
    state, removal, _, engine, vanilla = position(seat, 'Zulaport Cutthroat')
    card = state.cards[engine]
    if kind == 'missing': card.knowledge_snapshot = {}
    elif kind == 'malformed': card.knowledge_snapshot = {'estimates': {'tier': 3}}
    elif kind == 'stale': card.oracle_text += '\n'
    elif kind == 'suppressed': add_keyword_effect(state, engine, ['all abilities'], operation='remove')
    else:
        from rules_engine.type_effects import add_type_effect
        add_type_effect(state, engine, ['Artifact'])
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    assert actor._printed_major_threat(state, card) is None
    # A supplied real legal selected target makes unavailable fallback explicit.
    move = removal_move(state, seat, removal)
    move = {**move, 'targets': {'target_card_id': engine}}
    legacy = deepcopy(state)
    for item in legacy.cards.values(): item.knowledge_snapshot = {}
    before = serialize_match_snapshot(state)
    assert actor._cast_bias(state, move, seat) == AIAgent(archetype='Midrange')._cast_bias(legacy, move, seat) == 2.0
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_low_printed_tier_counters_preserve_effective_big_pressure(seat):
    state, removal, _, _, vanilla = position(seat, 'Zulaport Cutthroat')
    state.cards[vanilla].counters['+1/+1'] = 4
    assert service.estimate_for(state.cards[vanilla]).tier == 1
    move = {**removal_move(state, seat, removal), 'targets': {'target_card_id': vanilla}}
    actor = AIAgent(archetype='Midrange')
    assert actor._printed_major_threat(state, state.cards[vanilla]) is False
    assert actor._cast_bias(state, move, seat) == 2.0


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_pending_growth_keeps_exact_legacy_priority_not_tier_demote(seat):
    state, removal, _, engine, _ = position(seat, 'Sprite Dragon')
    bolt = add_profiled(state, RAW['Lightning Bolt'], 3 - seat, rules.Zone.HAND)
    state.active_player = state.priority_player = 3 - seat
    state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': bolt.id,
                                      'targets': {'target_player': seat}})
    state = rules.act(state, 3 - seat, {'type': 'pass_priority'})
    assert len(state.stack) == 2
    move = removal_move(state, seat, removal)
    actor = AIAgent(archetype='Midrange')
    assert actor._premium_removal_priority(state, move, seat) is None
    legacy = deepcopy(state)
    for item in legacy.cards.values(): item.knowledge_snapshot = {}
    assert actor._cast_bias(state, move, seat) == AIAgent(archetype='Midrange')._cast_bias(legacy, move, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_indexed_cast_face_identity_and_mismatch_are_checked(seat):
    from rules_engine.card_faces import select_cast_face
    state, _ = factory_position(seat)
    card = next(c for c in state.cards.values() if c.owner == seat and c.card_faces)
    actor = AIAgent(archetype='Midrange')
    for index in (0, 1):
        face = select_cast_face(card, index)
        estimate = service.estimate_for(face)
        assert estimate is not None
        assert actor._printed_major_threat(state, face) == (estimate.tier >= 2)
    wrong = select_cast_face(card, 1)
    wrong.selected_face_index = 0
    assert actor._printed_major_threat(state, wrong) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_validated_tier_replaces_only_printed_big_deployment_limb_actual_paid_surface(seat):
    state, _, _, _, _ = position(seat, 'Llanowar Elves')
    card = add_profiled(state, RAW['Zulaport Cutthroat'], seat, rules.Zone.HAND)
    move = removal_move(state, seat, card.id)
    actor = AIAgent(archetype='Control')
    legacy = deepcopy(state)
    legacy.cards[card.id].knowledge_snapshot = {}
    original = serialize_match_snapshot(state)
    assert actor._printed_major_threat(state, card) is True
    assert actor._cast_bias(state, move, seat) > actor._cast_bias(legacy, move, seat)
    result = rules.act(state, seat, {'type': 'cast_spell', 'card_id': card.id, 'targets': {}})
    assert result.stack[-1].payload['mana_spent'] == 2
    result = rules.settle(result)
    assert result.cards[card.id].zone == rules.Zone.BATTLEFIELD
    assert serialize_match_snapshot(state) == original


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_humility_prospective_entry_keeps_exact_legacy_deployment(seat):
    import json
    from game_state.state import assign_static_order_on_battlefield_entry
    from rules_engine.continuous import effective_power, effective_toughness, printed_abilities_suppressed

    state, _, _, _, _ = position(seat, 'Llanowar Elves')
    cards = json.loads((rules.ROOT.parent / 'fixtures/ability_suppression.json').read_bytes())
    raw = next(card for card in cards if card['name'] == 'Humility')
    constructor = raw | {key: raw.get(key) or '' for key in ('power', 'toughness', 'loyalty')}
    resident = rules.add(state, constructor, 3 - seat, rules.Zone.BATTLEFIELD, old_board=True)
    assign_static_order_on_battlefield_entry(state, resident.id)
    entrant = add_profiled(state, RAW['Zulaport Cutthroat'], seat, rules.Zone.HAND)
    assert service.estimate_for(entrant).tier == 3
    assert not printed_abilities_suppressed(state, entrant.id)
    before = serialize_match_snapshot(state)
    actor = AIAgent(archetype='Control')
    assert actor._printed_major_threat(state, entrant) is None
    legacy = deepcopy(state)
    legacy.cards[entrant.id].knowledge_snapshot = {}
    move = removal_move(state, seat, entrant.id)
    assert actor._cast_bias(state, move, seat) == actor._cast_bias(legacy, move, seat)
    result = rules.act(state, seat, {'type': 'cast_spell', 'card_id': entrant.id, 'targets': {}})
    assert result.stack[-1].payload['mana_spent'] == 2
    result = rules.settle(result)
    assert result.cards[entrant.id].zone == rules.Zone.BATTLEFIELD
    assert printed_abilities_suppressed(result, entrant.id)
    assert (effective_power(result, entrant.id), effective_toughness(result, entrant.id)) == (1, 1)
    assert serialize_match_snapshot(state) == before
