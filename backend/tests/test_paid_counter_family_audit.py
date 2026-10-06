"""Full canonical paid counter families: strict desired rows, no injected effects."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from game_state.state import MatchFactory, Zone, object_incarnation
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import ActionRejected
from rules_engine.costs import activated_cost_available, apply_activated_costs, parse_activated_cost
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from tests.generic_import_fixtures import client as base_client
from tests.test_batch_graveyard_publication_audit import client, assert_private
from tests.test_builtin_metadata_refresh import repo, seed_cache
from tests.test_generic_protection_damage import position, raw_card
from tests.test_kozilek_graveyard_trigger_audit import passes
from tests.test_self_graveyard_replacement_audit import act, restart, snap
from tests.test_spell_admission_safety_http import sql_facts


FIXTURES = Path(__file__).parent / 'fixtures/paid_counter_families'
ROWS = {name: json.loads((FIXTURES / filename).read_text()) for name, filename in
        [('Fertilid', 'fertilid.json'), ('Lux Cannon', 'lux-cannon.json')]}
FAMILIES = list(ROWS)


def board(seat, name, target_name='White Knight'):
    state, target = position(seat, target_name)
    source = raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD)
    # Controlled retained canonical board, NOT proof of casting/entry counter support.
    source.summoning_sick = False
    source.counters['+1/+1' if name == 'Fertilid' else 'charge'] = 2 if name == 'Fertilid' else 3
    state.players[seat].mana_pool = {'G': 1, 'C': 1} if name == 'Fertilid' else {}
    return state, source.id, target


def ability(state, source):
    return extract_activated_abilities(state.cards[source])[-1]


def action(name, source, target, seat):
    return {'type': 'activate_ability', 'card_id': source,
            'ability_index': 0 if name == 'Fertilid' else 1,
            'targets': {'target_player': seat} if name == 'Fertilid' else {'target_card_id': target}}


@pytest.mark.parametrize('name', FAMILIES)
def test_full_raw_receipt_identity_and_complete_oracle(name):
    path = FIXTURES / ('fertilid.json' if name == 'Fertilid' else 'lux-cannon.json')
    provenance = json.loads(path.with_suffix('.json.provenance.json').read_text())
    assert provenance['full_raw'] and provenance['url'].startswith('https://api.scryfall.com/cards/named?exact=')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance['sha256']
    assert ROWS[name]['oracle_id'] == {'Fertilid': '21f1c6d7-8289-44b2-b88f-c09e202be200',
                                     'Lux Cannon': 'ebdf26a4-77ee-4635-8d52-926bdca623f7'}[name]
    assert len(ROWS[name]['oracle_text'].splitlines()) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_complete_cost_body_and_index_extraction_is_query_pure(seat, name):
    state, source, _ = board(seat, name)
    before = snap(state)
    extracted = extract_activated_abilities(state.cards[source])
    printed = [line for line in ROWS[name]['oracle_text'].splitlines() if ': ' in line]
    assert len(extracted) == len(printed)
    assert [row['index'] for row in extracted] == list(range(len(printed)))
    for row, line in zip(extracted, printed):
        cost, text = line.split(': ', 1)
        assert row['mana_cost'] == cost.upper() and row['text'] == text
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_desired_full_source_counter_cost_and_resource_admission(seat, name):
    state, source, _ = board(seat, name)
    cost = ability(state, source)['mana_cost']
    before = snap(state)
    parsed = parse_activated_cost(cost)
    assert parsed.supported, f'Complete canonical cost unsupported: {cost}'
    assert parsed.remove_source_counters == (1 if name == 'Fertilid' else 3)
    assert parsed.remove_counter_kind == ('+1/+1' if name == 'Fertilid' else 'charge')
    assert parsed.mana_cost == ('{1}{G}' if name == 'Fertilid' else '')
    assert parsed.tap_source == (name == 'Lux Cannon')
    assert activated_cost_available(state, seat, source, cost, ability_index=ability(state, source)['index'])
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_desired_literal_body_has_no_noop_and_correct_target_owner(seat, name):
    state, source, target = board(seat, name)
    proxy = deepcopy(state.cards[source])
    # Compiler-only analysis of exact printed body, NEVER an executable injected card.
    proxy.oracle_text = ability(state, source)['text']
    proxy.card_faces = []
    proxy.mana_cost = ''
    before = snap(state)
    targets = action(name, source, target, 3-seat)['targets']
    spec = build_ability_spec(state, proxy, seat, targets, report_unsupported=False)
    assert not spec.used_fallback and spec.effect.key != 'noop', spec
    if name == 'Fertilid':
        assert spec.effect.key == 'search_library'
        assert spec.effect.payload['target_player'] == 3-seat
        assert spec.effect.payload['destination'] == 'battlefield'
        assert spec.effect.payload['tapped'] and spec.effect.payload['shuffle']
        assert spec.effect.payload['count'] == 1
        assert spec.effect.payload['contains'] == 'basic_land'
    else:
        assert spec.effect.key == 'destroy_permanent'
        assert spec.effect.payload['target_card_id'] == target
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_desired_payable_real_ability_is_offered_without_query_mutation(seat, name):
    state, source, _ = board(seat, name)
    before = snap(state)
    offered = RulesEngine().legal_moves(state, seat)
    assert snap(state) == before
    assert any(move.get('card_id') == source and move.get('ability_index') == ability(state, source)['index']
               for move in offered)


@pytest.mark.parametrize('seat', [1, 2])
def test_desired_lux_real_tap_three_charge_paid_before_delayed_destroy(seat, tmp_path):
    state, source, target = board(seat, 'Lux Cannon')
    reference, sequence = object_incarnation(state.cards[source]), state.cards[source].zone_change_sequence
    state = act(state, seat, action('Lux Cannon', source, target, seat))
    assert state.cards[source].tapped and state.cards[source].counters['charge'] == 0
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert len(state.stack) == 1 and state.stack[-1].controller == seat
    assert state.stack[-1].source_card_id == source
    state = passes(restart(state, tmp_path, 'lux-paid-stack'))
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert object_incarnation(state.cards[source]) == reference
    assert state.cards[source].zone_change_sequence == sequence
    assert not state.stack
    assert_private(restart(state, tmp_path, 'lux-real-resolution'))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target_self', [False, True])
@pytest.mark.parametrize('find', [False, True])
def test_desired_fertilid_actual_target_search_can_fail_find_but_must_shuffle(seat, target_self, find, tmp_path):
    state, source, _ = board(seat, 'Fertilid')
    target_seat = seat if target_self else 3-seat
    # Canonical basic land hydration already retained by setup; no invented land metadata.
    seed = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_text())['cards']['Island']
    lands = [raw_card(state, seed, target_seat, Zone.LIBRARY).id for _ in range(3)]
    original_library = list(state.players[target_seat].library)
    state = act(state, seat, action('Fertilid', source, None, target_seat))
    assert state.cards[source].counters['+1/+1'] == 1
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert len(state.stack) == 1 and state.stack[-1].controller == seat
    state = passes(restart(state, tmp_path, 'fertilid-paid-stack'))
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'search_library' and pending['player_id'] == target_seat
    assert set(lands).issubset(pending['options']) and pending['min_count'] == 0
    state = restart(state, tmp_path, 'target-private-search')
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, 3-target_seat, {'type': 'choose_mechanic', 'card_ids': [lands[0]]})
    assert snap(state) == before
    rng = state.rng.getstate()
    chosen = [lands[0]] if find else []
    state = act(state, target_seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    assert state.pending_mechanic_choice is None
    assert set(state.players[target_seat].library) == set(original_library)-set(chosen)
    assert state.rng.getstate() != rng
    for cid in chosen:
        assert state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].tapped
        assert state.cards[cid].owner == state.cards[cid].controller == target_seat
    assert_private(restart(state, tmp_path, 'fertilid-complete-search'))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('bad', ['actor', 'index', 'missing_target', 'target', 'foreign_source', 'departed', 'empty', 'wrong_kind'])
def test_invalid_real_candidate_rejects_entire_root_with_no_partial_payment(seat, name, bad):
    state, source, target = board(seat, name)
    candidate = action(name, source, target, seat)
    actor = seat
    if bad == 'actor':
        actor = 3-seat
    elif bad == 'index':
        candidate['ability_index'] = 99
    elif bad == 'missing_target':
        candidate['targets'] = {}
    elif bad == 'target':
        candidate['targets'] = {'target_player': 99} if name == 'Fertilid' else {'target_card_id': 'absent'}
    elif bad == 'foreign_source':
        state.players[seat].battlefield.remove(source)
        state.players[3-seat].battlefield.append(source)
        state.cards[source].controller = 3-seat
    elif bad == 'departed':
        state.players[seat].battlefield.remove(source)
        state.players[seat].graveyard.append(source)
        state.cards[source].move_to_zone(Zone.GRAVEYARD)
    else:
        state.cards[source].counters.clear()
        if bad == 'wrong_kind':
            state.cards[source].counters['charge' if name == 'Fertilid' else '+1/+1'] = 3
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, actor, candidate)
    assert snap(state) == before
    assert_private(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_supported_complete_cost_pays_exactly_once_at_direct_boundary(seat, name):
    state, source, _ = board(seat, name)
    before = snap(state)
    cost = ability(state, source)['mana_cost']
    # Cost-only boundary: Fertilid's missing search effect is never injected/executed.
    parsed = parse_activated_cost(cost)
    assert parsed.supported and parsed.remove_source_counters == (1 if name == 'Fertilid' else 3)
    assert parsed.remove_counter_kind == ('+1/+1' if name == 'Fertilid' else 'charge')
    assert parsed.mana_cost == ('{1}{G}' if name == 'Fertilid' else '')
    assert parsed.tap_source == (name == 'Lux Cannon')
    assert activated_cost_available(state, seat, source, cost)
    assert snap(state) == before
    repeated = deepcopy(state)
    for candidate in (state, repeated):
        assert apply_activated_costs(candidate, seat, source, cost)
        assert candidate.cards[source].counters['+1/+1' if name == 'Fertilid' else 'charge'] == (1 if name == 'Fertilid' else 0)
        assert candidate.cards[source].tapped == (name == 'Lux Cannon')
        assert sum(candidate.players[seat].mana_pool.values()) == 0
        assert not candidate.stack
        assert {pid: p.life for pid, p in candidate.players.items()} == {1: 20, 2: 20}
        paid = snap(candidate)
        assert not apply_activated_costs(candidate, seat, source, cost)
        assert snap(candidate) == paid
    assert snap(state) == snap(repeated)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_lux_charge_building_taps_pays_once_and_resolves_after_restart(seat, tmp_path):
    state, source, _ = board(seat, 'Lux Cannon')
    candidate = {'type': 'activate_ability', 'card_id': source, 'ability_index': 0, 'targets': {}}
    reference = object_incarnation(state.cards[source])
    state = act(state, seat, candidate)
    assert state.cards[source].tapped and state.cards[source].counters['charge'] == 3
    assert len(state.stack) == 1 and state.stack[0].effect_key == 'add_counters'
    assert state.stack[0].source_card_id == source and state.stack[0].controller == seat
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, candidate)
    assert snap(state) == before
    state = passes(restart(state, tmp_path, 'real-lux-charge-stack'))
    assert state.cards[source].counters['charge'] == 4
    assert object_incarnation(state.cards[source]) == reference
    assert_private(restart(state, tmp_path, 'real-lux-charge-resolved'))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('bad', ['insufficient', 'boolean', 'reserved', 'mana_or_tap'])
def test_cost_resource_negative_queries_are_pure_but_currently_shadowed_by_parser(seat, name, bad):
    state, source, _ = board(seat, name)
    reserved = ()
    kind = '+1/+1' if name == 'Fertilid' else 'charge'
    if bad == 'insufficient':
        state.cards[source].counters[kind] = 0 if name == 'Fertilid' else 2
    elif bad == 'boolean':
        state.cards[source].counters[kind] = True  # Controlled malformed resource seam.
    elif bad == 'reserved':
        reserved = (source,)
    elif name == 'Fertilid':
        state.players[seat].mana_pool = {}
    else:
        state.cards[source].tapped = True
    before = snap(state)
    assert not activated_cost_available(state, seat, source, ability(state, source)['mana_cost'],
                                        unavailable_resources=reserved)
    assert not apply_activated_costs(state, seat, source, ability(state, source)['mana_cost'],
                                   unavailable_resources=reserved)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_reachable_lux_charge_payment_belongs_to_controller_not_foreign_owner(seat, tmp_path):
    state, source, _ = board(seat, 'Lux Cannon')
    state.cards[source].owner = 3-seat  # Controlled lawful stolen-artifact board, not a theft episode.
    sequence = state.cards[source].zone_change_sequence
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 0, 'targets': {}})
    assert state.stack[0].controller == seat and state.stack[0].source_card_id == source
    assert state.cards[source].owner == 3-seat and state.cards[source].controller == seat
    state = passes(restart(state, tmp_path, 'foreign-owned-controller-charge'))
    assert state.cards[source].counters['charge'] == 4 and state.cards[source].tapped
    assert state.cards[source].zone_change_sequence == sequence


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_hidden_unobserved_complete_canonical_metadata_does_not_change_actor_view(seat, name):
    from ai.information import decision_view
    state, _, _ = board(seat, name)
    hidden = raw_card(state, ROWS[name], 3-seat, Zone.HAND)
    unseen = raw_card(state, ROWS[name], 3-seat, Zone.LIBRARY)
    before = snap(state)
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    altered = deepcopy(state)
    other = ROWS['Lux Cannon' if name == 'Fertilid' else 'Fertilid']
    for cid in (hidden.id, unseen.id):
        sample = MatchFactory.from_decks([{**other, 'card_name': other['name'], 'quantity': 8}], [], seed=831)
        card = deepcopy(next(iter(sample.cards.values())))
        card.id, card.zone = cid, altered.cards[cid].zone
        card.owner = card.controller = 3-seat
        card.zone_change_sequence = altered.cards[cid].zone_change_sequence
        altered.cards[cid] = card
    alternate_view, alternate_moves = decision_view(altered, seat, RulesEngine().legal_moves(altered, seat))
    assert snap(alternate_view) == snap(view)
    assert alternate_moves == moves
    assert snap(state) == before
    assert_private(state)


def http_position(repo, client, seat, name):
    import main
    seed_cache(repo, [{'card_name': 'Island'}])
    deck = [{'card_name': 'Island', 'quantity': 8}]
    started = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck, 'sandbox': True,
        'controller_a': 'human', 'controller_b': 'human', 'seed': 741})
    assert started.status_code == 200, started.text
    controller = main.ACTIVE_MATCHES[started.json()['id']]
    state, source, target = board(seat, name)
    state.id = controller.state.id
    controller.state, controller.engine = state, RulesEngine()
    main._persist_active_match(repo, controller)
    return controller, source, target, '/matches/' + state.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_desired_actual_http_complete_counter_cost_admission(repo, client, seat, name):
    controller, source, target, path = http_position(repo, client, seat, name)
    response = client.post(path + '/action', json={'player_id': seat, 'action': action(name, source, target, seat)})
    assert response.status_code == 200, response.text
    import main
    controller = main.ACTIVE_MATCHES[controller.state.id]
    assert len(controller.state.stack) == 1
    assert controller.state.cards[source].counters['+1/+1' if name == 'Fertilid' else 'charge'] == (1 if name == 'Fertilid' else 0)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_http_paid_counter_execution_and_search_preserve_contract(repo, client, seat, name):
    import main
    controller, source, target, path = http_position(repo, client, seat, name)
    if name == 'Fertilid':
        controller.state.mechanic_choice_players.add(seat)
        main._persist_active_match(repo, controller)
    before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post(path + '/action', json={'player_id': seat, 'action': action(name, source, target, seat)})
    if name == 'Fertilid':
        assert response.status_code == 200, response.text
        controller = main.ACTIVE_MATCHES[controller.state.id]
        assert controller.state.cards[source].counters['+1/+1'] == 1
        assert controller.state.players[seat].mana_pool['G'] == 0
        assert controller.state.players[seat].mana_pool['C'] == 0
        assert len(controller.state.stack) == 1
        assert controller.state.stack[0].controller == seat
        chosen = controller.state.players[seat].library[-1]
        library_count = len(controller.state.players[seat].library)
        for _ in range(4):
            if controller.state.pending_mechanic_choice:
                break
            resolved = client.post(path + '/action', json={
                'player_id': controller.state.priority_player,
                'action': {'type': 'pass_priority'}})
            assert resolved.status_code == 200, resolved.text
            controller = main.ACTIVE_MATCHES[controller.state.id]
        pending = controller.state.pending_mechanic_choice
        assert pending and pending['kind'] == 'search_library'
        assert pending['player_id'] == seat and chosen in pending['options']
        assert set(resolved.json()['pending_mechanic_choice']) <= {
            'kind', 'player_id', 'label', 'count', 'min_count'}
        paused = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
        main.ACTIVE_MATCHES.pop(controller.state.id)
        main._restore_active_matches(repo, paused[0]['id'])
        controller = main.ACTIVE_MATCHES[paused[0]['id']]
        assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == paused
        selected = client.post(path + '/action', json={'player_id': seat,
            'action': {'type': 'choose_mechanic', 'card_ids': [chosen]}})
        assert selected.status_code == 200, selected.text
        controller = main.ACTIVE_MATCHES[controller.state.id]
        assert controller.state.pending_mechanic_choice is None
        assert not controller.state.stack
        assert controller.state.cards[chosen].zone == Zone.BATTLEFIELD
        assert controller.state.cards[chosen].controller == seat
        assert controller.state.cards[chosen].tapped
        assert len(controller.state.players[seat].library) == library_count - 1
        assert controller.state.cards[source].counters['+1/+1'] == 1
    else:
        assert response.status_code == 200, response.text
        controller = main.ACTIVE_MATCHES[controller.state.id]
        assert controller.state.cards[source].tapped and controller.state.cards[source].counters['charge'] == 0
        assert controller.state.cards[target].zone == Zone.BATTLEFIELD
        assert len(controller.state.stack) == 1 and controller.state.stack[0].source_card_id == source
        assert controller.state.stack[0].controller == seat
        paid = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
        repeat = client.post(path + '/action', json={'player_id': seat, 'action': action(name, source, target, seat)})
        assert repeat.status_code == 422, repeat.text
        assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == paid
        main.ACTIVE_MATCHES.pop(controller.state.id)
        main._restore_active_matches(repo, paid[0]['id'])
        controller = main.ACTIVE_MATCHES[paid[0]['id']]
        assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == paid
        while controller.state.stack:
            resolved = client.post(path + '/action', json={'player_id': controller.state.priority_player,
                                                          'action': {'type': 'pass_priority'}})
            assert resolved.status_code == 200, resolved.text
            controller = main.ACTIVE_MATCHES[controller.state.id]
        assert controller.state.cards[target].zone == Zone.GRAVEYARD
        assert controller.state.cards[source].tapped and controller.state.cards[source].counters['charge'] == 0
    assert_private(controller.state)


@pytest.mark.parametrize('seat', [1, 2])
def test_reachable_lux_http_atomic_root_sql_cold_restart_and_private_resolution(repo, client, seat, tmp_path):
    import main
    controller, source, target, path = http_position(repo, client, seat, 'Lux Cannon')
    candidate = {'type': 'activate_ability', 'card_id': source, 'ability_index': 0, 'targets': {}}
    for actor, invalid in [(3-seat, candidate), (seat, {**candidate, 'ability_index': 99}),
                           (seat, action('Lux Cannon', source, 'absent', seat)),
                           (seat, {**candidate, 'payment_choices': {'counter_amount': 0}})]:
        before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
        response = client.post(path + '/action', json={'player_id': actor, 'action': invalid})
        assert response.status_code in (403, 422), response.text
        assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    response = client.post(path + '/action', json={'player_id': seat, 'action': candidate})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[controller.state.id]
    assert controller.state.cards[source].tapped and controller.state.cards[source].counters['charge'] == 3
    assert len(controller.state.stack) == 1
    before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    main.ACTIVE_MATCHES.pop(controller.state.id)
    main._restore_active_matches(repo, before[0]['id'])
    controller = main.ACTIVE_MATCHES[before[0]['id']]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    assert_private(controller.state)
    database = repo.session.get_bind().url.database
    if database:
        expected = tmp_path / 'cold-http-expected.json'
        expected.write_text(json.dumps({'match_id': controller.state.id, 'root': before[0],
                                       'controller': before[1], 'sql': before[2]}))
        worker = Path(__file__).with_name('source_counter_http_restart_worker.py')
        result = subprocess.run([sys.executable, str(worker), database, str(expected)], capture_output=True,
                                text=True, timeout=60, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        (tmp_path / 'cold-http.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
    while controller.state.stack:
        response = client.post(path + '/action', json={'player_id': controller.state.priority_player,
                                                      'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
        controller = main.ACTIVE_MATCHES[controller.state.id]
    assert controller.state.cards[source].counters['charge'] == 4
    assert_private(restart(controller.state, tmp_path, 'actual-http-charge-resolved'))
