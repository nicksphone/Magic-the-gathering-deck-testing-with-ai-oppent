"""Real resolved queues, visit ordering and restoration, not parser certificates."""
from copy import deepcopy
import hashlib
import json
import pickle

import pytest

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.turn_scheduler import instruction
from tests.desired_extra_sequence_contracts import next_upkeep
from tests.queued_sequence_support import FIXTURE, RAW, add, act, cast, position, resume, facts


def test_canonical_intake_and_bounded_full_schemas():
    proof = json.loads((FIXTURE / 'provenance.json').read_text())
    assert proof['facts_modified'] is False and proof['intake_before_tests']
    assert hashlib.sha256((FIXTURE / 'canonical.json').read_bytes()).hexdigest() == proof['canonical_sha256']
    for name, row in RAW.items():
        assert proof['rows'][name]['id'] == row['id']
        assert proof['rows'][name]['raw_sha256'] == hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert instruction(RAW['Temporal Manipulation']['oracle_text']) == 'controller'
    assert instruction(RAW['Temporal Mastery']['oracle_text']) is None
    assert instruction(RAW['Relentless Assault']['oracle_text']) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_controller_turn_and_extra_turn_does_not_consume_normal_cursor(seat):
    state = position(seat)
    source = add(state, 'Temporal Manipulation', seat)
    original = pickle.dumps(state)
    original_state = state
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source.id})
    assert pickle.dumps(original_state) == original
    assert state.spells_cast_this_turn[seat] == 1
    assert resolve_top_of_stack(state)
    state = resume(state)
    next_upkeep(state)
    assert state.active_player == seat and state.normal_turn_successor == 3 - seat
    RulesEngine().next_step(state)
    RulesEngine().next_step(state)
    state.players[seat].mana_pool = {'U': 20, 'C': 20}
    state, _ = cast(state, 'Time Warp', seat, {'target_player': 3 - seat})
    assert resolve_top_of_stack(state)
    next_upkeep(state)
    assert state.active_player == 3 - seat
    next_upkeep(state)
    assert state.active_player == 3 - seat
    next_upkeep(state)
    assert state.active_player == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_real_countered_spell_or_ability_creates_no_queue(seat):
    for ability in (False, True):
        state = position(seat)
        if ability:
            source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
            state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
        else:
            state, _ = cast(state, 'Time Warp', seat, {'target_player': seat})
        target = state.stack[-1].id
        state.priority_player = 3 - seat
        state, _ = cast(state, 'Stifle' if ability else 'Counterspell', 3 - seat, {'target_stack_id': target})
        assert resolve_top_of_stack(state) and not state.stack
        assert not state.extra_turns and not any(row['group'] for row in state.phase_plan)
        next_upkeep(state)
        assert state.active_player == 3 - seat


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_spell_copy_resolves_twice_but_is_not_cast(seat):
    state = position(seat)
    state.mechanic_choice_players = {seat}
    state, _ = cast(state, 'Time Warp', seat, {'target_player': seat})
    target = state.stack[-1].id
    state.priority_player = seat
    state, _ = cast(state, 'Twincast', seat, {'target_stack_id': target})
    resolved = resolve_top_of_stack(state)
    if state.pending_mechanic_choice:
        assert not resolved
        choices = RulesEngine().legal_moves(state, seat)
        choice = dict(choices[0])
        choice['card_ids'] = ['keep']
        state = act(state, seat, choice)
    else:
        assert resolved
    assert state.stack[-1].payload['__stack_copy_kind'] == 'spell'
    assert resolve_top_of_stack(state) and resolve_top_of_stack(state)
    assert state.spells_cast_this_turn[seat] == 2 and len(state.extra_turns) == 2
    assert state.extra_turns[0]['ordinal'] < state.extra_turns[1]['ordinal']
    for expected in (seat, seat, 3 - seat):
        next_upkeep(state)
        assert state.active_player == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('step', [Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN])
def test_newest_whole_group_first_original_plan_and_nested_extra_main(seat, step):
    state = position(seat, step)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    for _ in range(2):
        state.priority_player = seat
        state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
        assert resolve_top_of_stack(state)
    rows = state.phase_plan
    extras = [(r['kind'], r['group']) for r in rows if r['group']]
    assert [r[0] for r in extras] == ['combat', 'postcombat_main'] * 2
    assert extras[0][1] == extras[1][1] > extras[2][1] == extras[3][1]
    original_visits = [r['visit'] for r in rows if r['group'] == 0]
    assert len(original_visits) == 6
    state = resume(state)
    for _ in range(6):
        RulesEngine().next_step(state)
    assert state.step == Step.POSTCOMBAT_MAIN
    state.players[seat].mana_pool = {'R': 2, 'C': 3}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
    assert resolve_top_of_stack(state)
    nested = state.phase_plan[state.phase_cursor + 1:state.phase_cursor + 3]
    assert [r['kind'] for r in nested] == ['combat', 'postcombat_main']
    assert nested[0]['group'] > extras[0][1]
    assert [r['visit'] for r in state.phase_plan if not r['group']] == original_visits
    visits = []
    while state.turn == 5:
        current = state.phase_plan[state.phase_cursor]
        if not visits or visits[-1] != current['visit']:
            visits.append(current['visit'])
        RulesEngine().next_step(state)
    assert len(visits) == len(set(visits))
    assert state.active_player == 3 - seat and not any(r['group'] for r in state.phase_plan)


@pytest.mark.parametrize('seat', [1, 2])
def test_untap_stun_effective_control_sickness_and_source_departure(seat):
    state = position(seat)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    own = add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    stun = add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    other = add(state, 'Grizzly Bears', 3 - seat, Zone.BATTLEFIELD)
    land = add(state, 'Island', seat, Zone.BATTLEFIELD)
    for c in (own, stun, other, land):
        c.tapped = True
    stun.counters['stun'] = 1
    old = facts(state)
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
    assert old['cards'][own.id]['tapped']
    # Independent source departure after payment cannot cancel its stack object.
    state.players[seat].battlefield.remove(source.id)
    state.cards[source.id].move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(source.id)
    assert resolve_top_of_stack(state)
    assert not state.cards[own.id].tapped and state.cards[own.id].summoning_sick
    assert state.cards[stun.id].tapped and not state.cards[stun.id].counters
    assert state.cards[other.id].tapped and state.cards[land.id].tapped
    next_upkeep(state)
    assert state.cards[own.id].summoning_sick
    next_upkeep(state)
    assert not state.cards[own.id].summoning_sick


@pytest.mark.parametrize('seat', [1, 2])
def test_cleanup_real_discard_pending_and_repeat_holds_queue(seat):
    state = position(seat)
    state, _ = cast(state, 'Time Warp', seat, {'target_player': seat})
    assert resolve_top_of_stack(state)
    for _ in range(8):
        add(state, 'Island', seat)
    state.mechanic_choice_players = {seat}
    engine = RulesEngine()
    while state.step != Step.CLEANUP:
        engine.next_step(state)
    assert state.pending_mechanic_choice['kind'] == 'cleanup_discard'
    state = resume(state)
    old = facts(state)
    engine.next_step(state)
    assert facts(state) == old and len(state.extra_turns) == 1
    choice = dict(RulesEngine().legal_moves(state, seat)[0])
    choice['card_ids'] = state.pending_mechanic_choice['options'][:state.pending_mechanic_choice['count']]
    state = act(state, seat, choice)
    assert not state.pending_mechanic_choice and len(state.players[seat].hand) == 7
    # Existing repeat-cleanup state must be handled before consuming a turn.
    state.cleanup_repeat_required = True
    engine.next_step(state)
    assert state.turn == 5 and len(state.extra_turns) == 1
    engine.next_step(state)
    assert state.turn == 6 and state.active_player == seat and not state.extra_turns


@pytest.mark.parametrize('seat', [1, 2])
def test_cast_history_and_day_night_only_reset_at_real_turn(seat):
    state = position(seat)
    state.day_night = 'night'
    state, _ = cast(state, 'Time Warp', seat, {'target_player': seat})
    assert resolve_top_of_stack(state)
    state.priority_player = seat
    state, _ = cast(state, 'Temporal Manipulation', seat)
    assert resolve_top_of_stack(state)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    state.priority_player = seat
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
    assert resolve_top_of_stack(state)
    state.spells_cast_this_turn[3 - seat] = 9
    for _ in range(6):
        RulesEngine().next_step(state)
    assert state.spells_cast_this_turn == {seat: 2, 3 - seat: 9}
    assert state.day_night == 'night'
    next_upkeep(state)
    assert state.spells_cast_this_turn == {1: 0, 2: 0}
    assert state.spells_cast_last_turn == 2 and state.day_night == 'day'
    next_upkeep(state)
    assert state.day_night == 'night' and state.spells_cast_last_turn == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_order_invariance_and_read_root_purity(seat):
    state = position(seat)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    warp = add(state, 'Time Warp', seat)
    original = pickle.dumps(state)
    variant = deepcopy(state)
    variant.players[1].library.reverse()
    variant.players[2].library.reverse()
    schedules = []
    for root in (state, variant):
        before = pickle.dumps(root)
        moves = RulesEngine().legal_moves(root, seat)
        assert pickle.dumps(root) == before
        candidate = act(root, seat, {'type': 'cast_spell', 'card_id': warp.id, 'targets': {'target_player': seat}})
        assert pickle.dumps(root) == before and resolve_top_of_stack(candidate)
        candidate.priority_player = seat
        candidate = act(candidate, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
        assert resolve_top_of_stack(candidate)
        schedules.append(serialize_match_snapshot(candidate)['scheduler'])
    assert schedules[0] == schedules[1]
    assert pickle.dumps(state) == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['version', 'recipient', 'ordinal', 'cursor', 'visit', 'group', 'missing', 'null', 'boolean-version', 'boolean-successor', 'kind-list', 'broken-pair'])
def test_malformed_persistent_schedule_rejects_not_drops(seat, bad):
    state = position(seat)
    state, _ = cast(state, 'Time Warp', seat, {'target_player': seat})
    assert resolve_top_of_stack(state)
    payload = serialize_match_snapshot(state)
    rows = payload['scheduler']
    if bad == 'version': rows['version'] = 2
    if bad == 'recipient': rows['extra_turns'][0]['recipient'] = 3
    if bad == 'ordinal': rows['extra_turns'][0]['ordinal'] = rows['next_schedule_ordinal']
    if bad == 'cursor': rows['phase_cursor'] = 100
    if bad == 'visit': rows['phase_plan'][0]['visit'] = rows['phase_plan'][1]['visit']
    if bad == 'group': rows['phase_plan'][2]['group'] = 1
    if bad == 'missing': rows['phase_plan'] = []
    if bad == 'null': payload['scheduler'] = None
    if bad == 'boolean-version': rows['version'] = True
    if bad == 'boolean-successor': rows['normal_turn_successor'] = True
    if bad == 'kind-list': rows['phase_plan'][0]['kind'] = []
    if bad == 'broken-pair':
        rows['phase_plan'][2]['group'] = 1
        rows['phase_plan'][3] = None
    with pytest.raises(ValueError): deserialize_match_snapshot(payload)


def test_legacy_snapshot_and_pure_uninitialized_snapshot():
    state = position(2)
    old = pickle.dumps(state)
    payload = serialize_match_snapshot(state)
    assert pickle.dumps(state) == old
    del payload['scheduler']
    restored = deserialize_match_snapshot(payload)
    assert not restored.phase_plan and restored.normal_turn_successor is None
    next_upkeep(restored)
    assert restored.active_player == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_real_copied_ability_is_one_more_group_not_one_more_cast(seat):
    state = position(seat)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    copier = add(state, 'Lithoform Engine', seat, Zone.BATTLEFIELD)
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
    target = state.stack[-1].id
    state.priority_player = seat
    state = act(state, seat, {'type': 'activate_ability', 'card_id': copier.id,
                            'ability_index': 0, 'targets': {'target_stack_id': target}})
    assert resolve_top_of_stack(state)
    assert state.stack[-1].payload['__stack_copy_kind'] == 'activated'
    assert resolve_top_of_stack(state) and resolve_top_of_stack(state)
    assert len([r for r in state.phase_plan if r['kind'] == 'combat']) == 3
    assert state.spells_cast_this_turn == {1: 0, 2: 0}
    assert state.cards[copier.id].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_first_strike_and_attack_history_reset_per_combat_not_per_turn(seat):
    state = position(seat, Step.POSTCOMBAT_MAIN)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    knight = add(state, 'Youthful Knight', seat, Zone.BATTLEFIELD)
    state.cards[knight.id].entered_turn = 4
    state.cards[knight.id].summoning_sick = False
    for combat_number in (1, 2):
        state.players[seat].mana_pool = {'R': 2, 'C': 3}
        state.priority_player = seat
        state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
        assert resolve_top_of_stack(state)
        RulesEngine().next_step(state)
        assert state.step == Step.BEGIN_COMBAT
        assert state.combat_damage_stage == 'none' and not state.first_strike_damage_ids
        RulesEngine().next_step(state)
        assert state.combat_damage_stage == 'none' and not state.first_strike_damage_ids
        state = act(state, seat, {'type': 'attack', 'attackers': [knight.id]})
        RulesEngine().next_step(state)
        state = act(state, 3 - seat, {'type': 'block', 'blocks': {}})
        RulesEngine().next_step(state)
        assert state.step == Step.COMBAT_DAMAGE and state.combat_damage_stage == 'first'
        assert state.players[3 - seat].life == 20 - 2 * combat_number
        state = resume(state)
        RulesEngine().next_step(state)
        assert state.step == Step.COMBAT_DAMAGE and state.combat_damage_stage == 'regular'
        assert state.players[3 - seat].life == 20 - 2 * combat_number
        RulesEngine().next_step(state)
        RulesEngine().next_step(state)
        assert state.step == Step.POSTCOMBAT_MAIN and not state.attackers and not state.blocks
        assert state.declared_attackers_this_turn[seat] == combat_number
        assert state.turn == 5


@pytest.mark.parametrize('seat', [1, 2])
def test_foretell_cannot_use_extra_phase_as_later_turn_but_can_use_extra_turn(seat):
    state = position(seat)
    card = add(state, 'Behold the Multiverse', seat)
    state = act(state, seat, {'type': 'foretell', 'card_id': card.id})
    state, _ = cast(state, 'Time Warp', seat, {'target_player': seat})
    assert resolve_top_of_stack(state)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    state.priority_player = seat
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
    assert resolve_top_of_stack(state)
    for _ in range(6): RulesEngine().next_step(state)
    assert state.turn == 5
    state.players[seat].mana_pool = {'U': 20, 'C': 20}
    assert not any(m.get('card_id') == card.id and m['type'] == 'cast_spell'
                   for m in RulesEngine().legal_moves(state, seat))
    next_upkeep(state)
    state.players[seat].mana_pool = {'U': 1, 'C': 1}
    assert any(m.get('card_id') == card.id and m['type'] == 'cast_spell'
               for m in RulesEngine().legal_moves(state, seat))
    state = act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
                             'cost_option_id': 'foretell_0', 'from_exile': True})
    assert state.cards[card.id].was_foretold and state.spells_cast_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_suspend_actual_extra_upkeep_once_not_extra_main(seat):
    state = position(seat)
    card = add(state, 'Ancestral Vision', seat)
    state = act(state, seat, {'type': 'suspend', 'card_id': card.id})
    state, _ = cast(state, 'Time Warp', seat, {'target_player': seat})
    assert resolve_top_of_stack(state)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    state.priority_player = seat
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
    assert resolve_top_of_stack(state)
    for _ in range(6): RulesEngine().next_step(state)
    assert state.cards[card.id].counters['time'] == 4 and not state.stack
    next_upkeep(state)
    assert len(state.stack) == 1 and state.stack[-1].effect_key == 'suspend_upkeep'
    state = resume(state)
    assert resolve_top_of_stack(state)
    assert state.cards[card.id].counters['time'] == 3
    RulesEngine().next_step(state)
    assert state.step == Step.DRAW and state.cards[card.id].counters['time'] == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_real_nth_cast_trigger_survives_extra_main_then_extra_turn_resets(seat):
    state = position(seat)
    spirit = add(state, 'Clarion Spirit', seat, Zone.BATTLEFIELD)
    state, _ = cast(state, 'Time Warp', seat, {'target_player': seat})
    assert resolve_top_of_stack(state)
    source = add(state, 'Aggravated Assault', seat, Zone.BATTLEFIELD)
    state.priority_player = seat
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})
    assert resolve_top_of_stack(state)
    for _ in range(6): RulesEngine().next_step(state)
    state.players[seat].mana_pool = {'U': 20, 'C': 20}
    state, _ = cast(state, 'Temporal Manipulation', seat)
    assert state.stack[-1].source_card_id == spirit.id
    assert resolve_top_of_stack(state)
    tokens = [c for c in state.cards.values() if c.is_token]
    assert len(tokens) == 1 and tokens[0].power == tokens[0].toughness == 1
    assert 'flying' in tokens[0].keywords
    assert resolve_top_of_stack(state)
    next_upkeep(state)
    assert state.spells_cast_this_turn == {1: 0, 2: 0}
