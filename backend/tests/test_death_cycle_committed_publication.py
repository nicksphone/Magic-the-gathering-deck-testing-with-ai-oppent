"""Real paid costs publish committed entry receipts before discard/cycle aliases."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_death_cycle_ordering_audit as audit


def capture_action(state, seat, action, monkeypatch, records=None):
    import rules_engine.engine as engine
    import rules_engine.events as events
    import rules_engine.stack_engine as stack
    import rules_engine.zone_actions as zones
    records = [] if records is None else records
    single, batch = events.emit_event, events.emit_event_batch

    def observe(current, event, payloads, call):
        # Capture every publication, including empty batches and unrelated cards.
        records.append({'event': event, 'payloads': deepcopy(payloads),
                        'stack_at_event': [asdict(item) for item in current.stack],
                        'state_at_event': serialize_match_snapshot(current)})
        return call()

    with monkeypatch.context() as patch:
        patch.setattr(events, 'emit_event', lambda current, event, payload:
                      observe(current, event, [payload], lambda: single(current, event, payload)))
        patch.setattr(events, 'emit_event_batch', lambda current, event, payloads:
                      observe(current, event, payloads, lambda: batch(current, event, payloads)))
        patch.setattr(engine, 'emit_event', events.emit_event)
        patch.setattr(engine, 'emit_event_batch', events.emit_event_batch)
        patch.setattr(stack, 'emit_event', events.emit_event)
        patch.setattr(zones, 'emit_event_batch', events.emit_event_batch)
        with audit.cards.unchanged_root(state):
            result = checked_action(state, RulesEngine(), seat, action)
    return result, records


def assert_hand_entry(records, source, seat, expected, aliases):
    payload = {'card_id': source.id, 'owner': seat, 'from_zone': 'hand',
               'previous_controller': seat,
               'previous_reference': {'incarnation': 0, 'zone_change_sequence': 0},
               'entry_reference': {'incarnation': 0, 'zone_change_sequence': 1}}
    publications = ([('enters_graveyard', [payload])] if expected == Zone.GRAVEYARD else [])
    assert [(row['event'], row['payloads']) for row in records] == publications + aliases
    for row in records:
        snapshot = row['state_at_event']
        card = snapshot['cards'][source.id]
        player = snapshot['players'][str(seat)]
        assert card['zone'] == expected.value
        assert card['zone_change_sequence'] == 1
        assert card['last_known_battlefield'] == {}
        assert source.id not in player['hand']
        assert player[expected.value].count(source.id) == 1
        assert source.id not in player['exile' if expected == Zone.GRAVEYARD else 'graveyard']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', audit.MODES + ['dress'])
@pytest.mark.parametrize('name,find_land', [('Shark Typhoon', False),
                                         ('Krosan Tusker', True), ('Krosan Tusker', False)])
def test_paid_cycle_entry_receipt_and_complete_resolution(request, monkeypatch, seat, mode,
                                                        name, find_land):
    state, source, action = audit.cycle_position(seat, name, mode)
    state.mechanic_choice_players = {seat}
    before = serialize_match_snapshot(state)
    library = list(state.players[seat].library)
    expected = audit.destination(mode, seat, source.owner)
    paid, records = capture_action(state, seat, action, monkeypatch)
    assert_hand_entry(records, source, seat, expected, [
        ('discard', [{'card_id': source.id, 'controller': seat}]),
        ('cycle', [{'card_id': source.id, 'controller': seat,
                    'x_value': 2 if name == 'Shark Typhoon' else 0}])])
    queued = [asdict(item) for item in paid.stack]
    assert [(item['effect_key'], item['source_card_id'], item['controller']) for item in queued] == [
        ('cycle_draw', source.id, seat),
        ('create_shark_token' if name == 'Shark Typhoon' else 'search_library', source.id, seat)]
    assert paid.players[seat].hand == [] and paid.draws_this_turn[seat] == 0
    assert not audit.tokens(paid, seat)
    assert paid.players[seat].mana_pool == {
        'W': 0, 'U': 0 if name == 'Shark Typhoon' else 1, 'B': 0, 'R': 0,
        'G': 1 if name == 'Shark Typhoon' else 0, 'C': 0 if name == 'Shark Typhoon' else 1}
    paid = audit.restart(paid)
    completed = resolve_top_of_stack(paid)
    if name == 'Krosan Tusker':
        assert completed is False
        pending = paid.pending_mechanic_choice
        assert pending['kind'] == 'search_library' and pending['player_id'] == seat
        assert pending['options'] == library[:2]
        assert paid.players[seat].hand == [] and paid.draws_this_turn[seat] == 0
        paid = audit.restart(paid)
        paid = checked_action(paid, RulesEngine(), seat, {
            'type': 'choose_mechanic', 'card_ids': [library[1]] if find_land else []})
        assert paid.pending_mechanic_choice is None
        assert paid.players[seat].hand == ([library[1]] if find_land else [])
        assert paid.rng.getstate() != state.rng.getstate()
        assert not audit.tokens(paid, seat)
    else:
        assert completed is True
        shark, = audit.tokens(paid, seat)
        assert shark.name == 'Shark' and shark.power == shark.toughness == 2
        assert shark.owner == shark.controller == seat and shark.zone == Zone.BATTLEFIELD
        assert shark.keywords == ['flying']
        assert paid.players[seat].hand == []
    assert paid.draws_this_turn[seat] == 0
    assert [(item.effect_key, item.source_card_id) for item in paid.stack] == [('cycle_draw', source.id)]
    middle = serialize_match_snapshot(paid)
    paid = audit.restart(paid)
    assert resolve_top_of_stack(paid)
    assert not paid.stack and paid.pending_mechanic_choice is None
    assert paid.draws_this_turn[seat] == 1
    assert len(paid.players[seat].hand) == (2 if find_land else 1)
    assert set(paid.players[seat].hand + paid.players[seat].library) == set(library)
    if name == 'Shark Typhoon':
        assert paid.players[seat].hand == [library[-1]]
        assert len(audit.tokens(paid, seat)) == 1
    assert paid.cards[source.id].zone == expected
    assert paid.players[seat].life == paid.players[3-seat].life == 20
    assert serialize_match_snapshot(state) == before
    audit.receipt(request, {'setup': before, 'action': action, 'publications': records,
                            'queued': queued, 'before_cycle_draw': middle,
                            'resolved': serialize_match_snapshot(audit.restart(paid))})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', audit.MODES)
def test_paid_spell_discard_entry_precedes_alias_and_resolves_canonical_draw(request, monkeypatch,
                                                                          seat, mode):
    state = audit.cards.position(seat)
    spell = audit.add(state, 'Tormenting Voice', seat, Zone.HAND)
    source = audit.add(state, 'Island', seat, Zone.HAND)
    opposing = audit.add(state, 'Swamp', 3-seat, Zone.HAND)
    audit.replacement(state, seat, mode)
    library = [audit.add(state, name, seat, Zone.LIBRARY).id
               for name in ['Forest', 'Raging Goblin']]
    state.players[seat].mana_pool = {'C': 1, 'R': 1}
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'cost_choice': {'id': 'base', 'discard_card_ids': [source.id]}}
    before = serialize_match_snapshot(state)
    paid, records = capture_action(state, seat, action, monkeypatch)
    expected = audit.destination(mode, seat, source.owner)
    payload = {'card_id': source.id, 'owner': seat, 'from_zone': 'hand',
               'previous_controller': seat,
               'previous_reference': {'incarnation': 0, 'zone_change_sequence': 0},
               'entry_reference': {'incarnation': 0, 'zone_change_sequence': 1}}
    published = records[-1]['stack_at_event'][-1]
    assert [(row['event'], row['payloads']) for row in records] == (
        ([('enters_graveyard', [payload])] if expected == Zone.GRAVEYARD else []) + [
        ('discard', [{'card_id': source.id, 'controller': seat}]),
        ('spell_cast', [{'source_card_id': spell.id, 'source_stack_id': published['id'],
                         'controller': seat, 'label': 'Tormenting Voice',
                         'stack_payload': published['payload']}])])
    assert_hand_entry(records[:-1], source, seat, expected, [
        ('discard', [{'card_id': source.id, 'controller': seat}])])
    assert len(paid.stack) == 1 and paid.stack[0].source_card_id == spell.id
    assert paid.cards[spell.id].zone == Zone.STACK
    assert sum(paid.players[seat].mana_pool.values()) == 0
    queued = serialize_match_snapshot(audit.restart(paid))
    paid = audit.restart(paid)
    assert resolve_top_of_stack(paid)
    audit.receipt(request, {'setup': before, 'action': action, 'publications': records,
                            'queued': queued, 'resolved': serialize_match_snapshot(audit.restart(paid))})
    assert not paid.stack and paid.players[seat].hand == library[::-1]
    assert paid.players[3-seat].hand == [opposing.id]
    assert paid.cards[opposing.id].zone == Zone.HAND
    assert not paid.players[seat].library and paid.draws_this_turn[seat] == 2
    assert paid.cards[source.id].zone == paid.cards[spell.id].zone == expected
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['cycle', 'discard-cost'])
def test_unpayable_canonical_cost_has_no_publication_or_root_change(monkeypatch, seat, kind):
    if kind == 'cycle':
        state, source, action = audit.cycle_position(seat, 'Shark Typhoon')
        state.players[seat].mana_pool = {}
    else:
        state = audit.cards.position(seat)
        source = audit.add(state, 'Tormenting Voice', seat, Zone.HAND)
        held = audit.add(state, 'Island', seat, Zone.HAND)
        action = {'type': 'cast_spell', 'card_id': source.id,
                  'cost_choice': {'id': 'base', 'discard_card_ids': [held.id]}}
    records = []
    with audit.cards.unchanged_root(state), pytest.raises(ActionRejected):
        capture_action(state, seat, action, monkeypatch, records)
    assert records == []
