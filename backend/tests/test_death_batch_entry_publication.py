"""Narrow caller boundary controls; controlled seams, not natural gameplay claims."""
from copy import deepcopy

import pytest

from effects import handlers
from game_state.state import Zone, object_incarnation
from rules_engine import events, state_based_actions as sba
from rules_engine.action_validation import ActionRejected
from tests.test_batch_graveyard_publication_audit import assert_private
from tests.test_direct_graveyard_bypass_audit import ROWS
from tests.test_library_reorder import setup
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import restart, snap
from tests.test_self_graveyard_replacement_interactions import ROWS as INTERACTIONS


@pytest.fixture
def publication(monkeypatch):
    recorded = []
    one, batch = events.emit_event, events.emit_event_batch

    def single(state, event, payload):
        recorded.append((state, event, 'single', [deepcopy(payload)]))
        return one(state, event, payload)

    def many(state, event, payloads):
        payloads = list(payloads)
        recorded.append((state, event, 'batch', deepcopy(payloads)))
        if event == 'enters_graveyard':
            for cid, expected in state._audit_cohort.items():
                card = state.cards[cid]
                assert card.zone == expected
                assert getattr(state.players[card.owner], expected.value).count(cid) == 1
        return batch(state, event, payloads)

    for module in (events, handlers, sba):
        monkeypatch.setattr(module, 'emit_event', single)
        monkeypatch.setattr(module, 'emit_event_batch', many)
    return recorded


def invoke(state, family, ids):
    if family == 'sba':
        sba._resolve_lethal_creature_batch(state, ids)
    else:
        handlers._destroy_all_permanents_of_types(state, {'Creature'}, 'All creatures are destroyed.')


def controlled(seat, family, case):
    state, _ = setup('Index', seat)
    ids, expected, refs = [], {}, {}
    if case != 'zero':
        traveler = raw_card(state, ROWS['Doomed Traveler'], seat, Zone.BATTLEFIELD)
        # Retained foreign ownership position, not a claimed control spell episode.
        traveler.owner = 3-seat
        traveler.damage_marked = 1
        ids.append(traveler.id)
        expected[traveler.id] = Zone.EXILE if case == 'exile' else Zone.GRAVEYARD
    if case in {'mixed', 'competing'}:
        name = 'Darksteel Colossus' if family == 'sba' else 'Progenitus'
        card = raw_card(state, ROWS[name], 3-seat, Zone.BATTLEFIELD)
        if family == 'sba':
            # Controlled zero-toughness seam: indestructibility does not prevent it.
            card.counters['-1/-1'] = 12
        ids.append(card.id)
        expected[card.id] = Zone.LIBRARY
    if case in {'exile', 'competing'}:
        raw_card(state, INTERACTIONS['Rest in Peace'], seat, Zone.BATTLEFIELD)
    for cid in ids:
        card = state.cards[cid]
        refs[cid] = {'incarnation': object_incarnation(card),
                     'zone_change_sequence': card.zone_change_sequence}
    state._audit_cohort = expected
    return state, ids, expected, refs


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['sba', 'wrath'])
@pytest.mark.parametrize('case', ['zero', 'one', 'mixed', 'exile', 'competing'])
def test_buffered_entry_boundary_real_canonical_plans(seat, family, case, publication, tmp_path):
    state, ids, expected, refs = controlled(seat, family, case)
    # Hydration creates independent sample matches; observe only the tested commit.
    publication.clear()
    repeated = deepcopy(state)
    before = snap(state)
    if case == 'competing':
        for root in (state, repeated):
            with pytest.raises(ActionRejected):
                invoke(root, family, ids)
            assert snap(root) == before
        assert publication == []
        return
    for root in (state, repeated):
        invoke(root, family, ids)
        rows = [row for row in publication if row[0] is root]
        entry = [row for row in rows if row[1] == 'enters_graveyard']
        graves = {cid for cid, zone in expected.items() if zone == Zone.GRAVEYARD}
        assert len(entry) == bool(graves)
        if graves:
            assert entry[0][2] == 'batch'
            assert {p['card_id'] for p in entry[0][3]} == graves
            entry_index = rows.index(entry[0])
            assert all(index > entry_index for index, row in enumerate(rows)
                       if row[1] in {'permanent_dies', 'creature_dies'} and row[3])
            assert all(index < entry_index for index, row in enumerate(rows)
                       if row[1] == 'leaves_battlefield')
            for payload in entry[0][3]:
                cid = payload['card_id']
                assert payload['owner'] == root.cards[cid].owner == 3-seat
                assert payload['previous_controller'] == seat
                assert payload['from_zone'] == 'battlefield'
                assert payload['previous_reference'] == refs[cid]
                assert payload['entry_reference'] == {
                    'incarnation': object_incarnation(root.cards[cid]),
                    'zone_change_sequence': refs[cid]['zone_change_sequence'] + 1}
        for event in ('permanent_dies', 'creature_dies'):
            actual = [p['card_id'] for row in rows if row[1] == event for p in row[3]]
            assert set(actual) == graves and len(actual) == len(graves)
        for cid, zone in expected.items():
            assert root.cards[cid].zone == zone
            assert root.cards[cid].zone_change_sequence == refs[cid]['zone_change_sequence'] + 1
            assert getattr(root.players[root.cards[cid].owner], zone.value).count(cid) == 1
        assert_private(root)
    assert snap(state) == snap(repeated)
    restart(state, tmp_path, 'buffered-' + family + '-' + case)
