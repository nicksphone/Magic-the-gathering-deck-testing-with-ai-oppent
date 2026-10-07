"""Keyword-only paid Suspend-X contracts; full printed bodies stay unqualified."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api_contracts import ActionRequest
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.suspend import action_options, instruction, remove_time_counters, suspended
from tests.test_suspend_lifecycle import one, setup
from tests.variable_suspend_support import (
    CONTROL_DIRECTORY, NAMES, PROVENANCE, RAW, ROOT, RIFT, position, resume,
)


def act(state, seat, cid, x):
    return checked_action(state, RulesEngine(), seat, {'type': 'suspend', 'card_id': cid, 'x_value': x})


def live_position(name, seat):
    # Both real libraries cover opening draws; unlike the historical intake's
    # empty opponent deck this position can actually pass/resolve priority.
    cards = [{**RIFT, 'card_name': RIFT['name'], 'quantity': 10}]
    actor = [{**RAW[name], 'card_name': name, 'quantity': 1}, *cards]
    state = MatchFactory.from_decks(actor if seat == 1 else cards, actor if seat == 2 else cards, seed=1719)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.turn = 5
    state.mechanic_choice_players = state.trigger_order_choice_players = {1, 2}
    card = next(card for card in state.cards.values() if card.name == name)
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
    state.players[seat].library.remove(card.id)
    card.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(card.id)
    state.players[seat].mana_pool = {'C': 6, RAW[name]['colors'][0]: 1}
    return state, card.id


def assert_rejected(state, seat, action):
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before


def canonical_land(state, seat, filename):
    raw = json.loads((CONTROL_DIRECTORY / filename).read_bytes())
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 1}], [], seed=1719)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.BATTLEFIELD)
    card.summoning_sick = False
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    return card


@pytest.mark.parametrize('value', [True, False, 1.0, '2', -1])
def test_public_strict_top_level_x_rejects_invalid_types(value):
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({'player_id': 1, 'action': {'type': 'suspend', 'card_id': 'card', 'x_value': value}})


@pytest.mark.parametrize('field,value', [('targets', {'x_value': 2}), ('time_counters', 2), ('effect_key', 'draw')])
def test_no_cast_targets_or_counter_override(field, value):
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({'player_id': 1, 'action': {'type': 'suspend', 'card_id': 'card', field: value}})


def test_canonical_bytes_provenance_and_existing_fixed_instruction_api():
    for row in PROVENANCE['canonical_cards']:
        data = (ROOT / row['path']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['sha256']
        assert json.loads(data)['id'] == row['printing_id']
        state, cid = position(row['name'])
        assert instruction(state.cards[cid]) is None
        assert state.cards[cid].oracle_text == RAW[row['name']]['oracle_text']


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_query_schema_actual_finite_bounds_and_root_rng_replay(name, seat):
    state, cid = position(name, seat)
    before = serialize_match_snapshot(state)
    options = action_options(state, seat, state.cards[cid])
    assert options['time_counters_variable'] is True and 'time_counters' not in options
    assert options['choice_schema'] == {'x_value': {'type': 'integer', 'required': True, 'minimum': 1, 'maximum': 3}}
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'suspend' and m['card_id'] == cid)
    assert {key: move[key] for key in options} == options
    assert serialize_match_snapshot(state) == before
    assert action_options(resume(state), seat, resume(state).cards[cid]) == options
    for x in (1, 2, 3, 4):
        assert can_pay_with_pool_and_lands(state, seat, options['mana_cost'], x_value=x,
                                          payment_kind='suspend', apply_modifiers=False) == (x <= 3)
    assert_rejected(state, seat, {'type': 'suspend', 'card_id': cid})
    state.players[seat].mana_pool.clear()
    assert_rejected(state, seat, {'type': 'suspend', 'card_id': cid, 'x_value': 3})


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('x', [None, 0, -1, True, False, 1.0, '1', 4])
def test_raw_variable_missing_invalid_or_unaffordable_refuses_without_payment(name, x):
    state, cid = position(name)
    assert_rejected(state, 1, {'type': 'suspend', 'card_id': cid, 'x_value': x})


@pytest.mark.parametrize('x', [0, 1, True, '1'])
def test_fixed_surplus_x_is_not_ignored(x):
    state, cid = setup()
    assert_rejected(state, 1, {'type': 'suspend', 'card_id': cid, 'x_value': x})


@pytest.mark.parametrize('explicit_null', [False, True])
def test_fixed_public_legacy_missing_or_null_still_pays_exactly(explicit_null):
    state, cid = setup()
    action = {'type': 'suspend', 'card_id': cid}
    if explicit_null:
        action['x_value'] = None
    parsed = ActionRequest.model_validate({'player_id': 1, 'action': action})
    successor = checked_action(state, RulesEngine(), 1, parsed.action.model_dump())
    assert successor.cards[cid].counters['time'] == 1
    assert successor.players[1].mana_pool['R'] == 0


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('control', ['zero', 'wrong-color', 'restricted'])
def test_zero_wrong_color_and_restricted_pool_no_offer(name, control):
    state, cid = position(name)
    color = RAW[name]['colors'][0]
    if control == 'zero':
        state.players[1].mana_pool.clear()
    elif control == 'wrong-color':
        state.players[1].mana_pool = {'C': 20}
    else:
        state.players[1].restricted_mana_pool = [
            {'color': 'C', 'amount': 6, 'snow': False, 'rule': {'cast_types': ['Creature'], 'activate_types': []}},
        ]
    before = serialize_match_snapshot(state)
    assert action_options(state, 1, state.cards[cid]) is None
    assert_rejected(state, 1, {'type': 'suspend', 'card_id': cid, 'x_value': 1})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('amount', [True, -1, float('inf'), float('nan'), '6'])
def test_unknown_or_infinite_pool_assumptions_fail_closed(amount):
    state, cid = position(NAMES[0])
    state.players[1].mana_pool['C'] = amount
    before = deepcopy(state.players[1].mana_pool)
    assert action_options(state, 1, state.cards[cid]) is None
    assert state.players[1].mana_pool['C'] is amount or state.players[1].mana_pool == before


def test_no_arbitrary_x_ceiling_with_large_genuine_finite_pool():
    state, cid = position(NAMES[0])
    state.players[1].mana_pool['C'] = 200003
    assert action_options(state, 1, state.cards[cid])['choice_schema']['x_value']['maximum'] == 200000
    request = ActionRequest.model_validate({'player_id': 1, 'action': {'type': 'suspend', 'card_id': cid, 'x_value': 200000}})
    successor = checked_action(state, RulesEngine(), 1, request.action.model_dump())
    assert successor.cards[cid].counters['time'] == 200000
    assert successor.players[1].mana_pool['C'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_real_finite_pool_and_canonical_lands_bound_and_payment(seat):
    state, cid = position('Aeon Chronicler', seat)
    state.players[seat].mana_pool = {'C': 3}
    island = canonical_land(state, seat, 'island.json')
    land = canonical_land(state, seat, 'mutavault.json')
    before = serialize_match_snapshot(state)
    assert action_options(state, seat, state.cards[cid])['choice_schema']['x_value']['maximum'] == 1
    assert serialize_match_snapshot(state) == before
    successor = act(state, seat, cid, 1)
    assert successor.cards[island.id].tapped and successor.cards[land.id].tapped
    assert successor.cards[cid].counters['time'] == 1
    assert sum(successor.players[seat].mana_pool.values()) == 0


def test_real_restricted_creature_mana_source_is_not_suspend_funding():
    from tests.test_restricted_mana import add
    state, cid = position('Aeon Chronicler')
    state.players[1].mana_pool = {'C': 3}
    add(state, 'Somberwald Sage')
    assert action_options(state, 1, state.cards[cid]) is None


@pytest.mark.parametrize('assumption', ['paid', 'bundled', 'unbounded', 'no-tap', 'invalid-output'])
def test_resource_query_fails_closed_with_bounded_planner_calls(monkeypatch, assumption):
    # Fault injection at planner seams, not fabricated positive card mechanics.
    from rules_engine import mana, mana_abilities
    state, cid = position('Aeon Chronicler')
    calls = []
    if assumption == 'paid':
        monkeypatch.setattr(mana_abilities, 'paid_candidates', lambda *a, **kw: iter([('source', (), 'C')]))
    elif assumption == 'bundled':
        monkeypatch.setattr(mana_abilities, 'needs_mana_bundles', lambda *a: True)
    elif assumption in {'no-tap', 'invalid-output'}:
        canonical_land(state, 1, 'island.json')
        spec = (0, '' if assumption == 'no-tap' else '{T}', '')
        bundle = {'U': 1} if assumption == 'no-tap' else {'U': float('inf')}
        monkeypatch.setattr(mana_abilities, 'free_mana_options', lambda *a, **kw: [(spec, 'U', bundle, {}, 0)])
    else:
        def always_payable(*a, **kw):
            calls.append(kw['x_value'])
            return True
        monkeypatch.setattr(mana, 'can_pay_with_pool_and_lands', always_payable)
    before = serialize_match_snapshot(state)
    assert action_options(state, 1, state.cards[cid]) is None
    assert calls == ([8] if assumption == 'unbounded' else [])
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('control', ['owner', 'priority', 'opponent-turn', 'combat', 'untap', 'cleanup', 'pending', 'zone'])
def test_timing_owner_and_continuation_revalidation(control):
    state, cid = position('Aeon Chronicler')
    if control == 'owner': state.cards[cid].owner = 2
    elif control == 'priority': state.priority_player = 2
    elif control == 'opponent-turn': state.active_player = 2
    elif control == 'combat': state.step = Step.DECLARE_ATTACKERS
    elif control == 'untap': state.step = Step.UNTAP
    elif control == 'cleanup': state.step = Step.CLEANUP
    elif control == 'pending': state.pending_mechanic_choice = {'kind': 'suspend_cast', 'player_id': 1, 'suspend_payload': {'card_id': cid, 'sequence': 0}}
    else: state.cards[cid].move_to_zone(Zone.EXILE)
    assert_rejected(state, 1, {'type': 'suspend', 'card_id': cid, 'x_value': 1})


@pytest.mark.parametrize('control', ['layout', 'faces', 'type', 'zero-clause', 'unknown-symbol', 'second-X', 'extra-time', 'extra-suspend'])
def test_rejected_metadata_corruption_is_not_new_oracle(control):
    state, cid = position('Aeon Chronicler')
    card = state.cards[cid]
    if control == 'layout': card.layout = 'transform'
    elif control == 'faces': card.card_faces = [{}]
    elif control == 'type': card.types = ['Sorcery']
    elif control == 'zero-clause': card.oracle_text = card.oracle_text.replace("X can't be 0.", '')
    elif control == 'unknown-symbol': card.oracle_text = card.oracle_text.replace('{X}{3}{U}', '{X}{3}{Q}')
    elif control == 'second-X': card.oracle_text = card.oracle_text.replace('{X}{3}{U}', '{X}{X}{U}')
    elif control == 'extra-time': card.oracle_text += '\nRemove a time counter from this card.'
    else: card.oracle_text += '\nSuspend 1\u2014{U}'
    assert action_options(state, 1, card) is None


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_paid_counter_resume_owner_upkeep_free_cast_no_reselected_x(name, seat):
    state, cid = live_position(name, seat)
    state = resume(act(state, seat, cid, 2))
    state.cards[cid].controller = 3-seat
    state.step = Step.UPKEEP
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': 3-seat})
    assert not state.stack
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
    assert state.stack[-1].effect_key == 'suspend_upkeep'
    state = resume(one(state))
    if name == 'Aeon Chronicler':
        assert state.cards[cid].counters['time'] == 1
        state = _resolve_independent_owner_draw(state, seat, cid)
    assert state.cards[cid].counters['time'] == 1 and not state.stack
    assert suspended(state.cards[cid])
    if name == 'Aeon Chronicler':
        state.trigger_order_choice_required = True
    remove_time_counters(state, cid)
    if name == 'Aeon Chronicler':
        state = _order_keyword_above_draw(state, seat, cid)
    assert state.stack[-1].effect_key == 'suspend_cast_trigger'
    state = resume(one(state))
    moves = RulesEngine().legal_moves(state, seat)
    cast = next(m for m in moves if m['type'] == 'cast_spell')
    assert 'x_value_max' not in cast['target_hints']
    before = serialize_match_snapshot(state)
    successor = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True})
    assert serialize_match_snapshot(state) == before
    assert successor.cards[cid].zone == Zone.STACK and successor.cards[cid].controller == seat
    assert successor.spells_cast_this_turn[seat] == 1 and not successor.pending_mechanic_choice
    assert serialize_match_snapshot(resume(successor)) == serialize_match_snapshot(successor)
    # This qualifies casting permission, NOT either card's entire resolution.
    resolve_effect(successor, 3-seat, 'counter_spell', {'target_stack_id': successor.stack[-1].id})
    assert successor.cards[cid].zone == Zone.GRAVEYARD
    if name == 'Aeon Chronicler':
        successor = _resolve_independent_owner_draw(successor, seat, cid)
        assert not successor.stack


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_countered_keyword_triggers_do_not_reask_paid_x(name, seat):
    state, cid = position(name, seat)
    if name == 'Aeon Chronicler':
        reference_cid = cid
        reference = act(state, seat, cid, 1)
        state, cid = live_position(name, seat)
    state = act(state, seat, cid, 1)
    if name == 'Aeon Chronicler':
        assert state.players[seat].mana_pool == reference.players[seat].mana_pool
        assert state.cards[cid].counters == reference.cards[reference_cid].counters
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
    resolve_effect(state, 3-seat, 'counter_ability', {'target_stack_id': state.stack[-1].id})
    assert state.cards[cid].counters['time'] == 1 and not state.stack
    if name == 'Aeon Chronicler':
        state.trigger_order_choice_required = True
    remove_time_counters(state, cid)
    if name == 'Aeon Chronicler':
        state = _order_keyword_above_draw(state, seat, cid)
        assert state.stack[-1].effect_key == 'suspend_cast_trigger'
    resolve_effect(state, 3-seat, 'counter_ability', {'target_stack_id': state.stack[-1].id})
    if name == 'Aeon Chronicler':
        assert not state.pending_mechanic_choice
        state = _resolve_independent_owner_draw(state, seat, cid)
    assert not state.pending_mechanic_choice and not state.stack
    assert not suspended(state.cards[cid])
    assert_rejected(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True})


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_real_stifle_cast_counters_last_counter_permission(name, seat):
    from tests.test_counterability_scope import add_card
    state, cid = live_position(name, seat)
    state = act(state, seat, cid, 1)
    if name == 'Aeon Chronicler':
        state.trigger_order_choice_required = True
    remove_time_counters(state, cid)
    if name == 'Aeon Chronicler':
        state = _order_keyword_above_draw(state, seat, cid)
        assert state.stack[-1].effect_key == 'suspend_cast_trigger'
    target = state.stack[-1].id
    stifle = add_card(state, 'Stifle', Zone.HAND, 3-seat)
    state.players[3-seat].mana_pool = {'U': 1}
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), 3-seat, {'type': 'cast_spell', 'card_id': stifle.id,
                                                      'targets': {'target_stack_id': target}})
    state = one(resume(state))
    if name == 'Aeon Chronicler':
        assert not state.pending_mechanic_choice
        state = _resolve_independent_owner_draw(state, seat, cid)
    assert not state.stack and not state.pending_mechanic_choice
    assert state.cards[cid].zone == Zone.EXILE and not suspended(state.cards[cid])
    assert_rejected(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True})


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_decline_and_stale_incarnation_keep_existing_sequence_guards(name, seat):
    state, cid = live_position(name, seat)
    state = act(state, seat, cid, 1)
    if name == 'Aeon Chronicler':
        state.trigger_order_choice_required = True
    remove_time_counters(state, cid)
    if name == 'Aeon Chronicler':
        state = _order_keyword_above_draw(state, seat, cid)
        assert state.stack[-1].effect_key == 'suspend_cast_trigger'
    stale = resume(state)
    stale.players[seat].exile.remove(cid)
    stale.cards[cid].move_to_zone(Zone.HAND)
    stale.players[seat].hand.append(cid)
    stale.players[seat].hand.remove(cid)
    stale.cards[cid].move_to_zone(Zone.EXILE)
    stale.players[seat].exile.append(cid)
    stale = one(resume(stale))
    if name == 'Aeon Chronicler':
        assert not stale.pending_mechanic_choice
        stale = _resolve_independent_owner_draw(stale, seat, cid)
    assert not stale.stack and not stale.pending_mechanic_choice
    state = one(resume(state))
    assert_rejected(state, seat, {'type': 'cast_spell', 'card_id': 'not-the-source', 'from_exile': True})
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert state.cards[cid].zone == Zone.EXILE and not state.pending_mechanic_choice
    assert_rejected(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True})
    if name == 'Aeon Chronicler':
        state = _resolve_independent_owner_draw(state, seat, cid)
        assert not state.stack


@pytest.mark.parametrize('name', NAMES)
def test_fullcard_warning_and_unresolved_exile_trigger_remain_explicit(name):
    state, cid = position(name)
    if name == 'Aeon Chronicler':
        reference_cid = cid
        reference = act(state, 1, cid, 2)
        state, cid = live_position(name, 1)
    metadata = {**RAW[name], 'card_name': name, 'card_data_sources': ['cache']}
    assert 'suspend' in known_unsupported_mechanics(RAW[name]['oracle_text'], card_name=name, canonical_context=metadata)
    state = act(state, 1, cid, 2)
    if name == 'Aeon Chronicler':
        assert state.players[1].mana_pool == reference.players[1].mana_pool
        assert state.cards[cid].counters == reference.cards[reference_cid].counters
    remove_time_counters(state, cid)
    if name == 'Aeon Chronicler':
        assert state.cards[cid].counters['time'] == 1
        state = _resolve_independent_owner_draw(state, 1, cid)
    assert state.cards[cid].counters['time'] == 1 and not state.stack
    assert state.cards[cid].oracle_text == RAW[name]['oracle_text']


def _order_keyword_above_draw(state, seat, cid):
    pending = state.pending_trigger_order
    assert pending and pending.get('phase') != 'targets'
    rows = list(pending['groups'][str(seat)])
    assert sorted(row['effect_key'] for row in rows) == ['draw_cards', 'suspend_cast_trigger']
    assert all(row['source_card_id'] == cid and row['controller'] == seat for row in rows)
    rows.sort(key=lambda row: row['effect_key'] == 'suspend_cast_trigger')
    before = serialize_match_snapshot(state)
    RulesEngine().legal_moves(state, seat)
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_trigger_order', 'trigger_order': [row['_choice_id'] for row in rows]})
    assert state.stack[-1].effect_key == 'suspend_cast_trigger'
    assert serialize_match_snapshot(resume(state)) == serialize_match_snapshot(state)
    return state


def _resolve_independent_owner_draw(state, seat, cid):
    assert len(state.stack) == 1 and not state.pending_mechanic_choice
    item = state.stack[-1]
    assert item.effect_key == 'draw_cards' and item.controller == seat and item.source_card_id == cid
    assert item.payload['__trigger_full_clause'] in RAW['Aeon Chronicler']['oracle_text'].splitlines()
    assert item.payload['amount'] == 1
    hands = {owner: len(player.hand) for owner, player in state.players.items()}
    before = serialize_match_snapshot(state)
    RulesEngine().legal_moves(state, state.priority_player)
    assert serialize_match_snapshot(state) == before
    state = one(resume(state))
    assert len(state.players[seat].hand) == hands[seat] + 1
    assert len(state.players[3-seat].hand) == hands[3-seat]
    assert not state.stack
    assert serialize_match_snapshot(resume(state)) == serialize_match_snapshot(state)
    return state
