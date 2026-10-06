"""Independent canonical replacement-choice and suppression goldens."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import SELF, act, execute, position, restart, snap
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts

FIXTURE = Path(__file__).parent / 'fixtures/self_graveyard_interactions/canonical.jsonl'
PROVENANCE = json.loads(FIXTURE.with_name('provenance.json').read_text())
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['fixture_sha256']
ROWS = {r['name']: r for r in map(json.loads, FIXTURE.read_text().splitlines())}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('stimulus', ['sacrifice', 'discard', 'mill'])
def test_actual_humility_suppresses_only_battlefield_replacement(seat, name, stimulus, tmp_path):
    state, card, source, _, action = position(name, seat, stimulus)
    raw_card(state, ROWS['Humility'], 3-seat, Zone.BATTLEFIELD)
    state = execute(state, source, seat, stimulus, action)
    state = restart(state, tmp_path, 'humility-after')
    expected = Zone.GRAVEYARD if stimulus == 'sacrifice' else Zone.LIBRARY
    assert state.cards[card.id].zone == expected
    assert not any(item.source_card_id == card.id for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('stimulus', ['sacrifice', 'discard'])
def test_competing_replacements_are_pure_choices_not_self_priority(seat, name, stimulus):
    from rules_engine.replacement import graveyard_entry_plans, select_graveyard_entry_plan
    state, card, _, _, _ = position(name, seat, stimulus)
    rival = raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    before = snap(state)
    for _ in range(3):
        plans = graveyard_entry_plans(state, card.id)
        assert {p.destination for p in plans} == {Zone.EXILE, Zone.LIBRARY}
        assert {p.replacement_source_id for p in plans} == {card.id, rival.id}
        assert select_graveyard_entry_plan(state, card.id, card.id).destination == Zone.LIBRARY
        assert select_graveyard_entry_plan(state, card.id, rival.id).destination == Zone.EXILE
        with pytest.raises(ActionRejected):
            select_graveyard_entry_plan(state, card.id)
        with pytest.raises(ActionRejected):
            select_graveyard_entry_plan(state, card.id, 'unavailable-source')
        assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('chosen', ['printed', 'rival'])
def test_explicit_trusted_replacement_choices_execute_exact_destination(seat, name, chosen, tmp_path):
    from rules_engine.zone_actions import sacrifice_selected
    state, card, _, observer, _ = position(name, seat, 'sacrifice')
    rival = raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    expected = Zone.LIBRARY if chosen == 'printed' else Zone.EXILE
    selected = card.id if chosen == 'printed' else rival.id
    # Trusted executor choice, NOT a newly invented public cost parameter.
    assert sacrifice_selected(state, seat, [card.id], replacement_choices={card.id: selected})
    state = restart(state, tmp_path, 'chosen-replacement')
    assert state.cards[card.id].zone == expected
    assert card.id in getattr(state.players[seat], expected.value)
    assert not any(item.source_card_id == observer.id for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_unannounced_competing_cost_choice_rejects_full_root(seat, name):
    state, _, _, _, action = position(name, seat, 'sacrifice')
    raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, action)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_milled_same_library_shuffle_does_not_fabricate_zone_incarnation(seat, name, tmp_path):
    state, card, source, _, action = position(name, seat, 'mill')
    sequence = card.zone_change_sequence
    state = execute(state, source, seat, 'mill', action)
    state = restart(state, tmp_path, 'same-library')
    assert state.cards[card.id].zone == Zone.LIBRARY
    assert state.cards[card.id].zone_change_sequence == sequence
    assert state.players[seat].library.count(card.id) == 1
    assert not any(card.id in p.graveyard for p in state.players.values())
    assert any('reveal' in line.lower() and name in line for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('change', ['zone', 'owner', 'suppression'])
def test_stale_structured_plan_rejects_before_any_mutation(seat, name, change):
    from rules_engine.replacement import select_graveyard_entry_plan
    from rules_engine.zone_actions import execute_graveyard_entry
    state, card, _, _, _ = position(name, seat, 'sacrifice')
    plan = select_graveyard_entry_plan(state, card.id)
    if change == 'zone':
        state.players[seat].battlefield.remove(card.id)
        card.move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(card.id)
    elif change == 'owner':
        card.owner = 3-seat
    else:
        raw_card(state, ROWS['Humility'], 3-seat, Zone.BATTLEFIELD)
    before = snap(state)
    with pytest.raises(ActionRejected):
        execute_graveyard_entry(state, plan)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_leyline_follows_owner_not_controller_in_retained_foreign_board(seat, name):
    from rules_engine.replacement import graveyard_entry_plans
    state, card, _, _, _ = position(name, seat, 'sacrifice', True)
    rival = raw_card(state, ROWS['Leyline of the Void'], seat, Zone.BATTLEFIELD)
    assert card.controller == seat and card.owner == 3-seat
    plans = graveyard_entry_plans(state, card.id)
    assert {p.replacement_source_id for p in plans} == {card.id, rival.id}
    assert {p.destination for p in plans} == {Zone.EXILE, Zone.LIBRARY}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('foreign_owner', [False, True])
@pytest.mark.parametrize('observer_name', ['Psychogenic Probe', "Cosi's Trickster"])
def test_paid_cost_shuffle_has_no_fake_resolving_cause(seat, name, foreign_owner, observer_name, tmp_path):
    state, card, source, _, action = position(name, seat, 'sacrifice', foreign_owner)
    owner = card.owner
    observer = raw_card(state, ROWS[observer_name], 3-owner, Zone.BATTLEFIELD)
    reference = {'incarnation': object_incarnation(card),
                 'zone_change_sequence': card.zone_change_sequence}
    state = execute(state, source, seat, 'sacrifice', action)
    state = restart(state, tmp_path, 'cost-observer')
    receipts = [item for item in state.stack if item.source_card_id == observer.id]
    assert len(receipts) == 1
    if receipts:
        assert receipts[0].controller == 3-owner
        assert receipts[0].payload['__shuffle_player'] == owner
        cause = receipts[0].payload['__shuffle_cause']
        assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
        assert cause['source_card_id'] == card.id and cause['source_card_id'] != source.id
        assert cause['source_reference'] == reference and cause['source_zone'] == 'battlefield'
        assert cause['source_owner'] == owner and cause['controller'] == seat
        from tests.test_self_graveyard_replacement_audit import ROWS as canonical
        assert cause['ability_clause'] == canonical[name]['oracle_text'].splitlines()[cause['ability_index']]
        assert 'stack_id' not in cause
        if observer_name == "Cosi's Trickster":
            assert receipts[0].payload['__may']
    assert not state.cards[observer.id].counters


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_cosi_does_not_observe_own_replacement_shuffle(seat, name):
    state, _, source, _, action = position(name, seat, 'sacrifice')
    observer = raw_card(state, ROWS["Cosi's Trickster"], seat, Zone.BATTLEFIELD)
    state = execute(state, source, seat, 'sacrifice', action)
    assert not any(item.source_card_id == observer.id for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_actual_selected_tower_mana_cost_has_no_fabricated_spell_receipt(seat, name, tmp_path):
    state, card, _, _, _ = position(name, seat, 'sacrifice')
    tower = raw_card(state, ROWS['Phyrexian Tower'], seat, Zone.BATTLEFIELD)
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    cosi = raw_card(state, ROWS["Cosi's Trickster"], 3-seat, Zone.BATTLEFIELD)
    reference = {'incarnation': object_incarnation(card),
                 'zone_change_sequence': card.zone_change_sequence}
    state.players[seat].mana_pool = {}
    state = act(state, seat, {'type': 'activate_mana_ability', 'card_id': tower.id,
                'ability_index': 1, 'color': 'B',
                'payment_choices': {'sacrifice_card_ids': [card.id]}})
    state = restart(state, tmp_path, 'tower-cost')
    assert state.players[seat].mana_pool.get('B') == 2 and state.cards[tower.id].tapped
    assert state.cards[card.id].zone == Zone.LIBRARY
    assert not any(item.source_card_id == tower.id for item in state.stack)
    probe_receipts = [item for item in state.stack if item.source_card_id == probe.id]
    assert len(probe_receipts) == 1
    receipts = [item for item in state.stack if item.source_card_id == cosi.id]
    assert len(receipts) == 1
    for receipt in [*probe_receipts, *receipts]:
        cause = receipt.payload['__shuffle_cause']
        assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
        assert cause['source_card_id'] == card.id and cause['source_card_id'] != tower.id
        assert cause['source_reference'] == reference and cause['source_zone'] == 'battlefield'
        assert cause['source_owner'] == seat and cause['controller'] == seat
        from tests.test_self_graveyard_replacement_audit import ROWS as canonical
        assert cause['ability_clause'] == canonical[name]['oracle_text'].splitlines()[cause['ability_index']]
        assert 'stack_id' not in cause


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_actual_http_unannounced_competing_payment_preserves_root_controller_sql(repo, client, seat, name):
    import main
    from tests.test_self_graveyard_replacement_audit import ROWS as canonical
    for raw in [*canonical.values(), ROWS['Rest in Peace']]:
        repo.upsert_card(normalize(raw))
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                           'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7221})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state, _, _, _, action = position(name, seat, 'sacrifice')
    raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 422, response.text
    assert 'competing graveyard replacement source' in response.json()['detail']['message']
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
