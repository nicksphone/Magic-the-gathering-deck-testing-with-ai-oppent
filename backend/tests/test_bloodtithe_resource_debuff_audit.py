"""Strict canonical paid resource-derived debuff audit; no product bypasses."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.ability_model import build_ability_spec
from rules_engine.continuous import effective_combat_stats, printed_abilities_suppressed
from rules_engine.costs import activated_cost_available
from rules_engine.engine import RulesEngine
from rules_engine.land_types import effective_type_line
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.restrictions import can_activate_in_current_timing
from rules_engine.type_effects import effective_types
from rules_engine.targeting import stack_object_kind
from training.environment import TrainingEnvironment


FIXTURES = Path(__file__).parent / 'fixtures'
DIRECTORY = FIXTURES / 'bloodtithe_resource_debuff'
RAW = json.loads((DIRECTORY / 'bloodtithe-harvester.json').read_text())
GROWTH = json.loads((DIRECTORY / 'giant-growth.json').read_text())
ROWS = {RAW['name']: RAW, GROWTH['name']: GROWTH}
TARGET = json.loads((DIRECTORY / 'colossal-dreadmaw.json').read_text())
ROWS[TARGET['name']] = TARGET
for relative in ('soulscar_protection_boundaries/naturalize.json',
                 'favor_target_lifecycle/cloudshift.json',
                 'favor_target_lifecycle/unsummon.json',
                 'soulscar_protection_boundaries/dress-down.json'):
    row = json.loads((FIXTURES / relative).read_text())
    ROWS[row['name']] = row


def snap(state):
    return serialize_match_snapshot(state)


def restore(state):
    before = snap(state)
    result = deserialize_match_snapshot(before)
    assert snap(result) == before
    return result


def act(state, seat, action):
    before = snap(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert snap(state) == before
    return result


def add(state, name, owner, zone=Zone.HAND):
    raw = ROWS.get(name) or fallback_card_payload(name)
    assert raw and raw['oracle_text'] is not None
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=7107)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = owner
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[owner], zone.value).append(card.id)
    return card.id


def position(seat):
    raw = fallback_card_payload('Forest')
    deck = [{**raw, 'quantity': 60, 'card_name': 'Forest'}]
    state = MatchFactory.from_decks(deck, deck, seed=7107)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    # Explicit canonical starting board, not a natural or historical game.
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {}
    for owner in (1, 2):
        for name in ('Swamp',) * 3 + ('Mountain',) * 3 + ('Forest',) * 2 + ('Island',) * 2 + ('Plains',) * 2:
            add(state, name, owner, Zone.BATTLEFIELD)
    target = add(state, 'Colossal Dreadmaw', 3-seat, Zone.BATTLEFIELD)
    return state, target


def pass_once(state):
    return act(state, state.priority_player, {'type': 'pass_priority'})


def cast(state, seat, name, targets=None):
    if state.priority_player != seat:
        state = pass_once(state)
    cid = add(state, name, seat)
    tapped = sum(state.cards[cid].tapped for cid in state.players[seat].battlefield)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': targets or {},
                             'cost_choice': {'id': 'base'}})
    assert state.cards[cid].zone == Zone.STACK
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield) > tapped
    return restore(state), cid


def drain(state):
    for _ in range(24):
        if not state.stack and not state.pending_mechanic_choice:
            return restore(state)
        assert not state.pending_mechanic_choice, 'Separate upstream unexpected private choice'
        state = pass_once(state)
    raise AssertionError('Separate upstream stack/entry continuation did not finish')


def blood(state, seat):
    return [cid for cid in state.players[seat].battlefield
            if state.cards[cid].is_token and 'Artifact' in effective_types(state, state.cards[cid])
            and 'Blood' in effective_type_line(state, state.cards[cid]).split('—')[-1].split()]


def paid_source(state, seat):
    before = len(blood(state, seat))
    state, source = cast(state, seat, RAW['name'])
    state = drain(state)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.cards[source].summoning_sick
    assert len(blood(state, seat)) == before + 1, 'Separate upstream full canonical ETB Blood gap'
    return state, source


def next_main(state, seat):
    turn = state.turn
    for _ in range(160):
        if state.turn > turn and state.active_player == seat and state.step == Step.PRECOMBAT_MAIN:
            assert not state.stack
            return restore(state)
        state = pass_once(state)
    raise AssertionError('Separate upstream legitimate phase progression failed')


def ready(seat, count=1, opposing_count=0):
    state, target = position(seat)
    state, source = paid_source(state, seat)
    if count == 2:
        state, _ = paid_source(state, seat)
    elif count == 0:
        state, _ = cast(state, seat, 'Naturalize', {'target_card_id': blood(state, seat)[0]})
        state = drain(state)
    assert len(blood(state, seat)) == count
    if opposing_count:
        state = next_main(state, 3-seat)
        for _ in range(opposing_count):
            state, _ = paid_source(state, 3-seat)
    state = next_main(state, seat)
    assert not state.cards[source].summoning_sick
    assert len(blood(state, seat)) == count
    assert len(blood(state, 3-seat)) == opposing_count
    return state, source, target


def activation(state, source, target):
    ability = extract_activated_abilities(state.cards[source])[0]
    return {'type': 'activate_ability', 'card_id': source, 'ability_index': ability['index'],
            'targets': {'target_card_id': target},
            'payment_choices': {'sacrifice_card_ids': [source]}}


def record(request, state, source, target):
    path = os.environ.get('MTG_BLOODTITHE_TRACE')
    if not path:
        return
    with open(path, 'a') as stream:
        stream.write(json.dumps({'node': request.node.nodeid, 'turn': state.turn, 'step': state.step.value,
            'active_player': state.active_player, 'source_zone': state.cards[source].zone.value,
            'source_sick': state.cards[source].summoning_sick, 'blood': {pid: blood(state, pid) for pid in (1, 2)},
            'target_stats': effective_combat_stats(state, target),
            'offered': RulesEngine().legal_moves(state, state.active_player)}, sort_keys=True) + '\n')


def activate(request, state, seat, source, target):
    record(request, state, source, target)
    assert any(move['type'] == 'activate_ability' and move.get('card_id') == source
               for move in RulesEngine().legal_moves(state, seat)), 'Canonical resource-scaled debuff missing from legal view'
    before_blood = blood(state, seat)
    state = act(state, seat, activation(state, source, target))
    assert state.cards[source].zone == Zone.GRAVEYARD and source in state.players[seat].graveyard
    assert blood(state, seat) == before_blood
    frame = next(item for item in state.stack if item.source_card_id == source)
    assert frame.controller == seat and stack_object_kind(state, frame) == 'activated'
    assert frame.payload['__announced_targets']['target_card_id'] == target
    return restore(state)


def test_full_raw_provenance_printed_bodies_and_wotc_resolution_rulings():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    for row in provenance['sources']:
        assert hashlib.sha256((Path(__file__).parents[1] / row['path']).read_bytes()).hexdigest() == row['sha256']
    assert RAW['object'] == 'card'
    assert RAW['oracle_text'] == fallback_card_payload(RAW['name'])['oracle_text']
    rulings = json.loads((DIRECTORY / 'bloodtithe-rulings.json').read_text())['data']
    assert any(row['source'] == 'wotc' and 'as Bloodtithe Harvester' in row['comment'] and
               'resolves' in row['comment'] for row in rulings)
    assert any(row['source'] == 'wotc' and 'artifact token with the subtype Blood' in row['comment'] for row in rulings)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_source_and_complete_etb_publish_real_blood(seat):
    state, _ = position(seat)
    state, source = paid_source(state, seat)
    assert len(blood(state, seat)) == 1 and not blood(state, 3-seat)
    assert restore(state).cards[source].oracle_text == RAW['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 2])
def test_resolution_uses_current_own_blood_and_source_already_graveyard(request, seat, count):
    state, source, target = ready(seat, count)
    before = effective_combat_stats(state, target)
    state = activate(request, state, seat, source, target)
    state = drain(state)
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert effective_combat_stats(state, target) == tuple(stat-2*count for stat in before)
    assert len(blood(state, seat)) == count


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_opponent_paid_blood_not_counted(request, seat):
    state, source, target = ready(seat, count=1, opposing_count=2)
    before = effective_combat_stats(state, target)
    state = drain(activate(request, state, seat, source, target))
    assert effective_combat_stats(state, target) == tuple(stat-2 for stat in before)
    assert len(blood(state, 3-seat)) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_naturalize_response_changes_resolution_count_not_announced_x(request, seat):
    state, source, target = ready(seat, count=2)
    before = effective_combat_stats(state, target)
    state = activate(request, state, seat, source, target)
    victim = blood(state, seat)[0]
    state, spell = cast(state, 3-seat, 'Naturalize', {'target_card_id': victim})
    state = pass_once(pass_once(state))
    assert state.cards[victim].zone == Zone.CEASED
    assert victim not in state.players[seat].battlefield
    assert state.cards[spell].zone == Zone.GRAVEYARD and len(blood(state, seat)) == 1
    assert state.stack and state.cards[source].zone == Zone.GRAVEYARD
    state = drain(restore(state))
    assert effective_combat_stats(state, target) == tuple(stat-2 for stat in before)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['stale', 'blink'])
def test_actual_paid_target_departure_or_new_object_never_gets_old_debuff(request, seat, kind):
    state, source, target = ready(seat)
    original = (object_incarnation(state.cards[target]), state.cards[target].zone_change_sequence)
    state = activate(request, state, seat, source, target)
    spell_name = 'Unsummon' if kind == 'stale' else 'Cloudshift'
    state, _ = cast(state, 3-seat, spell_name, {'target_card_id': target})
    state = pass_once(pass_once(state))
    assert state.cards[target].zone == (Zone.HAND if kind == 'stale' else Zone.BATTLEFIELD)
    assert (object_incarnation(state.cards[target]), state.cards[target].zone_change_sequence) != original
    if kind == 'blink':
        assert effective_combat_stats(state, target) == (6, 6)
    state = drain(restore(state))
    assert state.cards[target].zone == (Zone.HAND if kind == 'stale' else Zone.BATTLEFIELD)
    if kind == 'blink':
        assert effective_combat_stats(state, target) == (6, 6)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_source_sickness_and_sorcery_rejections_preserve_root(seat):
    state, target = position(seat)
    state, source = paid_source(state, seat)
    ability = extract_activated_abilities(state.cards[source])[0]
    assert not activated_cost_available(state, seat, source, ability['mana_cost'], ability_index=ability['index'])
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, activation(state, source, target))
    assert snap(state) == before
    state = next_main(state, 3-seat)
    assert not can_activate_in_current_timing(state, ability['text'], seat)
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, activation(state, source, target))
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_dress_down_suppression_and_rejection_are_independent_of_missing_body(seat):
    state, source, target = ready(seat)
    state, _ = cast(state, 3-seat, 'Dress Down')
    state = drain(state)
    assert printed_abilities_suppressed(state, source)
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, activation(state, source, target))
    assert snap(state) == before and state.cards[source].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_positive_paid_naturalize_and_cloudshift_response_routes(seat):
    state, source, target = ready(seat)
    victim = blood(state, seat)[0]
    state, _ = cast(state, 3-seat, 'Naturalize', {'target_card_id': victim})
    state = drain(state)
    assert state.cards[victim].zone == Zone.CEASED and not blood(state, seat)
    assert victim not in state.players[seat].battlefield
    previous = object_incarnation(state.cards[target])
    state, _ = cast(state, 3-seat, 'Cloudshift', {'target_card_id': target})
    state = drain(state)
    assert object_incarnation(state.cards[target]) != previous
    assert effective_combat_stats(state, target) == (6, 6)
    assert restore(state).cards[source].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_private_hand_and_snapshot_contract_on_real_paid_position(seat):
    state, source, target = ready(seat)
    env = TrainingEnvironment()
    env._state = state
    before = snap(state)
    for actor in (1, 2):
        view = env.observe(actor)
        assert 'hand' not in view['players'][str(3-actor)]
        assert all(cid not in view['known_cards'] for cid in state.players[3-actor].hand)
    assert snap(state) == before
    assert snap(restore(state)) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_fixed_number_paid_buff_and_cleanup_remain_unchanged(seat):
    state, source, target = ready(seat)
    before = effective_combat_stats(state, target)
    state, _ = cast(state, seat, GROWTH['name'], {'target_card_id': target})
    state = drain(state)
    assert effective_combat_stats(state, target) == tuple(stat+3 for stat in before)
    state = next_main(state, 3-seat)
    assert effective_combat_stats(state, target) == before
    assert restore(state).cards[source].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('suffix', [' Draw a card.', ' Gain 2 life.'])
def test_unknown_full_body_tail_gets_no_partial_reward(suffix):
    state, target = position(1)
    source = add(state, RAW['name'], 1, Zone.BATTLEFIELD)
    body = extract_activated_abilities(state.cards[source])[0]['text'] + suffix
    # Negative compiler prose only; never placed into a playable CardInstance.
    proxy = SimpleNamespace(id=source, name=RAW['name'], mana_cost='', oracle_text=body)
    before = snap(state)
    spec = build_ability_spec(state, proxy, 1, {'target_card_id': target}, report_unsupported=False)
    assert snap(state) == before
    assert spec.effect.key == 'noop', 'Unsupported complete body received a partial reward'


def test_native_and_public_sqlite_socket_denial_precedes_collection():
    import _socket
    import _sqlite3
    import sqlite3
    for probe in (lambda: sqlite3.connect(':memory:'), lambda: sqlite3.dbapi2.connect(':memory:'),
                  lambda: _sqlite3.connect(':memory:'), lambda: _sqlite3.Connection(':memory:'),
                  lambda: _socket.socket.__new__(_socket.socket)):
        with pytest.raises(RuntimeError, match='SQL/socket denied'):
            probe()
