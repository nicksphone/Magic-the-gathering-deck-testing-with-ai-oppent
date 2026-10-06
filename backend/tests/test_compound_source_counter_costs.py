"""Whole counter costs only: actual Lux episodes, explicitly separate Fertilid cost seam."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine import costs
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.generic_import_fixtures import client as base_client
from tests.test_batch_graveyard_publication_audit import client, assert_private
from tests.test_builtin_metadata_refresh import repo
from tests.test_counter_activation_admission_audit import board as ballista_board
from tests.test_generic_protection_damage import CANONICAL, raw_card
from tests.test_kozilek_graveyard_trigger_audit import FRESH, passes
from tests.test_paid_counter_family_audit import board, ability, action, http_position, FAMILIES
from tests.test_self_graveyard_replacement_audit import act, snap, restart
from tests.test_spell_admission_safety_http import sql_facts


@pytest.mark.parametrize('text,quantity,kind,mana,tap', [
    ('Remove a +1/+1 counter from this creature', 1, '+1/+1', '', False),
    ('{1}{G}, Remove a +1/+1 counter from this creature', 1, '+1/+1', '{1}{G}', False),
    ('{T}, Remove three charge counters from this artifact', 3, 'charge', '', True),
    ('{2}{C}, {T}, Remove 12 charge counters from this permanent', 12, 'charge', '{2}{C}', True),
    ('remove two charge counters from this enchantment, {t}, {g}', 2, 'charge', '{G}', True),
    ('{0}, Remove an +1/+1 counter from this creature', 1, '+1/+1', '{0}', False),
    ('{W/U}, Remove one charge counter from this artifact', 1, 'charge', '{W/U}', False),
    ('{2/G}, Remove one charge counter from this artifact', 1, 'charge', '{2/G}', False),
    ('{W/P}, Remove one charge counter from this artifact', 1, 'charge', '{W/P}', False),
    ('{G/U/P}, Remove one charge counter from this artifact', 1, 'charge', '{G/U/P}', False),
    ('{S}, Remove one charge counter from this artifact', 1, 'charge', '{S}', False),
])
def test_complete_fixed_cost_parser_structures_every_component(text, quantity, kind, mana, tap):
    # Pure grammar input, never fabricated gameplay Oracle.
    parsed = costs.parse_activated_cost(text)
    assert parsed == costs.ActivatedCost(mana_cost=mana, tap_source=tap,
                                        remove_source_counters=quantity, remove_counter_kind=kind)


@pytest.mark.parametrize('text', [
    'Remove X +1/+1 counters from this creature',
    '{X}, Remove a +1/+1 counter from this creature',
    '{Y}, Remove a +1/+1 counter from this creature',
    '{Z}, Remove a +1/+1 counter from this creature',
    '{Q}, Remove a +1/+1 counter from this creature',
    '{P}, Remove a +1/+1 counter from this creature',
    '{W/W}, Remove a +1/+1 counter from this creature',
    '{G/G/P}, Remove a +1/+1 counter from this creature',
    '{1oops}, Remove a +1/+1 counter from this creature',
    'Remove 0 charge counters from this artifact',
    'Remove -1 charge counters from this artifact',
    'Remove zero charge counters from this artifact',
    'Remove a loyalty counter from this permanent',
    'Remove three charge counters from another artifact',
    'Remove three charge counters from target artifact',
    'Remove three charge counters from artifacts you control',
    'Remove a +1/+1 counter from this creature, Remove a charge counter from this creature',
    '{T}, {T}, Remove three charge counters from this artifact',
    '{T}, Remove three charge counters from this artifact, pay 2 life',
    '{1}{G}, Remove a +1/+1 counter from this creature and sacrifice this creature',
    'Pay 2 life and remove a +1/+1 counter from this creature',
    'Remove three charge counters from this artifact then draw a card',
    'Remove three charge counters from this artifact,',
    ',Remove three charge counters from this artifact',
    '{1},, Remove a +1/+1 counter from this creature',
    '{T} extra, Remove three charge counters from this artifact',
    '{T}: Remove three charge counters from this artifact',
])
def test_unknown_variable_multiple_or_partial_cost_never_admits_payment(text):
    state, source, _ = board(1, 'Lux Cannon')
    state.players[1].mana_pool = {'C': 10, 'G': 10}
    before = snap(state)
    assert costs.parse_activated_cost(text) == costs.ActivatedCost(supported=False)
    assert not costs.activated_cost_available(state, 1, source, text)
    assert not costs.apply_activated_costs(state, 1, source, text)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_exact_canonical_cost_boundary_spends_resources_once_repeated_full_snapshot(seat, name, tmp_path):
    state, source, _ = board(seat, name)
    text = ability(state, source)['mana_cost']
    before = snap(state)
    candidates = [deserialize_match_snapshot(deepcopy(before)) for _ in range(2)]
    for candidate in candidates:
        assert costs.activated_cost_available(candidate, seat, source, text)
        assert costs.apply_activated_costs(candidate, seat, source, text)
        assert candidate.cards[source].counters['+1/+1' if name == 'Fertilid' else 'charge'] == (1 if name == 'Fertilid' else 0)
        assert candidate.cards[source].tapped == (name == 'Lux Cannon')
        assert sum(candidate.players[seat].mana_pool.values()) == 0
        after = snap(candidate)
        assert not costs.apply_activated_costs(candidate, seat, source, text)
        assert snap(candidate) == after
    assert snap(candidates[0]) == snap(candidates[1]) and snap(state) == before
    assert_private(restart(candidates[0], tmp_path, 'literal-cost-only'))
    # Fertilid is ONLY a direct cost seam. Its missing search body is never forced onto the stack.
    assert not candidates[0].stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('bad', ['insufficient', 'boolean', 'float', 'negative', 'wrong_kind', 'reserved',
                                'foreign', 'missing_membership', 'mana_or_tap'])
def test_admitted_cost_reaches_real_resource_validation_and_preserves_entire_root(seat, name, bad):
    state, source, _ = board(seat, name)
    text = ability(state, source)['mana_cost']
    assert costs.parse_activated_cost(text).supported
    assert costs.activated_cost_available(state, seat, source, text)
    reserved = ()
    kind = '+1/+1' if name == 'Fertilid' else 'charge'
    if bad in ('insufficient', 'boolean', 'float', 'negative'):
        state.cards[source].counters[kind] = {'insufficient': 0 if name == 'Fertilid' else 2,
                                            'boolean': True, 'float': 3.0, 'negative': -1}[bad]
    elif bad == 'wrong_kind':
        state.cards[source].counters = {'charge' if name == 'Fertilid' else '+1/+1': 3}
    elif bad == 'reserved':
        reserved = (source,)
    elif bad == 'foreign':
        state.players[seat].battlefield.remove(source)
        state.players[3-seat].battlefield.append(source)
        state.cards[source].controller = 3-seat
    elif bad == 'missing_membership':
        state.players[seat].battlefield.remove(source)
    elif name == 'Fertilid':
        state.players[seat].mana_pool = {}
    else:
        state.cards[source].tapped = True
    before = snap(state)
    assert not costs.activated_cost_available(state, seat, source, text, unavailable_resources=reserved)
    assert not costs.apply_activated_costs(state, seat, source, text, unavailable_resources=reserved)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mutation', ['sequence', 'incarnation', 'controller', 'counter', 'object'])
def test_actual_lux_checked_payment_revalidates_stale_source_before_tap_or_removal(seat, mutation, monkeypatch):
    state, source, target = board(seat, 'Lux Cannon')
    original = costs._pay_activated_mana
    calls = []
    def payment(candidate, *args, **kwargs):
        assert original(candidate, *args, **kwargs)
        card = candidate.cards[source]
        assert not card.tapped and card.counters['charge'] == 3
        calls.append(mutation)
        # Explicit fault injection into a checked copy, not invented card text or legal mana mutation.
        if mutation == 'sequence':
            card.zone_change_sequence += 1
        elif mutation == 'incarnation':
            card.battlefield_incarnation = object_incarnation(card)+1
        elif mutation == 'controller':
            card.controller = 3-seat
        elif mutation == 'counter':
            card.counters['charge'] = 2
        else:
            candidate.cards[source] = deepcopy(card)
        return True
    monkeypatch.setattr(costs, '_pay_activated_mana', payment)
    before = snap(state)
    with pytest.raises(ActionRejected, match='Source counter payment changed'):
        act(state, seat, action('Lux Cannon', source, target, seat))
    assert calls and snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('response', ['Disenchant', 'Stifle'])
def test_actual_paid_lux_stack_response_keeps_payment_and_real_source_identity(seat, response, tmp_path):
    state, source, target = board(seat, 'Lux Cannon')
    row = CANONICAL[response] if response == 'Disenchant' else FRESH[response]
    assert row['oracle_id'] and row['object'] == 'card'
    spell = raw_card(state, row, 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'W': 1, 'C': 1} if response == 'Disenchant' else {'U': 1}
    reference, sequence = object_incarnation(state.cards[source]), state.cards[source].zone_change_sequence
    state = act(state, seat, action('Lux Cannon', source, target, seat))
    item = state.stack[0]
    assert item.source_card_id == source and item.controller == seat
    assert state.cards[source].tapped and state.cards[source].counters['charge'] == 0
    state = act(state, seat, {'type': 'pass_priority'})
    targets = {'target_card_id': source} if response == 'Disenchant' else {'target_stack_id': item.id}
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    assert sum(state.players[3-seat].mana_pool.values()) == 0
    state = passes(restart(state, tmp_path, 'real-response-stack'))
    if response == 'Stifle':
        assert not state.stack and state.cards[target].zone == Zone.BATTLEFIELD
        assert state.cards[source].counters['charge'] == 0 and state.cards[source].tapped
    else:
        assert state.cards[source].zone == Zone.GRAVEYARD
        assert state.cards[source].zone_change_sequence == sequence+1
        assert len(state.stack) == 1 and state.stack[0].source_card_id == source
        lki = state.cards[source].last_known_battlefield
        assert lki['battlefield_incarnation'] == reference and lki['counters']['charge'] == 0
        state = passes(restart(state, tmp_path, 'real-departed-source-ability'))
        assert state.cards[target].zone == Zone.GRAVEYARD and not state.stack
    assert_private(restart(state, tmp_path, 'real-response-resolution'))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_last_ballista_counter_still_pays_before_sba_and_damage_uses_lki(seat, tmp_path):
    state, source, _ = ballista_board(seat, counters=1)
    reference = object_incarnation(state.cards[source])
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 1,
                              'targets': {'target_player': 3-seat}})
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.stack[0].payload['__source_lki']['battlefield_incarnation'] == reference
    assert state.stack[0].payload['__source_lki']['counters']['+1/+1'] == 0
    state = passes(restart(state, tmp_path, 'last-counter-real-sba-stack'))
    assert state.players[3-seat].life == 19 and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_lux_foreign_owner_uses_controller_and_explicit_target(seat, tmp_path):
    state, source, target = board(seat, 'Lux Cannon')
    state.cards[source].owner = 3-seat  # Controlled stolen-artifact board, not a theft episode.
    state = act(state, seat, action('Lux Cannon', source, target, seat))
    assert state.stack[0].controller == seat and state.cards[source].owner == 3-seat
    state = passes(restart(state, tmp_path, 'foreign-owned-real-paid-destroy'))
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert state.cards[source].counters['charge'] == 0 and state.cards[source].tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target_name', ['White Knight', 'Progenitus'])
def test_actual_lux_target_legality_is_not_omitted_to_admit_costs(seat, target_name):
    state, source, target = board(seat, 'Lux Cannon', target_name)
    before = snap(state)
    if target_name == 'Progenitus':
        with pytest.raises(ActionRejected):
            act(state, seat, action('Lux Cannon', source, target, seat))
        assert snap(state) == before
    else:
        state = act(state, seat, action('Lux Cannon', source, target, seat))
        assert state.stack[0].payload['__announced_targets']['target_card_id'] == target
        assert state.cards[source].counters['charge'] == 0 and state.cards[source].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_lux_compound_paid_stack_atomic_failures_and_cold_restart(repo, client, seat, tmp_path):
    import main
    controller, source, target, path = http_position(repo, client, seat, 'Lux Cannon')
    protected = raw_card(controller.state, CANONICAL['Progenitus'], 3-seat, Zone.BATTLEFIELD)
    main._persist_active_match(repo, controller)
    candidate = action('Lux Cannon', source, target, seat)
    for actor, invalid in [(3-seat, candidate), (seat, {**candidate, 'targets': {}}),
                           (seat, {**candidate, 'targets': {'target_card_id': 'absent'}}),
                           (seat, {**candidate, 'targets': {'target_card_id': protected.id}}),
                           (seat, {**candidate, 'payment_choices': {'counter_amount': 0}})]:
        before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
        rejected = client.post(path + '/action', json={'player_id': actor, 'action': invalid})
        assert rejected.status_code in (403, 422), rejected.text
        assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    paid = client.post(path + '/action', json={'player_id': seat, 'action': candidate})
    assert paid.status_code == 200, paid.text
    controller = main.ACTIVE_MATCHES[controller.state.id]
    assert controller.state.cards[source].tapped and controller.state.cards[source].counters['charge'] == 0
    assert len(controller.state.stack) == 1 and controller.state.cards[target].zone == Zone.BATTLEFIELD
    before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post(path + '/action', json={'player_id': seat, 'action': candidate})
    assert rejected.status_code == 422
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    main.ACTIVE_MATCHES.pop(controller.state.id)
    main._restore_active_matches(repo, before[0]['id'])
    controller = main.ACTIVE_MATCHES[before[0]['id']]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    database = repo.session.get_bind().url.database
    if database:
        expected = tmp_path / 'cold-compound-http-expected.json'
        expected.write_text(json.dumps({'match_id': controller.state.id, 'root': before[0],
                                       'controller': before[1], 'sql': before[2]}))
        worker = Path(__file__).with_name('source_counter_http_restart_worker.py')
        result = subprocess.run([sys.executable, str(worker), database, str(expected)], capture_output=True,
                                text=True, timeout=60, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        (tmp_path / 'actual-cold-compound-http.log').write_text(result.stdout+result.stderr)
        assert result.returncode == 0, result.stdout+result.stderr
    while controller.state.stack:
        resolved = client.post(path + '/action', json={'player_id': controller.state.priority_player,
                                                      'action': {'type': 'pass_priority'}})
        assert resolved.status_code == 200, resolved.text
        controller = main.ACTIVE_MATCHES[controller.state.id]
    assert controller.state.cards[target].zone == Zone.GRAVEYARD
    assert controller.state.cards[source].tapped and controller.state.cards[source].counters['charge'] == 0
    assert_private(restart(controller.state, tmp_path, 'compound-http-resolution'))
