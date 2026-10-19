"""Explicit public metadata boundary; no private-zone or absent-move certificate."""
import pickle

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.state import CardInstance, MatchState, Zone
from rules_engine import graveyard_inventory as inventory
from rules_engine.action_validation import checked_action
from tests.test_empty_hand_attack_witness import ROWS, position
from tests.test_linked_damage_targets import raw_card
from tests.test_public_combat_boundary_audit import response_window


def public_position(seat):
    root, source = position(seat, 'Sheoldred, the Apocalypse', counter=True)
    grave = raw_card(root, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    before = pickle.dumps(root)
    announced, _, _ = response_window(root, seat, source)
    public, _ = decision_view(announced, seat, [])
    assert pickle.dumps(root) == before
    return root, before, public, grave.id


def unchanged_query(state, seat):
    before = pickle.dumps(state)
    value = inventory.public_graveyard_inventory(state, seat)
    assert pickle.dumps(state) == before
    return value


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [None, 0])
def test_reviewed_defaults_are_inert_without_private_mutation(seat, count):
    root, before, public, cid = public_position(seat)
    assert public.spell_color_history == {1: set(), 2: set()}
    assert public.spell_color_history_known is True
    assert not public.turn_spell_protection and not public.turn_player_hexproof
    assert not public.retained_counter_prohibitions
    assert public.cards[cid].was_kicked is False
    public.cards[cid].kicker_count = count
    assert unchanged_query(public, seat)['status'] == 'inert'
    assert pickle.dumps(root) == before


CONTEXT_CASES = [
    ('history-active', 'spell_color_history', {1: {'W'}, 2: set()}),
    ('history-missing-seat', 'spell_color_history', {1: set()}),
    ('history-extra-seat', 'spell_color_history', {1: set(), 2: set(), 3: set()}),
    ('history-string-seat', 'spell_color_history', {'1': set(), 2: set()}),
    ('history-bool-seat', 'spell_color_history', {True: set(), 2: set()}),
    ('history-list-value', 'spell_color_history', {1: [], 2: set()}),
    ('history-invalid-color', 'spell_color_history', {1: {7}, 2: set()}),
    ('history-wrong-container', 'spell_color_history', []),
    ('history-unknown', 'spell_color_history_known', False),
    ('history-known-int', 'spell_color_history_known', 1),
    ('history-known-none', 'spell_color_history_known', None),
    ('protection-active', 'turn_spell_protection', {1}),
    ('protection-bool', 'turn_spell_protection', {True}),
    ('protection-list', 'turn_spell_protection', []),
    ('hexproof-active', 'turn_player_hexproof', {1: {'W'}}),
    ('hexproof-malformed-nested', 'turn_player_hexproof', {1: 'W'}),
    ('hexproof-list', 'turn_player_hexproof', []),
    ('counter-prohibition-active', 'retained_counter_prohibitions', [{'player': 1}]),
    ('counter-prohibition-dict', 'retained_counter_prohibitions', {}),
    ('counter-prohibition-none', 'retained_counter_prohibitions', None),
    ('history-none', 'spell_color_history', None),
]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('label,field,value', CONTEXT_CASES, ids=[x[0] for x in CONTEXT_CASES])
def test_active_unknown_and_malformed_contexts_are_unknown(seat, label, field, value):
    root, before, public, _ = public_position(seat)
    setattr(public, field, value)
    assert unchanged_query(public, seat)['status'] == 'unknown'
    assert pickle.dumps(root) == before


KICKER_CASES = [
    (False, False), (True, False), (-1, False), (1, False), (2, False),
    (3, False), (0.0, False), ('0', False), ([], False), ({}, False),
    (None, True), (0, True), (1, True), (None, 0), (0, 1),
]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count,kicked', KICKER_CASES)
def test_active_malformed_or_contradictory_kicker_metadata_is_unknown(seat, count, kicked):
    root, before, public, cid = public_position(seat)
    public.cards[cid].kicker_count = count
    public.cards[cid].was_kicked = kicked
    assert unchanged_query(public, seat)['status'] == 'unknown'
    assert pickle.dumps(root) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['spell_color_history', 'spell_color_history_known',
    'turn_spell_protection', 'turn_player_hexproof', 'retained_counter_prohibitions', 'kicker_count'])
def test_missing_reviewed_field_is_not_legacy_inert_certificate(seat, field):
    _, _, public, cid = public_position(seat)
    delattr(public.cards[cid] if field == 'kicker_count' else public, field)
    assert unchanged_query(public, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('schema', [MatchState, CardInstance])
def test_future_schema_pin_mismatch_fails_closed(seat, schema, monkeypatch):
    _, _, public, _ = public_position(seat)
    monkeypatch.setitem(inventory._SCHEMA_PINS, schema, '0'*64)
    assert unchanged_query(public, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source', ['state', 'card'])
def test_unreviewed_extra_attribute_fails_closed(seat, source):
    _, _, public, cid = public_position(seat)
    setattr(public if source == 'state' else public.cards[cid], 'future_permission', True)
    assert unchanged_query(public, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suffix', [' Then gain 99 life.', '\nUnreviewed instruction.'])
def test_complete_unknown_tail_still_has_no_inert_certificate(seat, suffix):
    _, _, public, cid = public_position(seat)
    public.cards[cid].oracle_text += suffix
    assert unchanged_query(public, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('affordable', [False, True])
def test_printed_flashback_remains_interactive_with_real_paid_control(seat, affordable):
    root, source = position(seat, 'Sheoldred, the Apocalypse')
    grave = raw_card(root, ROWS['Memory Deluge'], 3-seat, Zone.GRAVEYARD)
    for _ in range(2):
        raw_card(root, ROWS['Island'], 3-seat, Zone.BATTLEFIELD)
    if not affordable:
        for cid in root.players[3-seat].battlefield:
            root.cards[cid].tapped = True
    before = pickle.dumps(root)
    announced, reply, legal = response_window(root, seat, source)
    public, _ = decision_view(announced, seat, [])
    assert unchanged_query(public, seat)['status'] == 'interactive'
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is None
    casts = [move for move in legal if move['type'] == 'cast_spell' and move['card_id'] == grave.id]
    if affordable:
        agent = AIAgent()
        paid = checked_action(reply, agent.engine, 3-seat,
                              agent._materialize_action(reply, casts[0], 3-seat))
        assert paid.cards[grave.id].zone == Zone.STACK and paid.stack
        assert sum(paid.cards[cid].tapped for cid in paid.players[3-seat].battlefield) == 7
    else:
        assert not casts
    assert pickle.dumps(root) == before
