"""Canonical Burn spell outcomes, not training rows or model evaluation."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from effects.registry import resolve_effect
from game_state.state import Zone
from rules_engine.continuous import has_keyword
from rules_engine.prevention import add_player_prevention_shield
from tests.test_ai_search_prefix import bare_state
from tests.test_any_player_cast_damage import checked, settle
from tests.test_linked_damage_targets import raw_card

ROOT = Path(__file__).parent / 'fixtures/ai_burn_foretell'
RAW_BYTES = (ROOT / 'CANONICAL-RAW.json').read_bytes()
RAW = json.loads(RAW_BYTES)
PROVENANCE = json.loads((ROOT / 'CARD-PROVENANCE.json').read_bytes())
WAIT = {'type': 'pass_priority'}


def test_exact_full_canonical_origins():
    assert sha256(RAW_BYTES).hexdigest() == '3072700528cfd0a7ec6878dc2a7f94cece02f3c2901221ee1ddd490c0aee214d'
    assert len(RAW) == 22 and 'Lightning Helix' not in RAW
    for name, raw in RAW.items():
        encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert sha256(encoded).hexdigest() == PROVENANCE['cards'][name]['object_sha256']
        assert raw['object'] == 'card' and raw['name'] == name


def add(state, name, seat, zone=Zone.HAND):
    raw = RAW[name]
    image = ScryfallSyncService._extract_remote_image_uri(raw)
    assert image
    row = {**deepcopy(raw), **ScryfallSyncService._normalize_payload(raw, image),
           'colors': deepcopy(raw['colors']), 'card_faces': deepcopy(raw.get('card_faces', []))}
    for key in ('oracle_text', 'mana_cost', 'type_line', 'power', 'toughness', 'loyalty', 'colors'):
        assert row.get(key) == raw.get(key)
    card = raw_card(state, row, seat, zone)
    assert card.oracle_text == raw['oracle_text'] and card.mana_cost == raw['mana_cost']
    assert card.type_line == raw['type_line'] and card.colors == raw['colors']
    # Factory runtime keywords are not Scryfall's catalog keyword labels.
    assert card.keywords == (['flying', 'vigilance'] if name == 'Serra Angel' else [])
    return card.id


def cast_resolve(state, seat, name, mana, targets):
    cid = add(state, name, seat)
    state.players[seat].mana_pool = dict(mana)
    action = {'type': 'cast_spell', 'card_id': cid,
              'cost_choice': {'id': 'base'}, 'targets': targets}
    state = checked(state, seat, action)
    assert state.cards[cid].zone == Zone.STACK
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert any(item.source_card_id == cid for item in state.stack)
    state = settle(state)
    assert not state.stack and state.cards[cid].zone == Zone.GRAVEYARD
    return state


def facts(state, seat, case, **extra):
    result = {'case': case, 'seat': seat,
              'life': {str(pid): p.life for pid, p in state.players.items()}, **extra}
    print('ACTUAL ' + json.dumps(result, sort_keys=True), flush=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,target_kind,mana', [
    ('Lava Spike', 'player', {'R': 1}),
    ('Rift Bolt', 'player', {'R': 1, 'C': 2}),
    ('Rift Bolt', 'creature', {'R': 1, 'C': 2}),
])
def test_paid_burn_damage(seat, name, target_kind, mana):
    state = bare_state(seat)
    target = add(state, 'Serra Angel', 3-seat, Zone.BATTLEFIELD) if target_kind == 'creature' else None
    targets = {'target_card_id': target} if target else {'target_player': 3-seat}
    state = cast_resolve(state, seat, name, mana, targets)
    damage = state.cards[target].counters.get('__damage_marked', 0) if target else None
    facts(state, seat, name + ':' + target_kind, creature_damage=damage)
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == (20 if target else 17)
    if target:
        assert state.cards[target].zone == Zone.BATTLEFIELD and damage == 3
    assert state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_skullcrack_damage_and_both_global_restrictions_expire(seat):
    state = bare_state(seat)
    add_player_prevention_shield(state, 3-seat, 5)
    state = cast_resolve(state, seat, 'Skullcrack', {'R': 1, 'C': 1},
                         {'target_player': 3-seat})
    facts(state, seat, 'Skullcrack', cant_gain=sorted(state.turn_cant_gain_life),
          cant_prevent=state.turn_damage_cant_be_prevented)
    assert state.players[seat].life == 20 and state.players[3-seat].life == 17
    assert state.turn_cant_gain_life == {1, 2}
    assert state.turn_damage_cant_be_prevented is True
    before = {pid: p.life for pid, p in state.players.items()}
    # Probe the existing life-gain event, not an invented spell or Oracle body.
    for pid in (1, 2):
        resolve_effect(state, pid, 'gain_life', {'target_player': pid, 'amount': 5})
        assert state.players[pid].life == before[pid]
    if state.priority_player != seat:
        state = checked(state, state.priority_player, WAIT)
    state = cast_resolve(state, seat, 'Lightning Bolt', {'R': 1}, {'target_player': 3-seat})
    assert state.players[3-seat].life == 14
    turn = state.turn
    for _ in range(64):
        if state.turn > turn:
            break
        state = checked(state, state.priority_player, WAIT)
    assert state.turn > turn and state.winner is None
    assert state.turn_cant_gain_life == set()
    assert state.turn_damage_cant_be_prevented is False
    for pid in (1, 2):
        before = state.players[pid].life
        resolve_effect(state, pid, 'gain_life', {'target_player': pid, 'amount': 5})
        assert state.players[pid].life == before + 5


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['damage', 'indestructible', 'double_strike'])
def test_paid_boros_charm_modes_and_expiry(seat, mode):
    state = bare_state(seat)
    ally = add(state, 'Serra Angel', seat, Zone.BATTLEFIELD)
    land = add(state, 'Island', seat, Zone.BATTLEFIELD)
    enemy = add(state, 'Serra Angel', 3-seat, Zone.BATTLEFIELD)
    index = {'damage': 1, 'indestructible': 2, 'double_strike': 3}[mode]
    text = RAW['Boros Charm']['oracle_text'].splitlines()[index].removeprefix(chr(8226) + ' ').rstrip('.')
    targets = {'mode_text': text}
    if mode == 'damage':
        targets['target_player'] = 3-seat
    elif mode == 'double_strike':
        targets['target_card_id'] = ally
    state = cast_resolve(state, seat, 'Boros Charm', {'R': 1, 'W': 1}, targets)
    observed = {str(cid): {key: has_keyword(state, cid, key)
                          for key in ('indestructible', 'double strike')}
                for cid in (ally, land, enemy)}
    facts(state, seat, 'Boros Charm:' + mode, keywords=observed)
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == (16 if mode == 'damage' else 20)
    for cid in (ally, land, enemy):
        assert has_keyword(state, cid, 'indestructible') == (mode == 'indestructible' and cid in (ally, land))
        assert has_keyword(state, cid, 'double strike') == (mode == 'double_strike' and cid == ally)
    late = add(state, 'Serra Angel', seat, Zone.BATTLEFIELD)
    assert not has_keyword(state, late, 'indestructible')
    turn = state.turn
    for _ in range(64):
        if state.turn > turn:
            break
        state = checked(state, state.priority_player, WAIT)
    assert state.turn > turn and state.winner is None
    for cid in (ally, land, enemy):
        assert not has_keyword(state, cid, 'indestructible')
        assert not has_keyword(state, cid, 'double strike')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('landfall', [False, True])
def test_paid_searing_blaze_uses_actual_land_entry_and_both_targets(seat, landfall):
    state = bare_state(seat)
    target = add(state, 'Serra Angel', 3-seat, Zone.BATTLEFIELD)
    assert state.land_entries_this_turn.get(seat, 0) == 0
    if landfall:
        land = add(state, 'Mountain', seat)
        state = checked(state, seat, {'type': 'play_land', 'card_id': land})
        assert state.cards[land].zone == Zone.BATTLEFIELD
        assert state.land_entries_this_turn[seat] == 1
    state = cast_resolve(state, seat, 'Searing Blaze', {'R': 2},
                         {'target_player': 3-seat, 'target_card_id': target})
    damage = state.cards[target].counters.get('__damage_marked', 0)
    facts(state, seat, 'Searing Blaze', landfall=landfall, creature_damage=damage)
    assert state.players[seat].life == 20
    assert state.players[3-seat].life == (17 if landfall else 19)
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert damage == (3 if landfall else 1)
    assert state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_rift_bolt_paid_suspend_reaches_native_next_own_upkeep_cast(seat):
    state = bare_state(seat)
    state.mechanic_choice_players = {1, 2}
    cid = add(state, 'Rift Bolt', seat)
    state.players[seat].mana_pool = {'R': 1}
    state = checked(state, seat, {'type': 'suspend', 'card_id': cid})
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.cards[cid].zone == Zone.EXILE and state.cards[cid].counters['time'] == 1
    assert not state.stack and not state.spells_cast_this_turn.get(seat, 0)
    turn = state.turn
    for _ in range(128):
        if state.pending_mechanic_choice:
            break
        state = checked(state, state.priority_player, WAIT)
    assert state.turn > turn and state.active_player == seat
    assert state.pending_mechanic_choice['kind'] == 'suspend_cast'
    assert state.cards[cid].counters.get('time', 0) == 0
    state = checked(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True,
                                 'targets': {'target_player': 3-seat}})
    assert state.cards[cid].zone == Zone.STACK and not state.pending_mechanic_choice
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = settle(state)
    facts(state, seat, 'Rift Bolt:paid-suspend-native-upkeep')
    assert state.cards[cid].zone == Zone.GRAVEYARD and not state.stack
    assert state.players[seat].life == 20 and state.players[3-seat].life == 17
