"""Synthetic parser fences only; never claim altered printings are canonical."""
import json
from pathlib import Path

import pytest
import domain_paid_support as g
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.attached_token_payment import compile_instruction, KEY
from rules_engine.events import _trigger_from_oracle


def canonical_source(seat):
    facts = json.loads((Path(__file__).parents[1]/'gate2-springheart/fixtures/canonical.json').read_bytes())
    state = g.position(facts, seat)
    cid = g.add(state, facts, 'Springheart Nantuko', seat, Zone.BATTLEFIELD)
    return state, state.cards[cid]


@pytest.mark.parametrize('tail', [' Draw a card.', ' if you gained life.', ' instead.', ' Extra.'])
def test_unknown_complete_clause_suffix_is_not_executable(tail):
    state, source = canonical_source(1)
    before = serialize_match_snapshot(state)
    key, payload = compile_instruction(source, source.oracle_text+tail)
    assert key == 'noop' and payload.get('__unsupported_trigger_instruction')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unrelated_self_entry_prefix_not_hijacked_by_attached_land_line(seat):
    state, source = canonical_source(seat)
    oracle = 'When this creature enters, draw a card.\n'+source.oracle_text
    before = serialize_match_snapshot(state)
    actual = _trigger_from_oracle(state, source.id, seat, oracle, 'synthetic self-entry fence',
                                 'enters_battlefield', {'card_id': source.id})
    assert actual['effect_key'] != KEY
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('entering', ['missing', 'nonland', 'opponent-land'])
def test_actual_event_condition_required_before_attached_body_admission(entering):
    state, source = canonical_source(1)
    cid = 'not-an-actual-card' if entering == 'missing' else source.id
    if entering == 'opponent-land':
        facts = json.loads((Path(__file__).parents[1]/'gate2-springheart/fixtures/canonical.json').read_bytes())
        cid = g.add(state, facts, 'Forest', 2, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    actual = _trigger_from_oracle(state, source.id, 1, source.oracle_text,
                                 'synthetic entry-condition fence', 'enters_battlefield', {'card_id': cid})
    assert actual['effect_key'] != KEY
    assert serialize_match_snapshot(state) == before
