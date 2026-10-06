"""Actual canonical selected costs; static shuffle protocol remains separate."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.costs import apply_activated_costs
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import SELF, ROWS as BASE, act, position, restart, snap
from tests.test_self_graveyard_replacement_interactions import ROWS

FIXTURE = Path(__file__).parent / 'fixtures/self_graveyard_cost/canonical.jsonl'
PROVENANCE = json.loads(FIXTURE.with_name('provenance.json').read_text())
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['fixture_sha256']
COST_ROWS = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}


def tower_position(seat, name, foreign=False):
    state, card, _, observer, _ = position(name, seat, 'sacrifice', foreign)
    tower = raw_card(state, ROWS['Phyrexian Tower'], seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {}
    action = {'type': 'activate_mana_ability', 'card_id': tower.id,
              'ability_index': 1, 'color': 'B',
              'payment_choices': {'sacrifice_card_ids': [card.id]}}
    return state, card, tower, observer, action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('foreign', [False, True])
def test_actual_selected_tower_owner_library_and_no_false_dies(seat, name, foreign, tmp_path):
    state, card, tower, observer, action = tower_position(seat, name, foreign)
    before = snap(state)
    owner = card.owner
    result = restart(act(state, seat, action), tmp_path, 'tower-routed')
    assert snap(state) == before
    assert result.players[seat].mana_pool.get('B') == 2
    assert result.cards[tower.id].tapped
    assert result.cards[card.id].zone == Zone.LIBRARY
    assert result.players[owner].library.count(card.id) == 1
    assert all(card.id not in p.battlefield and card.id not in p.graveyard for p in result.players.values())
    assert not any(item.source_card_id in {tower.id, card.id, observer.id} for item in result.stack)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_actual_tower_humility_removes_only_battlefield_self_replacement(seat, name):
    state, card, _, _, action = tower_position(seat, name)
    raw_card(state, ROWS['Humility'], 3-seat, Zone.BATTLEFIELD)
    result = act(state, seat, action)
    assert result.cards[card.id].zone == Zone.GRAVEYARD
    assert result.players[seat].mana_pool.get('B') == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('rival_name', ['Rest in Peace', 'Leyline of the Void'])
def test_tower_unresolved_replacement_rejects_before_raw_core_cost_mutation(seat, name, rival_name):
    state, card, tower, _, _ = tower_position(seat, name)
    raw_card(state, ROWS[rival_name], 3-seat, Zone.BATTLEFIELD)
    before = snap(state)
    text = tower.oracle_text.splitlines()[1].split(':', 1)[0]
    with pytest.raises(ActionRejected, match='competing graveyard replacement source'):
        apply_activated_costs(state, seat, tower.id, text, ability_kind='mana', ability_index=1,
                              payment_choices={'sacrifice_card_ids': [card.id]})
    assert snap(state) == before


def generic_position(seat, name, source_name, mode):
    state, card, old_source, _, _ = position(name, seat, 'sacrifice' if mode == 'sacrifice' else 'discard')
    source = raw_card(state, COST_ROWS[source_name], seat, Zone.BATTLEFIELD)
    line = source.oracle_text.splitlines()[0 if mode == 'discard' else 2] if source_name == 'Trading Post' else source.oracle_text
    text = line.split(':', 1)[0]
    payment = {}
    if 'Sacrifice' in text:
        victim = card if mode == 'sacrifice' else raw_card(state, BASE['Doomed Traveler'], seat, Zone.BATTLEFIELD)
        payment['sacrifice_card_ids'] = [victim.id]
    if 'Discard' in text:
        payment['discard_card_ids'] = [card.id if mode == 'discard' else old_source.id]
    # Actual Island from the inherited canonical setup, available for mana.
    island_id = next(cid for cid in state.players[seat].library if state.cards[cid].name == 'Island')
    state.players[seat].library.remove(island_id)
    state.cards[island_id].move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(island_id)
    state.players[seat].mana_pool = {}
    return state, card, source, text, payment, island_id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('source_name', ['Trading Post', 'Bloodsoaked Altar'])
@pytest.mark.parametrize('mode', ['sacrifice', 'discard'])
def test_canonical_generic_cost_preflight_precedes_mana_tap_life_discard(seat, name, source_name, mode):
    state, _, source, text, payment, _ = generic_position(seat, name, source_name, mode)
    raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    before = snap(state)
    with pytest.raises(ActionRejected, match='competing graveyard replacement source'):
        apply_activated_costs(state, seat, source.id, text, payment_choices=payment)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('source_name', ['Trading Post', 'Bloodsoaked Altar'])
@pytest.mark.parametrize('mode', ['sacrifice', 'discard'])
def test_canonical_generic_cost_exact_resources_and_owner_library(seat, name, source_name, mode, tmp_path):
    state, card, source, text, payment, island_id = generic_position(seat, name, source_name, mode)
    life = state.players[seat].life
    assert apply_activated_costs(state, seat, source.id, text, payment_choices=payment)
    state = restart(state, tmp_path, 'generic-paid')
    assert state.cards[card.id].zone == Zone.LIBRARY
    assert state.players[seat].library.count(card.id) == 1
    assert state.cards[source.id].tapped
    assert state.cards[island_id].tapped == (source_name == 'Trading Post')
    assert state.players[seat].life == life - (2 if source_name == 'Bloodsoaked Altar' else 0)
    for cid in payment.get('discard_card_ids', []):
        assert cid not in state.players[seat].hand
    for cid in payment.get('sacrifice_card_ids', []):
        assert cid not in state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('foreign', [False, True])
def test_actual_http_competing_tower_preserves_full_root_controller_sql(repo, client, seat, name, foreign):
    import main
    for row in [*BASE.values(), *ROWS.values()]:
        repo.upsert_card(normalize(row))
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                           'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7221})
    assert response.status_code == 200
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state, _, _, _, action = tower_position(seat, name, foreign)
    raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 422, response.text
    assert 'competing graveyard replacement source' in response.json()['detail']['message']
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
