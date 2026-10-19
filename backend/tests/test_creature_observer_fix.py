"""Actual copy/source-departure controls for the narrow observer admission fix."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.engine import RulesEngine
from tests.test_creature_observer_audit import (
    ROWS, FAMILIES, position, observer_items, trigger_boundary, optional, trace,
    act, passes, raw_card, repo, base_client, client, install, submit, responses,
    public_private_restore, main_controller_snapshot, normalize, sql_facts, snap,
)

FIXTURE = Path(__file__).parent / 'fixtures/creature_observer_fix'
EXTRA = {}
for entry in json.loads((FIXTURE / 'provenance.json').read_text())['cards']:
    data = (FIXTURE / entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    row = json.loads(data)
    assert row['oracle_id'] == entry['oracle_id'] and row['object'] == 'card'
    EXTRA[row['name']] = row


@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('seat', [1, 2])
def test_noncreature_artifact_paid_entry_does_not_match(name, seat):
    state, oid, unused, _ = position(name, seat)
    state.players[seat].hand.remove(unused)
    state.cards[unused].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(unused)
    artifact = raw_card(state, EXTRA['Sol Ring'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': artifact.id, 'targets': {}})
    assert not observer_items(state, oid)
    state = passes(state)
    assert state.cards[artifact.id].zone == Zone.BATTLEFIELD
    assert not observer_items(state, oid)


@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('seat', [1, 2])
def test_effective_ability_suppression_real_paid_stimulus(name, seat):
    state, oid, cid, action = position(name, seat)
    # Retained canonical continuous source; the Bears cast/entry is actual.
    raw_card(state, EXTRA['Humility'], 3-seat, Zone.BATTLEFIELD)
    state = act(state, seat, action)
    assert not observer_items(state, oid)
    state = passes(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert not observer_items(state, oid)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_permanent_spell_copy_not_another_creature_cast(seat, tmp_path, trace):
    state, oid, cid, action = position('Primordial Sage', seat)
    state = trigger_boundary(state, seat, 'Primordial Sage', action)
    state = optional(state, seat, oid, False, tmp_path)
    assert state.stack[-1].source_card_id == cid and not observer_items(state, oid)
    engine = raw_card(state, EXTRA['Lithoform Engine'], seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 4}
    target = state.stack[-1].id
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine.id, 'ability_index': 2,
                              'targets': {'target_stack_id': target}})
    assert state.cards[engine.id].tapped and sum(state.players[seat].mana_pool.values()) == 0
    state = passes(state)
    assert len(state.stack) == 2 and all(s.source_card_id == cid for s in state.stack)
    assert any(row['kind'] == 'event' and row['event'] == 'spell_copy' for row in trace)
    assert not observer_items(state, oid), 'Copying a creature spell is not casting it'


@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_http_foreign_owned_source_bounce_lki_optional_restore(repo, client, name, seat, accept, tmp_path):
    for row in list(ROWS.values()) + list(EXTRA.values()): repo.upsert_card(normalize(row))
    state, oid, cid, action = position(name, seat)
    # Retained foreign ownership, not a claimed control-changing spell.
    state.cards[oid].owner = 3-seat
    old_ref = object_incarnation(state.cards[oid]), state.cards[oid].zone_change_sequence
    controller = install(repo, client, state)
    submit(client, controller, seat, action)
    if name == 'Soul of the Harvest': responses(client, controller)
    assert len(observer_items(controller.state, oid)) == 1
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    actor = controller.state.priority_player
    bounce = raw_card(controller.state, ROWS['Unsummon'], actor, Zone.HAND)
    controller.state.players[actor].mana_pool = {'U': 1}
    # Test setup is explicit; persist only through actual HTTP action below.
    submit(client, controller, actor, {'type': 'cast_spell', 'card_id': bounce.id,
                                       'targets': {'target_card_id': oid}})
    responses(client, controller)
    assert controller.state.cards[oid].zone == Zone.HAND
    assert oid in controller.state.players[3-seat].hand
    assert controller.state.cards[oid].zone_change_sequence == old_ref[1] + 1
    item = observer_items(controller.state, oid)[0]
    assert item.controller == seat and item.source_card_id == oid
    assert item.payload['__source_lki']['controller'] == seat
    assert item.payload['__source_lki']['battlefield_incarnation'] == old_ref[0]
    assert item.payload['__source_lki']['oracle_text'] == ROWS[name]['oracle_text']
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    responses(client, controller)
    choices = [m for m in RulesEngine().legal_moves(controller.state, seat) if m['type'] == 'choose_optional_effect']
    assert len(choices) == 2 and {m['accept'] for m in choices} == {False, True}
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    chosen = {'type': 'choose_optional_effect', 'stack_id': choices[0]['stack_id'], 'accept': accept}
    for actor, invalid in [(3-seat, chosen), (seat, {**chosen, 'stack_id': 'stale-stack-id'})]:
        before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
        response = client.post('/matches/' + controller.state.id + '/action', json={'player_id': actor, 'action': invalid})
        assert response.status_code == 422, response.text
        assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    before_hand = list(controller.state.players[seat].hand)
    submit(client, controller, seat, chosen)
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    assert len(controller.state.players[seat].hand) == len(before_hand) + int(accept)
    assert not observer_items(controller.state, oid)
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    duplicate = client.post('/matches/' + controller.state.id + '/action', json={'player_id': seat, 'action': chosen})
    assert duplicate.status_code == 422, duplicate.text
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
