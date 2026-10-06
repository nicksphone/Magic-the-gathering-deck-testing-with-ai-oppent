"""Real canonical mana costs, continuation and intent boundaries, both seats."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana_abilities import mana_ability_specs, source_ready
from rules_engine.paid_triggers import (
    RESOLUTION_PAYER, can_pay_optional, resolution_mana_ability_allowed, resolution_mana_payment)
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_paid_optional_triggers import (
    ROWS, evidence, offered, position, private_root, queued, require_pending, reward,
    add, cards, restart)
from tests.test_restricted_mana import CARDS as RESTRICTED
from training.environment import TrainingEnvironment, decode_action
from tests.test_death_cycle_ordering_http_audit import (
    act, drain, frozen, install, offline_client, restore)
from tests.test_paid_optional_triggers import fresh_readonly_restore


DIRECTORY = Path(__file__).parent / 'fixtures/paid_optional_continuation'
RAW = {row['name']: row for row in map(json.loads, (DIRECTORY / 'canonical.jsonl').read_text().splitlines())}
UNSUPPORTED = json.loads((DIRECTORY / 'unsupported-mirari.json').read_text())
RAW[UNSUPPORTED['name']] = UNSUPPORTED
for name, row in {**RESTRICTED, **RAW}.items():
    if name not in cards.ROWS:
        cards.ROWS[name] = row


def pending(seat, name, funding='pool'):
    root, watcher, discarded, secret, land, action = position(seat, name, 'cycle', funding)
    state = queued(root, seat, watcher, action)
    assert not resolve_top_of_stack(state)
    return root, state, watcher, secret, land, require_pending(state, watcher)


def decide(state, seat, accept):
    with cards.unchanged_root(state):
        result = checked_action(state, RulesEngine(), seat, offered(state.pending_trigger_order, accept))
    assert RESOLUTION_PAYER.get() is None
    return restart(result)


def test_additional_raw_provenance_unchanged():
    ledger = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert ledger['source_compressed_sha256'] == '17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13'
    assert hashlib.sha256((DIRECTORY / 'canonical.jsonl').read_bytes()).hexdigest() == ledger['fixture_sha256']
    for entry in ledger['rows']:
        row = RAW[entry['name']]
        assert row['oracle_id'] == entry['oracle_id'] and row['id'] == entry['id']
        assert hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == entry['canonical_row_sha256']
    unsupported = json.loads((DIRECTORY / 'unsupported-provenance.json').read_text())
    assert hashlib.sha256((DIRECTORY / 'unsupported-mirari.json').read_bytes()).hexdigest() == unsupported['fixture_sha256']
    assert UNSUPPORTED['oracle_id'] == unsupported['oracle_id']


@pytest.mark.parametrize('seat', [1, 2])
def test_real_unsupported_paid_copy_stays_explicit_noop_without_free_copy(request, seat):
    root = cards.position(seat)
    source = add(root, 'Mirari', seat)
    spell = add(root, 'Lightning Bolt', seat, Zone.HAND)
    root.players[seat].mana_pool = {'R': 1, 'C': 3}
    with cards.unchanged_root(root):
        state = checked_action(root, RulesEngine(), seat,
                               cards.cast(spell, targets={'target_player': 3-seat}))
    assert len(state.stack) == 2 and state.stack[-1].source_card_id == source.id
    assert state.stack[-1].effect_key == 'noop'
    assert state.stack[-1].payload['__trigger_full_clause'] == UNSUPPORTED['oracle_text'].lower()
    assert resolve_top_of_stack(state)
    assert not state.pending_trigger_order
    assert state.players[seat].mana_pool.get('C', 0) == 3
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == 17 and not state.stack
    assert sum('Unsupported optional trigger payment' in line for line in state.log) == 1
    evidence(request, resolved=serialize_match_snapshot(state), unsupported_body='spell copy')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
def test_paid_choice_never_defaults_to_free_or_implicit_accept(seat, name):
    root, watcher, _, _, _, action = position(seat, name, 'cycle', 'pool')
    root.trigger_order_choice_required = False
    root.trigger_order_choice_players = set()
    state = queued(root, seat, watcher, action)
    assert not resolve_top_of_stack(state)
    assert require_pending(state, watcher)['current_controller'] == seat
    reward(state, seat, name, False)
    assert state.players[seat].mana_pool.get('C', 0) == 1
    assert all(set(move) == {'type', 'stack_id', 'accept'}
               for move in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
@pytest.mark.parametrize('floating', [False, True])
def test_actual_restricted_mana_cannot_pay_trigger(request, seat, name, floating):
    root, watcher, _, secret, _, action = position(seat, name, 'cycle', 'none')
    source = add(root, 'Renowned Weaponsmith', seat)
    if floating:
        with cards.unchanged_root(root):
            root = checked_action(root, RulesEngine(), seat,
                {'type': 'tap_nonland_for_mana', 'card_id': source.id, 'color': 'C'})
    state = queued(root, seat, watcher, action)
    assert not resolve_top_of_stack(state)
    before = serialize_match_snapshot(state)
    with cards.unchanged_root(state):
        assert not can_pay_optional(state, state.stack[-1])
        assert RulesEngine().legal_moves(state, seat) == [offered(state.pending_trigger_order, False)]
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, offered(state.pending_trigger_order, True))
    private_root(state, seat, secret)
    result = decide(state, seat, False)
    reward(result, seat, name, False)
    assert result.cards[source.id].tapped is floating
    assert result.players[seat].mana_pool.get('C', 0) == 2 * int(floating)
    evidence(request, pending=before, resolved=serialize_match_snapshot(result), restricted_floating=floating)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
def test_actual_payment_discard_stages_one_followup_not_free_or_duplicate(request, seat, name, monkeypatch):
    root, watcher, _, _, _, action = position(seat, name, 'cycle', 'none')
    fuel = add(root, 'Raging Goblin', seat, Zone.HAND)
    mana_source = add(root, 'Skirge Familiar', seat)
    state = queued(root, seat, watcher, action)
    assert not resolve_top_of_stack(state)
    original_id = state.stack[-1].id
    tail_id = state.stack[0].id
    from rules_engine import mana_abilities
    from rules_engine import paid_triggers
    actual = mana_abilities.activate_planned_mana_ability
    actual_pay = paid_triggers.pay_optional
    executing = [None]
    observed = []
    def pay(s, item):
        executing[0] = s
        try:
            return actual_pay(s, item)
        finally:
            executing[0] = None
    def activate(s, player, source, index, selector, **kwargs):
        observed.append({'payer': RESOLUTION_PAYER.get(), 'source': source, 'index': index,
                         'controller': player, 'trigger_staging': s.trigger_staging,
                         'actual_replay': s is executing[0]})
        return actual(s, player, source, index, selector, **kwargs)
    monkeypatch.setattr(mana_abilities, 'activate_planned_mana_ability', activate)
    monkeypatch.setattr(paid_triggers, 'pay_optional', pay)
    result = decide(state, seat, True)
    reward(result, seat, name, True)
    assert result.cards[fuel.id].zone == Zone.GRAVEYARD
    assert sum(result.players[seat].mana_pool.values()) == 0
    assert len(result.stack) == 2
    assert result.stack[0].id == tail_id and result.stack[-1].id != original_id
    assert result.stack[-1].source_card_id == watcher.id
    replay = [row for row in observed if row['actual_replay']]
    assert len(replay) == 1
    assert all(row['payer'] == row['controller'] == seat and row['trigger_staging'] for row in replay)
    assert all(row['source'] == mana_source.id for row in observed)
    assert not resolve_top_of_stack(result)
    assert RulesEngine().legal_moves(result, seat) == [offered(result.pending_trigger_order, False)]
    result = decide(result, seat, False)
    assert resolve_top_of_stack(result)
    reward(result, seat, name, True)
    assert not result.stack
    evidence(request, actual_mana=observed, resolved=serialize_match_snapshot(result))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
def test_actual_source_destruction_preserves_payer_and_lki(request, seat, name):
    root, watcher, _, _, _, action = position(seat, name, 'cycle', 'pool')
    removal = add(root, 'Naturalize', 3-seat, Zone.HAND)
    root.players[3-seat].mana_pool = {'G': 1, 'C': 1}
    state = queued(root, seat, watcher, action)
    with cards.unchanged_root(state):
        state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    with cards.unchanged_root(state):
        state = checked_action(state, RulesEngine(), 3-seat, cards.cast(removal, targets={'target_card_id': watcher.id}))
    assert resolve_top_of_stack(state)
    assert state.cards[watcher.id].zone == Zone.GRAVEYARD
    trigger = state.stack[-1]
    assert trigger.controller == trigger.payload['__source_lki']['controller'] == seat
    assert watcher.id in state.players[3-seat].graveyard
    assert not resolve_top_of_stack(state)
    result = decide(restart(state), seat, True)
    reward(result, seat, name, True)
    assert result.players[seat].mana_pool.get('C', 0) == 0
    evidence(request, source_lki=trigger.payload['__source_lki'], resolved=serialize_match_snapshot(result))


@pytest.mark.parametrize('seat', [1, 2])
def test_resolution_permission_uses_actual_printed_ability_and_resets(seat):
    root, _, _, _, _, _ = position(seat, 'Drake Haven', 'cycle', 'pool')
    source = add(root, "Lion's Eye Diamond", seat)
    from rules_engine.oracle_effects import ACTIVATED_ABILITY_RE
    clause = next(ACTIVATED_ABILITY_RE.finditer(source.oracle_text))
    spec = (0, clause[1].strip(), clause[2].strip())
    ordinary = add(root, 'Island', seat)
    ordinary_spec = mana_ability_specs(ordinary, root)[0]
    # LED's discard-all activation is separately unsupported by this engine;
    # this tests its real timing instruction, not an otherwise payable witness.
    assert resolution_mana_ability_allowed(root, source, spec)
    before = serialize_match_snapshot(root)
    with resolution_mana_payment(seat):
        assert not resolution_mana_ability_allowed(root, source, spec)
        assert not source_ready(root, source, spec)
        assert resolution_mana_ability_allowed(root, ordinary, ordinary_spec)
    assert RESOLUTION_PAYER.get() is None
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
@pytest.mark.parametrize('accept', [False, True])
def test_training_exact_optional_intent_no_stripping_or_inferred_payment(seat, name, accept):
    _, state, _, _, _, _ = pending(seat, name)
    env = TrainingEnvironment()
    env.reset('Mono Red Aggro', 'Mono Red Aggro', seed=37)
    state.id = env._state.id
    state.starting_decks = env._state.starting_decks
    env._state = state
    action = offered(state.pending_trigger_order, accept)
    before = env.snapshot()
    selected = env.lookup_intent(action, seat)
    assert decode_action(selected['id']) == action
    for bad in [{k: v for k, v in action.items() if k != 'accept'},
                {**action, 'accept': None}, {**action, 'accept': 'pay'},
                {**action, 'cost_text': '{1}'}, {**action, 'choice_id': 'pay'}]:
        with pytest.raises(ActionRejected):
            env.lookup_intent(bad, seat)
        assert env.snapshot() == before
    first, second = TrainingEnvironment(), TrainingEnvironment()
    first.restore(before)
    second.restore(before)
    assert first.step(selected['id'], seat) == second.step(action, seat)
    assert first.snapshot() == second.snapshot()
    reward(first._state, seat, name, accept)
    assert env.snapshot() == before


def lunar_position(seat):
    root = cards.position(seat)
    source = add(root, 'Lunar Mystic', seat)
    source.owner = 3-seat
    spell = add(root, 'Lightning Bolt', seat, Zone.HAND)
    dredger = add(root, 'Life from the Loam', seat, Zone.GRAVEYARD)
    for _ in range(7):
        add(root, 'Island', seat, Zone.LIBRARY)
    root.players[seat].mana_pool = {'R': 1, 'C': 1}
    root.trigger_order_choice_required = True
    root.trigger_order_choice_players = {seat}
    root.mechanic_choice_players = {seat}
    return root, source, spell, dredger


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_draw_reward_pauses_and_restores_without_double_payment(request, seat):
    root, source, spell, dredger = lunar_position(seat)
    with cards.unchanged_root(root):
        state = checked_action(root, RulesEngine(), seat, cards.cast(spell, targets={'target_player': 3-seat}))
    assert len(state.stack) == 2
    assert not resolve_top_of_stack(state)
    result = decide(restart(state), seat, True)
    assert result.pending_mechanic_choice['kind'] == 'draw'
    assert result.pending_mechanic_choice['resolving_item']['source_card_id'] == source.id
    assert result.pending_mechanic_choice['resolving_item']['payload']['__optional_payment_paid']['mana_spent'] == 1
    assert sum(result.players[seat].mana_pool.values()) == 0
    before = serialize_match_snapshot(result)
    with cards.unchanged_root(result):
        result = checked_action(result, RulesEngine(), seat, {'type': 'choose_mechanic', 'choice_id': dredger.id})
    assert not result.pending_mechanic_choice and len(result.stack) == 1
    assert dredger.id in result.players[seat].hand
    assert sum(result.players[seat].mana_pool.values()) == 0
    assert resolve_top_of_stack(result)
    assert result.players[3-seat].life == 17 and not result.stack
    evidence(request, reward_pending=before, resolved=serialize_match_snapshot(result))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_paid_draw_reward_continuation_restore(request, offline_client, seat):
    import main
    root, source, spell, dredger = lunar_position(seat)
    secret = add(root, 'Swamp', 3-seat, Zone.HAND)
    match = install(root, request, seat, private=True)
    assert act(offline_client, match, seat, cards.cast(spell, targets={'target_player': 3-seat})).status_code == 200
    for _ in range(8):
        match = restore(root.id)
        if match.state.pending_trigger_order:
            break
        actor = match.state.priority_player
        response = (offline_client.post('/matches/' + root.id + '/autoplay?ticks=1')
                    if match.controllers[actor] == 'ai' else
                    act(offline_client, match, actor, {'type': 'pass_priority'}))
        assert response.status_code == 200
    else:
        raise AssertionError('Paid draw optional prompt did not appear')
    choice = require_pending(match.state, source)
    fresh_readonly_restore(match)
    assert act(offline_client, match, seat, offered(choice, True)).status_code == 200
    match = restore(root.id)
    assert match.state.pending_mechanic_choice['kind'] == 'draw'
    assert match.state.pending_mechanic_choice['resolving_item']['payload']['__optional_payment_paid']['mana_spent'] == 1
    assert sum(match.state.players[seat].mana_pool.values()) == 0
    fresh_readonly_restore(match)
    private_root(match.state, seat, secret)
    before = frozen(match)
    for actor, action in [(3-seat, {'type': 'choose_mechanic', 'choice_id': dredger.id}),
                           (seat, offered(choice, True))]:
        response = act(offline_client, match, actor, action)
        assert response.status_code in (403, 422)
        assert frozen(main.ACTIVE_MATCHES[root.id]) == before
    assert act(offline_client, match, seat, {'type': 'choose_mechanic', 'choice_id': dredger.id}).status_code == 200
    match = drain(offline_client, root.id)
    assert not match.state.pending_mechanic_choice and not match.state.stack
    assert dredger.id in match.state.players[seat].hand
    assert match.state.players[3-seat].life == 17
    assert sum(match.state.players[seat].mana_pool.values()) == 0
    fresh_readonly_restore(match)
    evidence(request, resolved=serialize_match_snapshot(match.state), reward_continuation_ro_equal=True,
             physical_payment_count=1, paid_declared_cost='{1}')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
@pytest.mark.parametrize('funding', ['none', 'restricted'])
def test_actual_http_unavailable_accept_is_atomic_and_decline_restores(request, offline_client, seat, name, funding):
    import main
    root, watcher, _, secret, _, action = position(seat, name, 'cycle', 'none')
    if funding == 'restricted':
        source = add(root, 'Renowned Weaponsmith', seat)
        with cards.unchanged_root(root):
            root = checked_action(root, RulesEngine(), seat,
                {'type': 'tap_nonland_for_mana', 'card_id': source.id, 'color': 'C'})
    match = install(root, request, seat, private=True)
    assert act(offline_client, match, seat, action).status_code == 200
    for _ in range(8):
        match = restore(root.id)
        if match.state.pending_trigger_order:
            break
        actor = match.state.priority_player
        response = (offline_client.post('/matches/' + root.id + '/autoplay?ticks=1')
                    if match.controllers[actor] == 'ai' else
                    act(offline_client, match, actor, {'type': 'pass_priority'}))
        assert response.status_code == 200
    else:
        raise AssertionError('Actual optional prompt did not appear')
    choice = require_pending(match.state, watcher)
    fresh_readonly_restore(match)
    private_root(match.state, seat, secret)
    public_moves = offline_client.get('/matches/' + root.id + '/legal-moves?player_id=' + str(seat))
    assert public_moves.status_code == 200
    assert public_moves.json()['moves'] == [offered(choice, False)]
    before = frozen(match)
    for actor, bad in [(seat, offered(choice, True)), (3-seat, offered(choice, False)),
                       (seat, {**offered(choice, False), 'stack_id': 'stale'})]:
        response = act(offline_client, match, actor, bad)
        assert response.status_code in (403, 422)
        assert frozen(main.ACTIVE_MATCHES[root.id]) == before
    response = act(offline_client, match, seat, offered(choice, False))
    assert response.status_code == 200
    match = drain(offline_client, root.id)
    fresh_readonly_restore(match)
    reward(match.state, seat, name, False)
    assert match.state.players[seat].mana_pool.get('C', 0) == 2 * int(funding == 'restricted')
    evidence(request, resolved=serialize_match_snapshot(match.state), funding=funding,
             atomic_rules_controller_sql_equal=True, fresh_readonly_restore_equal=True)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_interrupted_real_mana_replay_rolls_back_everything(request, offline_client, seat, monkeypatch):
    import main
    from rules_engine import mana
    root, state, _, _, land, choice = pending(seat, 'Drake Haven', 'land')
    match = install(state, request, seat)
    before = frozen(match)
    actual = mana.auto_pay_cost
    observed = []
    def interrupted(s, player, cost, **kwargs):
        result = actual(s, player, cost, **kwargs)
        if kwargs.get('payment_kind') == 'resolution':
            assert result and s.cards[land.id].tapped
            assert sum(s.players[seat].mana_pool.values()) == 0
            observed.append(serialize_match_snapshot(s))
            return False  # Failure injection after real native payment, not fake card execution.
        return result
    monkeypatch.setattr(mana, 'auto_pay_cost', interrupted)
    response = act(offline_client, match, seat, offered(choice, True))
    assert response.status_code == 422
    assert len(observed) == 1
    assert frozen(main.ACTIVE_MATCHES[state.id]) == before
    assert not main.ACTIVE_MATCHES[state.id].state.cards[land.id].tapped
    assert RESOLUTION_PAYER.get() is None
    restored = restore(state.id)
    fresh_readonly_restore(restored)
    reward(restored.state, seat, 'Drake Haven', False)
    evidence(request, simulated_interrupt_after_real_payment=observed,
             unchanged_authoritative=serialize_match_snapshot(restored.state),
             full_rules_controller_sql_rollback=True, natural_failure_claim=False)
