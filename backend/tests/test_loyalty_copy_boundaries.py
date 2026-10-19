"""Native paid-copy target receipts and non-target copied Aura entry boundaries."""
import json
from copy import deepcopy

import pytest

from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.optional_reveal import public_choice
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_compleated_loyalty_full import (
    FIX, SEED, RAW, cast_walker, raw_card, activate, act, settle, reject)
from tests.test_loyalty_graveyard_copy_exact import await_attachment

AURA = next(row for row in json.loads((FIX.parent / 'aura_costs.json').read_bytes())
            if row['name'] == 'Pacifism')
ENGINE = json.loads((FIX.parent / 'archangel_pair/lithoform-engine.json').read_bytes())


def aura_position(seat, *, doubling=False, creatures=2):
    from tests.test_ward_resolution import CARDS
    state, cid = cast_walker(seat, doubling=doubling)
    state.mechanic_choice_players = {seat}
    targets = [raw_card(state, CARDS['Tolarian Terror'] if index == 0 else SEED['Llanowar Elves'],
                        3-seat, Zone.BATTLEFIELD).id for index in range(creatures)]
    for target in targets:
        add_keyword_effect(state, target, ['hexproof'])
    original = raw_card(state, AURA, seat, Zone.GRAVEYARD)
    return activate(state, seat, cid, 1, {'target_card_id': original.id, 'x_value': 2}), original.id, targets


def aura_tokens(state):
    return [card for card in state.cards.values() if card.is_token
            and card.zone == Zone.BATTLEFIELD and card.name == AURA['name']]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('doubling', [False, True])
def test_copied_aura_full_snapshot_cold_replay_independent_replacement_choices(seat, doubling):
    state, original, targets = aura_position(seat, doubling=doubling)
    state = await_attachment(state)
    assert state.cards[original].zone == Zone.EXILE
    assert not aura_tokens(state)
    assert set(state.pending_mechanic_choice['options']) == set(targets)
    snapshot = json.loads(json.dumps(serialize_match_snapshot(state)))
    finals = []
    for _ in range(2):
        replay = deserialize_match_snapshot(deepcopy(snapshot))
        for index in range(2 if doubling else 1):
            pending = replay.pending_mechanic_choice
            assert pending and pending['player_id'] == seat
            assert not aura_tokens(replay), 'Entry batch waits for every independent attachment'
            assert pending['entry_card_id'] not in replay.cards
            replay = act(replay, seat, {'type': 'choose_mechanic', 'choice_id': targets[index]})
        replay = settle(replay)
        tokens = aura_tokens(replay)
        assert len(tokens) == (2 if doubling else 1)
        assert {token.attached_to for token in tokens} == set(targets[:len(tokens)])
        assert len({token.id for token in tokens}) == len(tokens)
        for token in tokens:
            assert token.owner == token.controller == seat and token.summoning_sick
            assert token.oracle_text == AURA['oracle_text'] and not token.counters
        assert replay.cards[original].zone == Zone.EXILE and not replay.stack
        assert replay.players[seat].life == 20 and not any(replay.players[seat].mana_pool.values())
        finals.append(serialize_match_snapshot(replay))
    assert finals[0] == finals[1]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['actor', 'missing', 'zone', 'incarnation', 'restriction'])
def test_copied_aura_invalid_stale_attachment_rejects_entire_root(seat, bad):
    state, original, targets = aura_position(seat)
    state = await_attachment(state)
    target = targets[0]
    if bad in {'zone', 'incarnation'}:
        resolve_effect(state, seat, 'exile', {'target_card_id': target})
        if bad == 'incarnation':
            state.players[3-seat].exile.remove(target)
            state.cards[target].move_to_zone(Zone.BATTLEFIELD)
            state.players[3-seat].battlefield.append(target)
    elif bad == 'restriction':
        # Controlled runtime type-loss seam, not a claimed paid transformation.
        state.cards[target].types = ['Artifact']
    reject(state, 3-seat if bad == 'actor' else seat, {'type': 'choose_mechanic',
           'choice_id': 'absent' if bad == 'missing' else target})
    assert state.cards[original].zone == Zone.EXILE and not aura_tokens(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_copied_aura_queries_pure_and_payload_private(seat):
    state, _, targets = aura_position(seat)
    state = await_attachment(state)
    secret = raw_card(state, SEED['Lightning Bolt'], seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    for _ in range(2):
        actor = RulesEngine().legal_moves(state, seat)
        assert set(actor[0]['options']) == set(targets)
        assert RulesEngine().legal_moves(state, 3-seat) == []
        public = public_choice(state.pending_mechanic_choice)
        for view in [actor, public]:
            encoded = json.dumps(view)
            assert secret.id not in encoded and 'effect_payload' not in encoded
            assert '__entry_candidates' not in encoded and 'option_references' not in encoded
        assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('doubling', [False, True])
def test_copied_aura_zero_legal_attachment_has_no_entry_or_entry_event(seat, doubling, monkeypatch):
    from rules_engine import events
    from effects import handlers
    batches = []
    original_emit = events.emit_event_batch
    def observe(state, event, payload):
        if event == 'enters_battlefield':
            batches.extend(payload)
        return original_emit(state, event, payload)
    state, original, _ = aura_position(seat, doubling=doubling, creatures=0)
    monkeypatch.setattr(events, 'emit_event_batch', observe)
    monkeypatch.setattr(handlers, 'emit_event_batch', observe)
    state = settle(state)
    assert state.cards[original].zone == Zone.EXILE
    assert not aura_tokens(state) and not batches
    assert not state.pending_mechanic_choice and not state.pending_replacement_choice


def copied_freeze(seat, *, shape='singular'):
    state, cid = cast_walker(seat)
    state.mechanic_choice_players = {seat}
    first = raw_card(state, SEED['Llanowar Elves'], seat, Zone.BATTLEFIELD)
    second = raw_card(state, SEED['Llanowar Elves'], 3-seat, Zone.BATTLEFIELD)
    targets = {'target_card_id': first.id} if shape == 'singular' else {'target_card_ids': [first.id] if shape == 'list' else []}
    state = activate(state, seat, cid, 0, targets)
    engine = raw_card(state, ENGINE, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 2}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine.id,
        'ability_index': 0, 'targets': {'target_stack_id': state.stack[-1].id}})
    return state, cid, first.id, second.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('shape', ['singular', 'list'])
@pytest.mark.parametrize('keep', [False, True])
def test_copy_keeps_stale_receipt_or_explicit_same_id_refreshes_only_changed_slot(seat, shape, keep):
    state, cid, first, _ = copied_freeze(seat, shape=shape)
    resolve_effect(state, seat, 'exile', {'target_card_id': first})
    state.players[seat].exile.remove(first)
    state.cards[first].move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(first)
    assert not resolve_top_of_stack(state), 'Native copy resolution pauses for target selection'
    copied = state.stack[-1]
    before_payload = deepcopy(copied.payload)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    chosen = 'keep' if keep else 'target_card_id:' + first
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [chosen]})
    copied = state.stack[-1]
    announced = copied.payload['__announced_targets']
    assert announced == before_payload['__announced_targets']
    assert copied.payload['x_value'] == before_payload['x_value']
    if keep:
        assert copied.payload['__announced_target_references'] == before_payload['__announced_target_references']
    else:
        assert copied.payload['__announced_target_references'] != before_payload['__announced_target_references']
    assert state.cards[cid].loyalty == 6
    state = settle(state)
    assert state.cards[first].tapped is (not keep)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['actor', 'hexproof', 'protection', 'zone'])
def test_copied_loyalty_retarget_current_legality_rejections_pure(seat, bad):
    state, _, _, second = copied_freeze(seat)
    assert not resolve_top_of_stack(state), 'Native copy resolution pauses for target selection'
    assert 'target_card_id:' + second in state.pending_mechanic_choice['options']
    if bad in {'hexproof', 'protection'}:
        add_keyword_effect(state, second, ['hexproof' if bad == 'hexproof' else 'protection from blue'])
    elif bad == 'zone':
        resolve_effect(state, seat, 'exile', {'target_card_id': second})
    reject(state, 3-seat if bad == 'actor' else seat, {'type': 'choose_mechanic',
        'card_ids': ['target_card_id:' + second]})


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_target_copy_never_adds_targets(seat):
    state, cid, first, second = copied_freeze(seat, shape='zero')
    assert resolve_top_of_stack(state)
    assert not state.pending_mechanic_choice
    assert state.stack[-1].payload['__announced_targets']['target_card_ids'] == []
    state = settle(state)
    assert not state.cards[first].tapped and not state.cards[second].tapped
    assert state.cards[cid].loyalty == 6


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_to_zero_source_copy_retains_x_without_repayment_or_source_life_inheritance(seat):
    state, cid = cast_walker(seat)
    state.mechanic_choice_players = {seat}
    first = raw_card(state, RAW, seat, Zone.GRAVEYARD)
    second = raw_card(state, RAW, seat, Zone.GRAVEYARD)
    wrong = raw_card(state, SEED['Llanowar Elves'], seat, Zone.GRAVEYARD)
    state = activate(state, seat, cid, 1, {'target_card_id': first.id, 'x_value': 5})
    assert state.cards[cid].zone == Zone.GRAVEYARD
    original_id = state.stack[-1].id
    original_payload = deepcopy(state.stack[-1].payload)
    engine = raw_card(state, ENGINE, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 2}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine.id,
        'ability_index': 0, 'targets': {'target_stack_id': original_id}})
    assert not resolve_top_of_stack(state)
    assert 'target_card_id:' + second.id in state.pending_mechanic_choice['options']
    assert 'target_card_id:' + wrong.id not in state.pending_mechanic_choice['options']
    reject(state, seat, {'type': 'choose_mechanic', 'card_ids': ['target_card_id:' + wrong.id]})
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['target_card_id:' + second.id]})
    copied = state.stack[-1]
    assert copied.payload['x_value'] == copied.payload['effects'][0]['payload']['x_value'] == 5
    assert next(item for item in state.stack if item.id == original_id).payload == original_payload
    assert resolve_top_of_stack(state)
    token, = [card for card in state.cards.values() if card.is_token and card.zone == Zone.BATTLEFIELD]
    assert token.loyalty == 5 and token.oracle_text == RAW['oracle_text']
    assert state.cards[second.id].zone == Zone.EXILE and state.cards[first.id].zone == Zone.GRAVEYARD
    assert state.cards[cid].zone == Zone.GRAVEYARD and state.players[seat].life == 20
    assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_retarget_publishes_native_ward_once_then_decline_counters_only_copy(seat):
    from tests.test_ward_resolution import CARDS
    state, _, first, _ = copied_freeze(seat)
    warded = raw_card(state, CARDS['Tolarian Terror'], 3-seat, Zone.BATTLEFIELD)
    assert not resolve_top_of_stack(state)
    copied_id = state.stack[-1].id
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['target_card_id:' + warded.id]})
    ward_frames = [item for item in state.stack if item.effect_key == 'ward_payment']
    assert len(ward_frames) == 1
    assert ward_frames[0].payload['target_stack_id'] == copied_id
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'ward_payment'
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert not any(item.id == copied_id for item in state.stack)
    state = settle(state)
    assert state.cards[first].tapped and not state.cards[warded.id].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_copied_aura_entry_events_see_attached_batch_once(seat, monkeypatch):
    from rules_engine import events
    from effects import handlers
    state, original, targets = aura_position(seat, doubling=True)
    records = []
    native = events.emit_event_batch
    def observe(state, event, payload):
        if event == 'enters_battlefield':
            records.append([(row['card_id'], state.cards[row['card_id']].attached_to) for row in payload])
        return native(state, event, payload)
    monkeypatch.setattr(events, 'emit_event_batch', observe)
    monkeypatch.setattr(handlers, 'emit_event_batch', observe)
    state = await_attachment(state)
    state = act(state, seat, {'type': 'choose_mechanic', 'choice_id': targets[0]})
    assert not records and not aura_tokens(state)
    state = settle(act(state, seat, {'type': 'choose_mechanic', 'choice_id': targets[1]}))
    assert len(records) == 1 and len(records[0]) == 2
    assert {target for _, target in records[0]} == set(targets)
    assert state.cards[original].zone == Zone.EXILE
    reject(state, seat, {'type': 'choose_mechanic', 'choice_id': targets[0]})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('branch', ['G', 'P'])
def test_paid_copy_of_actual_departed_walker_uses_printed_not_live_loyalty(seat, branch):
    from tests.test_compleated_loyalty_full import next_main
    state, cid = cast_walker(seat, branch)
    while state.cards[cid].loyalty < 5:
        state = settle(activate(state, seat, cid, 0, {'target_card_ids': []}))
        state = next_main(state, seat)
    state.mechanic_choice_players = {seat}
    first = raw_card(state, RAW, seat, Zone.GRAVEYARD)
    state = activate(state, seat, cid, 1, {'target_card_id': first.id, 'x_value': 5})
    assert state.cards[cid].zone == Zone.GRAVEYARD
    assert state.cards[cid].last_known_battlefield['loyalty'] == 0
    assert state.cards[cid].loyalty == 5, 'Native graveyard cleanup restores printed characteristics'
    original_id = state.stack[-1].id
    engine = raw_card(state, ENGINE, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 2}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine.id,
        'ability_index': 0, 'targets': {'target_stack_id': original_id}})
    assert not resolve_top_of_stack(state)
    assert 'target_card_id:' + cid in state.pending_mechanic_choice['options']
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['target_card_id:' + cid]})
    assert resolve_top_of_stack(state)
    tokens = [card for card in state.cards.values() if card.is_token and card.zone == Zone.BATTLEFIELD]
    assert len(tokens) == 1, 'A copy of the dead walker enters with printed five loyalty, not zero'
    token = tokens[0]
    assert token.oracle_text == RAW['oracle_text'] and token.loyalty == 5
    assert token.owner == token.controller == seat and token.summoning_sick
    assert state.cards[cid].zone == Zone.EXILE and state.cards[first.id].zone == Zone.GRAVEYARD
    assert state.players[seat].life == (18 if branch == 'P' else 20)
    assert not any(state.players[seat].mana_pool.values())
