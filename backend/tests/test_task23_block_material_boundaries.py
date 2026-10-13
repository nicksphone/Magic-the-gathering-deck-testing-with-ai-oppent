"""Real checked boundaries plus explicitly inert unknown-frame probes."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import assign_static_order_on_battlefield_entry
from rules_engine.continuous import effective_power, printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_task23_block_material_baseline import position, blocked, Zone
from tests.vraska_full.test_full_vraska import add


def search(root, move):
    return AIAgent(difficulty='strong', archetype='Midrange')._search_block_assignments(
        root, move['attackers'], move['blockers'])


@pytest.mark.parametrize('seat', [1, 2])
def test_strong_reuses_checked_material_search_for_genuine_recurring_major(seat):
    root, _, block, attacker, engine, vanilla = position(seat, ('engine', 'vanilla'))
    before = serialize_match_snapshot(root)
    result = search(root, block)
    assert result is not None, 'The observed nonlethal material trade has a bounded checked search'
    bids = result.get(attacker) or []
    outcome = blocked(root, seat, attacker, [bids] if isinstance(bids, str) else bids)
    assert outcome.cards[engine].zone == Zone.BATTLEFIELD
    assert outcome.cards[vanilla].zone == Zone.GRAVEYARD
    assert outcome.players[seat].life == 21 and outcome.winner is None
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', ['missing', 'stale', 'suppressed', 'pending'])
def test_material_admission_unknown_or_suppressed_stays_legacy(seat, variant):
    root, _, block, _, _, _ = position(seat, ('engine', 'vanilla'),
                                     variant if variant != 'pending' else 'known')
    if variant == 'pending':
        # Inert unresolved-frame probe, not a fabricated native continuation.
        root.pending_mechanic_choice = {'kind': 'review_only_unresolved'}
    before = serialize_match_snapshot(root)
    assert search(root, block) is None
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_canonical_humility_suppression_does_not_admit_printed_engine(seat):
    root, _, block, attacker, engine, vanilla = position(seat, ('engine', 'vanilla'))
    for cid in (attacker, vanilla):
        root.cards[cid].counters.clear()  # Declared fixture counters, not a paid counter-removal episode.
    data = json.loads((Path(__file__).parent / 'fixtures/ability_suppression.json').read_bytes())
    raw = next(card for card in data if card['name'] == 'Humility')
    resident = add(root, raw | {key: raw.get(key) or '' for key in ('power', 'toughness', 'loyalty')},
                   3 - seat, Zone.BATTLEFIELD, old_board=True)
    assign_static_order_on_battlefield_entry(root, resident.id)
    assert root.cards[resident.id].oracle_text == raw['oracle_text']
    assert printed_abilities_suppressed(root, engine)
    assert all(effective_power(root, cid) == 1 for cid in (attacker, engine, vanilla))
    before = serialize_match_snapshot(root)
    assert search(root, block) is None
    outcome = blocked(root, seat, attacker, [vanilla])
    assert outcome.players[seat].life == outcome.players[3-seat].life == 20
    assert outcome.winner is None
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_nonbattlefield_source_is_not_a_material_admission(seat):
    root, _, block, _, engine, _ = position(seat, ('engine', 'vanilla'))
    # Inert stale-menu probe only; no legal action on this deliberately mismatched state.
    root.cards[engine].zone = Zone.LIBRARY
    before = serialize_match_snapshot(root)
    assert search(root, block) is None
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_projection_retains_no_block_when_all_assignments_only_chump(seat):
    root, _, _, attacker, engine, vanilla = position(seat, ('engine', 'vanilla'))
    root.cards[attacker].counters.clear()
    root.cards[attacker].counters['+1/+1'] = 1  # Genuine generic 3/3 public-board fixture.
    moves = RulesEngine().legal_moves(root, seat)
    block = next(move for move in moves if move['type'] == 'block')
    before = serialize_match_snapshot(root)
    result = search(root, block)
    assert result == {}, 'Existing checked chump rejection must preserve legal no-block'
    decision = AIAgent(difficulty='strong', archetype='Midrange').choose_action(root, moves, seat)
    assert decision.action['type'] == 'pass_priority'
    outcome = blocked(root, seat, attacker, [])
    assert outcome.players[seat].life == 17 and outcome.winner is None
    assert all(outcome.cards[cid].zone == Zone.BATTLEFIELD for cid in (engine, vanilla, attacker))
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_lethal_emergency_keeps_terminal_survival_priority(seat):
    root, _, _, attacker, _, _ = position(seat, ('engine', 'vanilla'))
    root.players[seat].life = 1
    add_keyword_effect(root, attacker, ['trample'])
    moves = RulesEngine().legal_moves(root, seat)
    before = serialize_match_snapshot(root)
    decision = AIAgent(difficulty='strong', archetype='Midrange').choose_action(root, moves, seat)
    assert decision.action['type'] == 'block'
    bids = (decision.action.get('blocks') or {}).get(attacker) or []
    outcome = blocked(root, seat, attacker, [bids] if isinstance(bids, str) else bids)
    assert outcome.players[seat].life > 0 and outcome.winner != 3-seat
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_checked_projection_has_no_fabricated_material_plan(seat, monkeypatch):
    root, _, block, _, _, _ = position(seat, ('engine', 'vanilla'))
    actor = AIAgent(difficulty='strong')
    monkeypatch.setattr(actor, '_finish_combat_projection', lambda *args: False)
    before = serialize_match_snapshot(root)
    assert actor._search_block_assignments(root, block['attackers'], block['blockers']) is None
    assert serialize_match_snapshot(root) == before
