"""Real paid canonical Millstone episodes; no event injection."""
from copy import deepcopy
import json

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone, object_incarnation
from rules_engine.engine import RulesEngine
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.test_direct_graveyard_bypass_audit import client, install, main_controller_snapshot, public_private_restore
from tests.test_library_reorder import setup
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import ROWS as BASE, act, restart, snap
from tests.test_self_graveyard_replacement_interactions import ROWS
from tests.test_simultaneous_graveyard_entry_audit import KOZILEK, passes
from tests.test_spell_admission_safety_http import sql_facts
from tests.readiness_rules_seam_support import normalize


@pytest.fixture
def entry_collections(monkeypatch, tmp_path):
    from rules_engine import events
    original = events._collect_triggers
    observed = []

    def collect(state, event, payload):
        if event in {'enters_graveyard', 'permanent_dies', 'creature_dies', 'sacrifice', 'mill'}:
            observed.append({'event': event, 'payload': deepcopy(payload),
                             'zones': {cid: card.zone.value for cid, card in state.cards.items()},
                             'sequences': {cid: card.zone_change_sequence for cid, card in state.cards.items()}})
        return original(state, event, payload)

    monkeypatch.setattr(events, '_collect_triggers', collect)
    yield observed
    (tmp_path / 'actual-batch-collections.json').write_text(json.dumps(observed, indent=2))


def mill_position(seat, opponent=False, replacement='ordinary'):
    state, _ = setup('Index', seat)
    target = 3-seat if opponent else seat
    # Trusted initial library ordering, not an executed top-deck spell claim.
    second_name = 'Darksteel Colossus' if replacement == 'library' else 'Blood Artist'
    second = raw_card(state, BASE[second_name], target, Zone.LIBRARY)
    first = raw_card(state, BASE[KOZILEK], target, Zone.LIBRARY)
    source = raw_card(state, BASE['Millstone'], seat, Zone.BATTLEFIELD)
    if replacement == 'exile':
        raw_card(state, ROWS['Rest in Peace'], 3-target, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 2}
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
              'targets': {'target_player': target}}
    assert state.players[target].library[-2:] == [second.id, first.id]
    return state, source.id, [first.id, second.id], target, action


def resolve_paid_mill(seat, opponent=False, replacement='ordinary'):
    state, source, ids, target, action = mill_position(seat, opponent, replacement)
    state = act(state, seat, action)
    assert state.cards[source].tapped and not sum(state.players[seat].mana_pool.values())
    assert state.stack[-1].source_card_id == source and state.stack[-1].effect_key == 'mill_cards'
    state = passes(state)
    return state, source, ids, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opponent', [False, True])
def test_paid_mill_entry_collection_requires_complete_two_card_batch(seat, opponent, entry_collections):
    state, source, ids, target = resolve_paid_mill(seat, opponent)
    entries = [row for row in entry_collections if row['event'] == 'enters_graveyard' and row['payload']['card_id'] in ids]
    assert entries and {row['payload']['card_id'] for row in entries} == set(ids)
    assert all(all(row['zones'][cid] == 'graveyard' for cid in ids) for row in entries), \
        'Paid mill must commit both selected library departures before entry collection'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opponent', [False, True])
@pytest.mark.parametrize('replacement', ['ordinary', 'library', 'exile'])
def test_independent_actual_paid_mill_destinations_owner_refs_private_restart(seat, opponent, replacement, entry_collections, tmp_path):
    before, _, ids, target, _ = mill_position(seat, opponent, replacement)
    refs = {cid: {'incarnation': object_incarnation(before.cards[cid]),
                  'zone_change_sequence': before.cards[cid].zone_change_sequence} for cid in ids}
    state, source, actual_ids, actual_target = resolve_paid_mill(seat, opponent, replacement)
    assert actual_ids == ids and actual_target == target
    expected = [Zone.GRAVEYARD, Zone.LIBRARY] if replacement == 'library' else [Zone.EXILE] * 2 if replacement == 'exile' else [Zone.GRAVEYARD] * 2
    for cid, zone in zip(ids, expected):
        assert state.cards[cid].zone == zone and state.cards[cid].owner == target
        assert getattr(state.players[target], zone.value).count(cid) == 1
        if zone != Zone.LIBRARY:
            assert state.cards[cid].zone_change_sequence == refs[cid]['zone_change_sequence'] + 1
    entries = [row for row in entry_collections if row['event'] == 'enters_graveyard' and row['payload']['card_id'] in ids]
    assert {row['payload']['card_id'] for row in entries} == {cid for cid, zone in zip(ids, expected) if zone == Zone.GRAVEYARD}
    for row in entries:
        payload = row['payload']; cid = payload['card_id']
        assert payload['owner'] == target and payload['from_zone'] == 'library'
        assert payload['previous_reference'] == refs[cid]
        assert payload['entry_reference'] == {**refs[cid], 'zone_change_sequence': refs[cid]['zone_change_sequence'] + 1}
    if replacement != 'exile':
        assert any(item.source_card_id == ids[0] and item.controller == target for item in state.stack)
    view, _ = decision_view(state, 3-target, RulesEngine().legal_moves(state, 3-target))
    assert all(is_unknown(view.cards[cid]) for cid in state.players[target].library)
    restart(state, tmp_path, 'paid-two-card-mill')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opponent', [False, True])
def test_http_paid_mill_valid_controls_atomic_invalid_target_sql_restore(repo, client, seat, opponent, entry_collections, tmp_path):
    for row in [*BASE.values(), *ROWS.values()]:
        repo.upsert_card(normalize(row))
    state, source, ids, target, action = mill_position(seat, opponent)
    controller = install(repo, client, state)
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    invalid = deepcopy(action); invalid['targets']['target_player'] = 99
    response = client.post('/matches/' + controller.state.id + '/action', json={'player_id': seat, 'action': invalid})
    assert response.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    assert not entry_collections
    response = client.post('/matches/' + controller.state.id + '/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert controller.state.cards[source].tapped and not sum(controller.state.players[seat].mana_pool.values())
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    for _ in range(2):
        response = client.post('/matches/' + controller.state.id + '/action',
                               json={'player_id': controller.state.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    assert all(controller.state.cards[cid].zone == Zone.GRAVEYARD for cid in ids)
    assert any(item.source_card_id == ids[0] and item.controller == target for item in controller.state.stack)
    public_private_restore(repo, client, controller, seat, tmp_path)
