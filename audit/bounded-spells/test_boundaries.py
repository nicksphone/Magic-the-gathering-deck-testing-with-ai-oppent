"""Strict boundary actions; canonical bodies stay unchanged except negative probes."""
import pytest

import test_paid_preflight as original
from test_paid_preflight import facts
import domain_paid_support as paid
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['duplicate', 'over_limit', 'unknown_id'])
def test_bounded_selection_is_atomic(facts, seat, bad):
    state, source, targets, _, ids = original.setup(facts, seat, 'Force of Vigor')
    choices = {'duplicate': [ids[0], ids[0]],
               'over_limit': [ids[0], ids[1], paid.add(state, facts, "Witch's Oven", seat)],
               'unknown_id': ['unknown-object']}
    targets['target_card_ids'] = choices[bad]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        original.cast(state, seat, source, targets)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_response_invalidates_one_bounded_target(facts, seat):
    state, source, targets, _, ids = original.setup(facts, seat, 'Force of Vigor')
    state = original.cast(state, seat, source, targets)
    response = paid.add(state, facts, 'March of Otherworldly Light', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'C': 1, 'W': 1}
    state = paid.respond(state, 3-seat)
    state = original.cast(state, 3-seat, response, {'x_value': 1, 'target_card_id': ids[0]})
    assert len(state.stack) == 2 and sum(state.players[3-seat].mana_pool.values()) == 0
    state = paid.restore(state)
    state = paid.resolve(state)
    assert state.cards[ids[0]].zone == Zone.EXILE and len(state.stack) == 1
    before = serialize_match_snapshot(state)
    state = paid.restore(state)
    state = paid.resolve(state)
    assert state.cards[ids[0]].zone == Zone.EXILE
    assert state.cards[ids[1]].zone == Zone.GRAVEYARD
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[response].zone == Zone.GRAVEYARD and not state.stack
    original.record('paid-response-partial-resolution', facts, 'Force of Vigor', seat, before, state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Force of Vigor', 'March of the Multitudes',
                                'Secure the Wastes', 'Searing Blaze'])
def test_unknown_parenthetical_is_not_a_reminder(facts, seat, name):
    state, source, targets, _, _ = original.setup(facts, seat, name)
    state.cards[source].oracle_text += ' (Unknown audit instruction.)'
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        original.cast(state, seat, source, targets)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_resource_reminder_is_rejected(facts, seat):
    state, source, targets, _, _ = original.setup(facts, seat, 'March of the Multitudes')
    body = state.cards[source].oracle_text
    state.cards[source].oracle_text = 'Convoke (Unknown audit instruction.)\n' + body.splitlines()[1]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        original.cast(state, seat, source, targets)
    assert serialize_match_snapshot(state) == before


def test_publish_all_boundary_receipts():
    import json
    (original.OUT/'boundary-paid-receipts.json').write_text(json.dumps(original.ROWS, indent=2, sort_keys=True)+'\n')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('prefix', [' ', '\t', '\n  '])
def test_whitespace_cannot_hide_unknown_x_token_body(facts, seat, prefix):
    state, source, targets, _, _ = original.setup(facts, seat, 'Secure the Wastes')
    state.cards[source].oracle_text = prefix + state.cards[source].oracle_text + ' (Unknown audit instruction.)'
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        original.cast(state, seat, source, targets)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('phrase', ['damage to target', 'target creature that'])
def test_embedded_unknown_parenthetical_cannot_hide_linked_body(facts, seat, phrase):
    state, source, targets, _, _ = original.setup(facts, seat, 'Searing Blaze')
    first, rest = phrase.split(' ', 1)
    state.cards[source].oracle_text = state.cards[source].oracle_text.replace(
        phrase, first + ' (Unknown audit instruction.) ' + rest, 1)
    assert '(Unknown audit instruction.)' in state.cards[source].oracle_text
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        original.cast(state, seat, source, targets)
    assert serialize_match_snapshot(state) == before
