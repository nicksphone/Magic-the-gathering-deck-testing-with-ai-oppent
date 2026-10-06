"""Full raw public fixtures; funded positions are not natural games.

Desired timing failures remain ordinary failures. No Oracle/keyword/permission
rewrite is used to manufacture the grant under investigation.
"""
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.restrictions import can_cast_in_current_timing
from tests.test_linked_damage_targets import raw_card

DIRECTORY = Path(__file__).parent / 'fixtures/global_flash_timing_audit'
ROWS = {}
for record in json.loads((DIRECTORY / 'provenance.json').read_text())['cards']:
    data = (DIRECTORY / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    row = json.loads(data)
    assert row['object'] == 'card' and row['oracle_id'] == record['oracle_id']
    ROWS[row['name']] = row

GRANTS = ['Leyline of Anticipation', 'Vedalken Orrery']
SPELLS = ['Grizzly Bears', 'Divination']


def snapshot(state):
    return json.loads(json.dumps(serialize_match_snapshot(state)))


def record(label, state, seat, detail):
    directory = os.environ.get('MTG_GLOBAL_FLASH_EVIDENCE')
    if not directory:
        return
    path = Path(directory) / (label + '.json')
    with path.open('x') as f:
        json.dump({'snapshot': snapshot(state), 'seat': seat, 'detail': detail}, f, indent=2)


def position(seat, grant, spell='Grizzly Bears', *, own_main=False, source=True):
    deck = [{**ROWS['Island'], 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=77531)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.active_player = seat if own_main else 3-seat
    state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN if own_main else Step.UPKEEP
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {}
    permanent = raw_card(state, ROWS[grant], seat, Zone.BATTLEFIELD) if source else None
    if permanent:
        assign_static_order_on_battlefield_entry(state, permanent.id)
    card = raw_card(state, ROWS[spell], seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'C': 1} if spell == 'Grizzly Bears' else {'U': 1, 'C': 2}
    return state, permanent, card


def cast(card):
    return {'type': 'cast_spell', 'card_id': card.id, 'targets': {}}


def offered(state, seat, cid):
    return any(move['type'] == 'cast_spell' and move.get('card_id') == cid
               for move in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
@pytest.mark.parametrize('spell', SPELLS)
def test_desired_global_permission_shared_timing_query(seat, grant, spell):
    state, permanent, card = position(seat, grant, spell)
    before = snapshot(state)
    result = can_cast_in_current_timing(state, card, seat)
    assert snapshot(state) == before
    record(f'query-{seat}-{grant}-{spell}', state, seat, {'result': result})
    assert result[0], result[1]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
@pytest.mark.parametrize('spell', SPELLS)
def test_desired_global_permission_move_generation(seat, grant, spell):
    state, _, card = position(seat, grant, spell)
    before = snapshot(state)
    available = offered(state, seat, card.id)
    assert snapshot(state) == before
    record(f'moves-{seat}-{grant}-{spell}', state, seat, {'offered': available})
    assert available, 'Canonical global flash source must admit this funded off-turn spell'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
@pytest.mark.parametrize('spell', SPELLS)
def test_desired_global_permission_actual_paid_checked_cast(seat, grant, spell):
    state, permanent, card = position(seat, grant, spell)
    before = snapshot(state)
    try:
        candidate = checked_action(state, RulesEngine(), seat, cast(card))
    except ActionRejected as error:
        record(f'paid-{seat}-{grant}-{spell}', state, seat, {'rejection': str(error), 'root_pure': snapshot(state) == before})
        raise
    finally:
        assert snapshot(state) == before
    assert candidate.cards[card.id].zone == Zone.STACK
    assert sum(candidate.players[seat].mana_pool.values()) == 0
    assert candidate.cards[permanent.id].zone == Zone.BATTLEFIELD
    assert any(item.source_card_id == card.id for item in candidate.stack)
    restored = deserialize_match_snapshot(snapshot(candidate))
    assert snapshot(restored) == snapshot(candidate)
    record(f'paid-{seat}-{grant}-{spell}', candidate, seat, {'paid': True, 'root_pure': True, 'roundtrip_exact': True})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
@pytest.mark.parametrize('spell', SPELLS)
def test_no_grant_same_funded_window_is_restricted(seat, grant, spell):
    state, _, card = position(seat, grant, spell, source=False)
    before = snapshot(state)
    assert not can_cast_in_current_timing(state, card, seat)[0]
    assert not offered(state, seat, card.id)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, cast(card))
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
@pytest.mark.parametrize('spell', SPELLS)
def test_same_cards_pay_normally_in_own_empty_main(seat, grant, spell):
    state, _, card = position(seat, grant, spell, own_main=True)
    before = snapshot(state)
    assert can_cast_in_current_timing(state, card, seat)[0]
    assert offered(state, seat, card.id)
    candidate = checked_action(state, RulesEngine(), seat, cast(card))
    assert candidate.cards[card.id].zone == Zone.STACK
    assert sum(candidate.players[seat].mana_pool.values()) == 0
    assert snapshot(state) == before


def grip_on_stack(state, seat, permanent):
    # Native priority pass, actual paid counterparty spell; no fake stack item.
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    assert state.priority_player == 3-seat
    grip = raw_card(state, ROWS['Krosan Grip'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'G': 1, 'C': 2}
    state = checked_action(state, RulesEngine(), 3-seat,
        {'type': 'cast_spell', 'card_id': grip.id, 'targets': {'target_card_id': permanent.id}})
    assert sum(state.players[3-seat].mana_pool.values()) == 0
    return checked_action(state, RulesEngine(), 3-seat, {'type': 'pass_priority'})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
def test_supported_split_second_prohibition_outranks_permission(seat, grant):
    state, permanent, _ = position(seat, grant)
    state = grip_on_stack(state, seat, permanent)
    assert state.priority_player == seat and state.stack
    instant = raw_card(state, ROWS['Opt'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1}
    before = snapshot(state)
    okay, reason = can_cast_in_current_timing(state, instant, seat)
    assert not okay and 'Split second' in reason
    assert not offered(state, seat, instant.id)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, cast(instant))
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
@pytest.mark.parametrize('spell', SPELLS)
def test_source_destroyed_by_actual_paid_spell_has_no_permission(seat, grant, spell):
    state, permanent, card = position(seat, grant, spell)
    state = grip_on_stack(state, seat, permanent)
    for _ in range(4):
        if not state.stack:
            break
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert not state.stack and state.cards[permanent.id].zone == Zone.GRAVEYARD
    if state.priority_player != seat:
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == seat and state.active_player == 3-seat
    before = snapshot(state)
    assert not can_cast_in_current_timing(state, state.cards[card.id], seat)[0]
    assert not offered(state, seat, card.id)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, cast(card))
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
def test_land_play_is_not_a_spell_even_with_global_flash(seat, grant):
    state, _, _ = position(seat, grant)
    land = raw_card(state, ROWS['Island'], seat, Zone.HAND)
    before = snapshot(state)
    assert not any(move['type'] == 'play_land' for move in RulesEngine().legal_moves(state, seat))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'play_land', 'card_id': land.id})
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
def test_loyalty_activation_is_not_a_spell_with_global_flash(seat, grant):
    state, _, _ = position(seat, grant)
    walker = raw_card(state, ROWS['Jace Beleren'], seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, walker.id)
    before = snapshot(state)
    assert not any(move['type'] == 'activate_loyalty' for move in RulesEngine().legal_moves(state, seat))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'activate_loyalty', 'card_id': walker.id, 'ability_index': 0})
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
@pytest.mark.parametrize('window', ['own_upkeep', 'own_combat', 'opponent_combat'])
def test_canonical_explicit_timing_restriction_is_not_relaxed(seat, grant, window):
    state, _, _ = position(seat, grant)
    spell = raw_card(state, ROWS['Savage Beating'], seat, Zone.HAND)
    state.active_player = seat if window != 'opponent_combat' else 3-seat
    state.step = Step.UPKEEP if window == 'own_upkeep' else Step.BEGIN_COMBAT
    before = snapshot(state)
    allowed, reason = can_cast_in_current_timing(state, spell, seat)
    assert snapshot(state) == before
    record(f'restriction-{seat}-{grant}-{window}', state, seat, {'allowed': allowed, 'reason': reason})
    assert allowed == (window == 'own_combat')
