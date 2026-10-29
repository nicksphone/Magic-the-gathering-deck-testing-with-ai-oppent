"""Canonical native responses and labelled negative parser/stat protocols."""
import json
from pathlib import Path

import pytest

from effects.handlers import exile_permanent
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.continuous import effective_combat_stats
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.pending_permanent_fullraw import raw_card
from tests.test_ai_recurring_engines import add, fixture
from tests.test_any_player_cast_damage import checked, settle, RAW as CAST_RAW
from tests.test_exile_power_life import RAW as BASE_RAW

FIXTURES = Path(__file__).parent / 'fixtures'
RAW = {**BASE_RAW, 'Giant Growth': raw_card('Giant Growth'), 'Humility': CAST_RAW['Humility']}
for path, name in [('hexproof_variants.json', 'Knight of Grace'),
                   ('keyword_effect_timestamps.json', 'Act of Treason')]:
    RAW[name] = next(row for row in json.loads((FIXTURES/path).read_bytes()) if row['name'] == name)
RAW['Raise the Alarm'] = json.loads((FIXTURES/'nth_spell_triggers/canonical.json').read_bytes())['Raise the Alarm']
RAW['Unsummon'] = json.loads((FIXTURES/'archangel_pair/unsummon.json').read_bytes())
RAW['Skullcrack'] = next(json.loads(line) for line in
    (FIXTURES/'knowledge_profiles/seed155-scryfall.jsonl').read_bytes().splitlines()
    if json.loads(line)['name'] == 'Skullcrack')
for name, path in [('Tainted Remedy', 'tainted-remedy'), ("Alhammarret's Archive", 'alhammarrets-archive')]:
    RAW[name] = json.loads((FIXTURES/f'life_conversion/{path}.json').read_bytes())


def position(seat, name='Monastery Swiftspear', active=None):
    state = fixture()
    state.active_player = state.priority_player = active or seat
    for player in state.players.values():
        player.mana_pool = {color: 20 for color in ('W', 'U', 'B', 'R', 'G', 'C')}
        player.snow_mana_pool.clear()
    target = add(state, name, seat, Zone.BATTLEFIELD, cards=RAW) if name else None
    return state, target.id if target else None


def cast(state, seat, name, **targets):
    spell = add(state, name, seat, Zone.HAND, cards=RAW)
    if state.priority_player != seat:
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    return checked(state, seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})


def test_all_positive_rows_are_full_canonical_objects():
    assert all(row['object'] == 'card' and len(row) > 50 for row in RAW.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_real_growth_response_changes_power_before_exile(seat):
    state, target = position(seat)
    state = cast(state, 3-seat, 'Swords to Plowshares', target_card_id=target)
    state = cast(state, 3-seat, 'Giant Growth', target_card_id=target)
    for _ in range(2):
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    assert effective_combat_stats(state, target)[0] == 4
    state = settle(state)
    assert state.players[seat].life == 24 and state.players[3-seat].life == 20
    assert state.cards[target].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
def test_real_humility_uses_effective_not_printed_power(seat):
    state, target = position(seat, 'Knight of Grace')
    assert effective_combat_stats(state, target)[0] == 2
    state = settle(cast(state, seat, 'Humility'))
    assert effective_combat_stats(state, target)[0] == 1
    state = settle(cast(state, 3-seat, 'Swords to Plowshares', target_card_id=target))
    assert state.players[seat].life == 21 and state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_real_token_retains_predeparture_power(seat):
    state, _ = position(seat, None)
    state = settle(cast(state, seat, 'Raise the Alarm'))
    tokens = [cid for cid in state.players[seat].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2 and effective_combat_stats(state, tokens[0])[0] == 1
    state = settle(cast(state, 3-seat, 'Swords to Plowshares', target_card_id=tokens[0]))
    assert tokens[0] not in state.players[seat].battlefield
    assert state.players[seat].life == 21 and state.players[3-seat].life == 20


@pytest.mark.parametrize('owner', [1, 2])
def test_real_control_change_pays_current_controller_not_owner_or_caster(owner):
    controller = 3-owner
    state, target = position(owner, active=controller)
    state = settle(cast(state, controller, 'Act of Treason', target_card_id=target))
    assert state.cards[target].owner == owner and state.cards[target].controller == controller
    state = settle(cast(state, owner, 'Swords to Plowshares', target_card_id=target))
    assert target in state.players[owner].exile
    assert state.players[controller].life == 21 and state.players[owner].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_real_unsummon_response_invalidates_target_without_life_gain(seat):
    state, target = position(seat)
    state = cast(state, 3-seat, 'Swords to Plowshares', target_card_id=target)
    state = settle(cast(state, 3-seat, 'Unsummon', target_card_id=target))
    assert state.cards[target].zone == Zone.HAND and not state.stack
    assert {pid: player.life for pid, player in state.players.items()} == {1: 20, 2: 20}


@pytest.mark.parametrize('seat', [1, 2])
def test_real_skullcrack_response_prevents_life_gain(seat):
    state, target = position(seat)
    state = cast(state, 3-seat, 'Swords to Plowshares', target_card_id=target)
    state = settle(cast(state, 3-seat, 'Skullcrack', target_player=seat))
    assert state.cards[target].zone == Zone.EXILE
    assert state.players[seat].life == 17 and state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('double_first', [False, True])
def test_native_gain_replacement_keeps_resolver_controller_and_survives_reload(seat, double_first):
    state, target = position(seat)
    converter = add(state, 'Tainted Remedy', 3-seat, Zone.BATTLEFIELD, cards=RAW)
    doubler = add(state, "Alhammarret's Archive", seat, Zone.BATTLEFIELD, cards=RAW)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    state = cast(state, 3-seat, 'Swords to Plowshares', target_card_id=target)
    for _ in range(2):
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    pending = state.pending_replacement_choice
    assert state.cards[target].zone == Zone.EXILE and pending['player_id'] == seat
    assert pending['controller'] == 3-seat
    assert pending['gain_payload']['target_player'] == seat
    assert pending['gain_payload']['__source_card_id']
    assert state.players[seat].life == 20
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked(state, seat, {'type': 'choose_replacement',
                    'replacement_source_id': doubler.id if double_first else converter.id})
    assert not state.pending_replacement_choice
    assert state.players[seat].life == (18 if double_first else 19)
    assert state.players[3-seat].life == 20


@pytest.mark.parametrize('suffix', [' Draw a card.', ', then draw a card.', '\nDraw a card.'])
def test_synthetic_unsupported_tail_does_not_partially_exile_or_gain(suffix):
    state, target = position(1)
    source = add(state, 'Swords to Plowshares', 2, Zone.HAND, cards=RAW)
    # Explicitly synthetic negative parser surface, never a canonical positive row.
    source.oracle_text += suffix
    before = serialize_match_snapshot(state)
    key, payload = infer_effect_from_oracle(state, source, 2, {'target_card_id': target})
    assert key == 'noop' and payload.get('__unsupported_instruction')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('power', [None, 0, -2])
def test_synthetic_unknown_power_is_not_conflated_with_known_nonpositive(power):
    state, target = position(1)
    # Negative malformed-stat protocol and explicit numeric boundary poses.
    state.cards[target].power = power
    state.cards[target].printed_power = None if power is None else str(power)
    assert effective_combat_stats(state, target)[0] == power
    exile_permanent(state, 2, {'target_card_id': target, '__gain_exiled_power_life': True})
    assert state.cards[target].zone == (Zone.BATTLEFIELD if power is None else Zone.EXILE)
    assert {pid: player.life for pid, player in state.players.items()} == {1: 20, 2: 20}
