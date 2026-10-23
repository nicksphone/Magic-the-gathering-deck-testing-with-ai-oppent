"""Full Vraska remains closed; the separate primitive exercises AI destroy guards."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.closed_loyalty import compile_body
from rules_engine.engine import RulesEngine
from tests.loyalty_destruction_diagnostic_support import source
from tests.test_ineffective_destruction import settled_state
from tests.test_pending_removal import CARDS, add_card
from tests.test_self_removal import canonical_cards


def _canonical_vraska():
    encoded = (Path(__file__).parent / 'vraska_full/fixtures/vraska-scryfall-raw.json').read_bytes()
    if hashlib.sha256(encoded).hexdigest() != 'd05bc8f4d639536deb46eabb9f1ee807373418591be1deb1af7d57548d79423f':
        raise ValueError('Full Vraska source changed')
    raw = json.loads(encoded)
    if (raw.get('object'), raw.get('name'), raw.get('id'), raw.get('oracle_id'), len(raw)) != (
            'card', 'Vraska the Unseen', 'a6ab9d2b-6cb3-4477-8d0e-712c530383bd',
            '0d2bbce0-8c27-4b82-ab62-51a0c3cfc9b0', 66):
        raise ValueError('Full Vraska identity changed')
    if hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                 ensure_ascii=False).encode()).hexdigest() != '53bb2bb2183d467d53842a588c074dedc118f62fc8a0ad70e33e2311f69fc7e6':
        raise ValueError('Full Vraska object changed')
    from card_data.sync import ScryfallSyncService
    normalized = ScryfallSyncService._normalize_payload(raw, 'unused:task13-fixture-display')
    entry = {**raw, **normalized, 'card_name': raw['name'], 'quantity': 8,
             'image_uri': None, 'colors': deepcopy(raw.get('colors', [])),
             'card_faces': deepcopy(raw.get('card_faces', []))}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id='canonical-vraska', owner=1, controller=1, zone=Zone.BATTLEFIELD,
                   instance_order=0, summoning_sick=True)


def test_full_canonical_vraska_complete_admission_and_checked_root_are_atomic():
    state, victim, _ = settled_state()
    row = CARDS['Vraska the Unseen']
    card = _canonical_vraska()
    state.cards[card.id] = card
    state.players[1].battlefield.append(card.id)
    before = serialize_match_snapshot(state)
    assert len(card.oracle_text.splitlines()) == 3
    compiled = compile_body(card.oracle_text, card.name)
    assert compiled is not None
    assert [ability['delta'] for ability in compiled['abilities']] == [1, -3, -7]
    assert len(compiled['abilities']) == 3
    assert {move['ability_index'] for move in RulesEngine().legal_moves(state, 1)
            if move.get('card_id') == card.id and move['type'] == 'activate_loyalty'} == {0, 1}
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'activate_loyalty', 'card_id': card.id,
                                               'ability_index': 2, 'targets': {}})
    assert serialize_match_snapshot(state) == before and card.oracle_text == row['oracle_text']
    candidate = checked_action(state, RulesEngine(), 1, {'type': 'activate_loyalty',
        'card_id': card.id, 'ability_index': 1, 'targets': {'target_card_id': victim}})
    from rules_engine.targeting import stack_object_kind
    assert stack_object_kind(candidate, candidate.stack[-1]) == 'activated'
    assert candidate.cards[card.id].loyalty == 2
    assert serialize_match_snapshot(state) == before and card.oracle_text == row['oracle_text']
    while candidate.stack:
        candidate = checked_action(candidate, RulesEngine(), candidate.priority_player, {'type': 'pass_priority'})
    assert candidate.cards[victim].zone == Zone.BATTLEFIELD
    assert candidate.cards[card.id].loyalty == 2
    assert candidate.cards[card.id].oracle_text == row['oracle_text']


def test_closed_diagnostic_ai_holds_indestructible_but_human_can_pay_loyalty():
    state, victim, _ = settled_state()
    card = source(state)
    before = serialize_match_snapshot(state)
    move = next(m for m in RulesEngine().legal_moves(state, 1)
                if m.get('card_id') == card.id and m.get('ability_delta') == -3)
    assert AIAgent()._materialize_action(state, move, 1).get('_invalid_ai_choice')
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, {'type': 'activate_loyalty', 'card_id': card.id,
                        'ability_index': 0, 'targets': {'target_card_id': victim}})
    assert state.cards[card.id].loyalty == 2
    while state.stack:
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.cards[victim].zone == Zone.BATTLEFIELD


def test_closed_diagnostic_ai_uses_original_canonical_creature_for_death_win():
    state, _, _ = settled_state()
    add_card(state, 'Bastion of Remembrance', Zone.BATTLEFIELD)
    creature = add_card(state, 'Sprite Dragon', Zone.BATTLEFIELD)
    walker = source(state)
    state.players[2].life = 1
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Midrange').choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action['type'] == 'activate_loyalty'
    assert decision.action['card_id'] == walker.id
    assert decision.action['targets']['target_card_id'] == creature.id
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, decision.action)
    while state.stack and state.winner is None:
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.winner == 1 and state.players[2].life == 0
    assert state.cards[creature.id].zone == Zone.GRAVEYARD
    assert state.cards[walker.id].loyalty == 2


def test_unknown_companion_still_blocks_the_entire_diagnostic_surface_atomically():
    state, victim, _ = settled_state()
    card = source(state)
    card.oracle_text += '\nUnaccounted diagnostic companion.'
    before = serialize_match_snapshot(state)
    assert compile_body(card.oracle_text, card.name) is None
    assert not any(m.get('card_id') == card.id for m in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'activate_loyalty', 'card_id': card.id,
                         'ability_index': 0, 'targets': {'target_card_id': victim}})
    assert serialize_match_snapshot(state) == before
