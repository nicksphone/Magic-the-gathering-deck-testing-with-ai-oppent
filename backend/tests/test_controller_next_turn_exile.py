"""Paid canonical exile permissions follow actual turns, not a turn-number guess."""
import json
import hashlib
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.card_faces import ordinary_exile_permission
from rules_engine.engine import RulesEngine
from tests.library_canonical_fixtures import canonical_card, raw_card
from tests.oracle_effects_positive_fixtures_8d import remaining_card
from tests.queued_sequence_support import add as add_sequence_card

FIXTURES = Path(__file__).parent / 'fixtures/exile_play_durations'
PROVENANCE_SHA = 'b0b251545cb23cc1d66ff757bcd5bf240d7e62a6b2f5e253020c68ae94ed204f'
assert hashlib.sha256((FIXTURES / 'PROVENANCE.json').read_bytes()).hexdigest() == PROVENANCE_SHA
ROWS = {}
for entry in json.loads((FIXTURES / 'PROVENANCE.json').read_bytes())['rows']:
    data = (FIXTURES / entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    row = json.loads(data)
    assert row['name'] == entry['name'] and row['id'] == entry['scryfall_id']
    assert row['oracle_id'] == entry['oracle_id']
    ROWS[row['name']] = row


def put(state, name, seat, zone=Zone.HAND):
    if name == 'Time Warp':
        return add_sequence_card(state, name, seat, zone).id
    cid = state.allocate_object_id()
    if name in ROWS:
        sample = MatchFactory.from_decks([{**ROWS[name], 'card_name': name, 'quantity': 1}], [], seed=141732)
        card = next(iter(sample.cards.values()))
        card.id, card.owner, card.controller = cid, seat, seat
        card.move_to_zone(zone)
        assert card.oracle_text == ROWS[name]['oracle_text']
    else:
        factory = remaining_card if name == 'Light Up the Stage' else canonical_card
        card = factory(name, id=cid, owner=seat, controller=seat, zone=zone)
    state.cards[cid] = card
    getattr(state.players[seat], zone.value).append(cid)
    return cid


def position(seat):
    mountain = raw_card('Mountain')
    deck = [{**mountain, 'card_name': 'Mountain', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=141731)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.turn, state.step = 5, Step.PRECOMBAT_MAIN
    for pid, player in state.players.items():
        for cid in list(player.hand):
            player.hand.remove(cid); player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        for _ in range(10):
            put(state, 'Mountain', pid, Zone.BATTLEFIELD)
        for _ in range(6):
            put(state, 'Island', pid, Zone.BATTLEFIELD)
    return state


def act(state, seat, action):
    return checked_action(state, RulesEngine(), seat, action)


def until(state, predicate):
    for _ in range(240):
        if predicate(state):
            return state
        assert state.pending_mechanic_choice is None
        assert state.pending_trigger_order is None
        assert state.winner is None
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native phase progression exceeded the declared bound')


def cast(state, name, seat, targets=None):
    cid = put(state, name, seat)
    action = {'type': 'cast_spell', 'card_id': cid, 'targets': targets or {}}
    if name == 'Rob the Archives':
        action['cost_choice'] = {'id': 'base'}
    state = act(state, seat, action)
    assert state.stack[-1].source_card_id == cid
    expected = 5 if name == 'Time Warp' else 2 if name == 'Rob the Archives' else 3
    assert state.stack[-1].payload['mana_spent'] == expected
    if name == 'Time Warp':
        assert state.stack[-1].effect_key == 'extra_turn'
    return state, cid


def grant(seat):
    state = position(seat)
    land = put(state, 'Mountain', seat, Zone.LIBRARY)
    bolt = put(state, 'Lightning Bolt', seat, Zone.LIBRARY)
    state.players[seat].library = [cid for cid in state.players[seat].library if cid not in (land, bolt)] + [land, bolt]
    state, source = cast(state, 'Light Up the Stage', seat)
    assert state.stack[-1].effect_key == 'exile_top_cards_playable'
    state = until(state, lambda s: not s.stack)
    assert all(cid in state.players[seat].exile for cid in (land, bolt))
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert ordinary_exile_permission(state, seat, land)
    assert ordinary_exile_permission(state, seat, bolt)
    return state, land, bolt


def next_main(state, seat, grant_turn):
    return until(state, lambda s: s.turn > grant_turn and s.active_player == seat
                 and s.priority_player == seat and s.step == Step.PRECOMBAT_MAIN)


def assert_offered_and_play(state, seat, land, bolt):
    moves = RulesEngine().legal_moves(state, seat)
    assert any(m['type'] == 'play_land' and m.get('card_id') == land and m.get('from_exile') for m in moves)
    assert any(m['type'] == 'cast_spell' and m.get('card_id') == bolt and m.get('from_exile') for m in moves)
    state = act(state, seat, {'type': 'play_land', 'card_id': land, 'from_exile': True})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': bolt, 'from_exile': True,
                             'targets': {'target_player': 3 - seat}})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = until(state, lambda s: not s.stack)
    assert state.players[3 - seat].life == 17
    assert state.cards[land].zone == Zone.BATTLEFIELD
    assert state.cards[bolt].zone == Zone.GRAVEYARD
    assert not ordinary_exile_permission(state, seat, land)
    assert not ordinary_exile_permission(state, seat, bolt)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_paid_canonical_grant_allows_land_and_spell_on_actual_next_turn(seat, restore):
    state, land, bolt = grant(seat)
    if restore:
        payload = json.loads(json.dumps(serialize_match_snapshot(state)))
        state = deserialize_match_snapshot(payload)
        assert json.loads(json.dumps(serialize_match_snapshot(state))) == payload
    state = next_main(state, seat, 5)
    assert state.turn == 7
    assert ordinary_exile_permission(state, seat, land)
    assert ordinary_exile_permission(state, seat, bolt)
    assert_offered_and_play(state, seat, land, bolt)


@pytest.mark.parametrize('seat', [1, 2])
def test_permission_expires_at_actual_own_next_cleanup_not_at_a_trigger(seat):
    state, land, bolt = grant(seat)
    state = next_main(state, seat, 5)
    assert ordinary_exile_permission(state, seat, bolt)
    state = until(state, lambda s: s.step == Step.CLEANUP and not s.cleanup_pending)
    assert state.active_player == seat and state.turn == 7 and not state.stack
    assert not ordinary_exile_permission(state, seat, land)
    assert not ordinary_exile_permission(state, seat, bolt)
    assert all(cid in state.players[seat].exile for cid in (land, bolt))


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_own_extra_turn_expires_at_its_cleanup_even_before_plus_two(seat):
    state, land, bolt = grant(seat)
    state, _ = cast(state, 'Time Warp', seat, {'target_player': seat})
    state = until(state, lambda s: not s.stack)
    state = next_main(state, seat, 5)
    assert state.turn == 6 and ordinary_exile_permission(state, seat, bolt)
    state = until(state, lambda s: s.step == Step.CLEANUP and not s.cleanup_pending)
    assert state.active_player == seat and state.turn == 6
    assert not ordinary_exile_permission(state, seat, land)
    assert not ordinary_exile_permission(state, seat, bolt)


@pytest.mark.parametrize('seat', [1, 2])
def test_later_added_opponent_extra_turns_do_not_expire_the_grant(seat):
    state, land, bolt = grant(seat)
    other = 3 - seat
    state = until(state, lambda s: s.turn == 6 and s.active_player == other
                  and s.step == Step.PRECOMBAT_MAIN and s.priority_player == other)
    for _ in range(2):
        state, _ = cast(state, 'Time Warp', other, {'target_player': other})
        state = until(state, lambda s: not s.stack)
    state = next_main(state, seat, 5)
    assert state.turn == 9
    assert ordinary_exile_permission(state, seat, land)
    assert ordinary_exile_permission(state, seat, bolt)
    assert_offered_and_play(state, seat, land, bolt)


@pytest.mark.parametrize('seat', [1, 2])
def test_native_new_zone_visit_cannot_reuse_a_real_prior_grant(seat):
    state, _, bolt = grant(seat)
    player, card = state.players[seat], state.cards[bolt]
    original_sequence = card.zone_change_sequence
    # Native object-visit control, not a fabricated cast or permission.
    player.exile.remove(bolt); player.graveyard.append(bolt)
    card.move_to_zone(Zone.GRAVEYARD)
    player.graveyard.remove(bolt); player.exile.append(bolt)
    card.move_to_zone(Zone.EXILE)
    assert card.zone_change_sequence == original_sequence + 2
    assert not ordinary_exile_permission(state, seat, bolt)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'cast_spell', 'card_id': bolt, 'from_exile': True,
                         'targets': {'target_player': 3 - seat}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_iteration_keeps_legacy_this_turn_numeric_permission(seat):
    state = position(seat)
    state.mechanic_choice_players = {seat}
    cid = put(state, 'Expressive Iteration', seat)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': {}})
    assert state.stack[-1].payload['mana_spent'] == 2
    state = until(state, lambda s: s.pending_mechanic_choice is not None)
    options = state.pending_mechanic_choice['options']
    assert len(options) == 3
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': options})
    exiled = options[1]
    assert state.players[seat].exile_play_until[exiled] == state.turn
    assert ordinary_exile_permission(state, seat, exiled)
    state = deserialize_match_snapshot(json.loads(json.dumps(serialize_match_snapshot(state))))
    state = until(state, lambda s: s.turn > 5)
    assert not ordinary_exile_permission(state, seat, exiled)


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_duration_defaults_preserve_legacy_snapshot_shape(seat):
    state = position(seat)
    payload = json.loads(json.dumps(serialize_match_snapshot(state)))
    assert all('exile_play_durations' not in player for player in payload['players'].values())
    restored = deserialize_match_snapshot(payload)
    assert json.loads(json.dumps(serialize_match_snapshot(restored))) == payload


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_spell_program_keeps_its_controller_next_turn_duration(seat):
    state, _ = cast(position(seat), 'Light Up the Stage', seat)
    assert state.stack[-1].payload['play_duration'] == 'controller_next_turn'


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_pull_then_cremate_cannot_reuse_an_exile_object_visit(seat):
    from tests.test_causal_graveyard_return import RAW
    from tests.test_selected_graveyard_reference import raw_card as native_card

    state, _, bolt = grant(seat)
    for name in ('Plains', 'Swamp'):
        put(state, name, seat, Zone.BATTLEFIELD)
    sequence = state.cards[bolt].zone_change_sequence
    for name, expected in (('Pull from Eternity', Zone.GRAVEYARD), ('Cremate', Zone.EXILE)):
        source = native_card(state, RAW[name], seat, Zone.HAND).id
        state = act(state, seat, {'type': 'cast_spell', 'card_id': source,
                                 'targets': {'target_card_id': bolt}})
        assert state.stack[-1].payload['mana_spent'] == 1
        state = until(state, lambda s: not s.stack)
        assert state.cards[bolt].zone == expected
    assert state.cards[bolt].zone_change_sequence == sequence + 2
    assert not ordinary_exile_permission(state, seat, bolt)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'cast_spell', 'card_id': bolt, 'from_exile': True,
                         'targets': {'target_player': 3 - seat}})
    assert serialize_match_snapshot(state) == before


def scoped_grant(state, seat, name):
    land = put(state, 'Mountain', seat, Zone.LIBRARY)
    bolt = put(state, 'Lightning Bolt', seat, Zone.LIBRARY)
    top = [land, bolt]
    if name == 'Riveteers Charm':
        top.append(put(state, 'Mountain', seat, Zone.LIBRARY))
        put(state, 'Swamp', seat, Zone.BATTLEFIELD)
        put(state, 'Forest', seat, Zone.BATTLEFIELD)
    player = state.players[seat]
    player.library = [cid for cid in player.library if cid not in top] + top
    if name == 'Riveteers Charm':
        from rules_engine.cast_choice import build_cast_hints
        source = put(state, name, seat)
        hints = build_cast_hints(state, state.cards[source], seat)
        mode = next(m for m in hints['modes'] if m.lower().startswith('exile the top '))
        state = act(state, seat, {'type': 'cast_spell', 'card_id': source,
                                 'targets': {'mode_text': mode}})
        assert state.stack[-1].payload['mana_spent'] == 3
    else:
        battlefield = list(player.battlefield)
        state, source = cast(state, name, seat)
        assert state.players[seat].battlefield == battlefield
        assert len(state.stack) == 1  # No casualty sacrifice or copied spell.
    assert state.cards[source].oracle_text == ROWS[name]['oracle_text']
    assert state.stack[-1].effect_key == 'exile_top_cards_playable'
    state = until(state, lambda s: not s.stack)
    assert all(cid in state.players[seat].exile for cid in top)
    return state, land, bolt


@pytest.mark.parametrize('seat', [1, 2])
def test_rob_paid_base_really_offers_and_plays_both_this_turn(seat):
    state, land, bolt = scoped_grant(position(seat), seat, 'Rob the Archives')
    assert state.turn == 5
    assert_offered_and_play(state, seat, land, bolt)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_rob_expires_at_current_cleanup_and_stays_denied_next_turn(seat, restore):
    state, land, bolt = scoped_grant(position(seat), seat, 'Rob the Archives')
    if restore:
        state = deserialize_match_snapshot(json.loads(json.dumps(serialize_match_snapshot(state))))
    state = until(state, lambda s: s.step == Step.CLEANUP and not s.cleanup_pending)
    assert state.turn == 5
    assert not ordinary_exile_permission(state, seat, land)
    assert not ordinary_exile_permission(state, seat, bolt)
    state = next_main(state, seat, 5)
    assert not ordinary_exile_permission(state, seat, land)
    assert not ordinary_exile_permission(state, seat, bolt)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('when', ['own_main', 'own_end', 'opponent_end'])
@pytest.mark.parametrize('restore', [False, True])
def test_charm_expiry_is_matching_end_step_entry_not_priority_pass(seat, when, restore):
    state = position(seat)
    if when != 'own_main':
        active = seat if when == 'own_end' else 3 - seat
        state = until(state, lambda s: s.step == Step.END_STEP and s.active_player == active
                      and s.priority_player == seat)
    grant_turn = state.turn
    state, land, bolt = scoped_grant(state, seat, 'Riveteers Charm')
    if restore:
        payload = json.loads(json.dumps(serialize_match_snapshot(state)))
        state = deserialize_match_snapshot(payload)
        assert json.loads(json.dumps(serialize_match_snapshot(state))) == payload
    assert ordinary_exile_permission(state, seat, bolt)
    if when == 'own_main':
        state = until(state, lambda s: s.step == Step.END_STEP)
        assert state.turn == grant_turn
    else:
        # A grant after the current entry must survive priority and cleanup.
        state = act(state, state.priority_player, {'type': 'pass_priority'})
        assert ordinary_exile_permission(state, seat, bolt)
        state = next_main(state, seat, grant_turn)
        assert ordinary_exile_permission(state, seat, bolt)
        state = until(state, lambda s: s.step == Step.END_STEP)
    assert state.active_player == seat
    assert not ordinary_exile_permission(state, seat, land)
    assert not ordinary_exile_permission(state, seat, bolt)
    assert not state.stack  # Expiration itself is not a counterable trigger.


@pytest.mark.parametrize('seat', [1, 2])
def test_charm_late_grant_uses_real_queued_own_extra_end_step(seat):
    state, _ = cast(position(seat), 'Time Warp', seat, {'target_player': seat})
    state = until(state, lambda s: not s.stack and s.step == Step.END_STEP and s.priority_player == seat)
    state, land, bolt = scoped_grant(state, seat, 'Riveteers Charm')
    state = next_main(state, seat, 5)
    assert state.turn == 6 and ordinary_exile_permission(state, seat, bolt)
    state = until(state, lambda s: s.step == Step.END_STEP)
    assert state.turn == 6 and state.active_player == seat
    assert not ordinary_exile_permission(state, seat, land)
    assert not ordinary_exile_permission(state, seat, bolt)


def test_unknown_duration_cannot_mutate_a_real_library_or_grant_permission():
    from effects.handlers import exile_top_cards_playable
    state = position(1)
    before = serialize_match_snapshot(state)
    with pytest.raises(ValueError, match='duration'):
        exile_top_cards_playable(state, 1, {'amount': 2, 'play_duration': 'unknown'})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('schema', [
    'Exile the top two cards of your library. You may play those cards until your next upkeep.',
    'Exile the top two cards of your library. Until the end of your next turn, you may play those cards. Draw seven cards.',
])
def test_unknown_complete_program_has_diagnostic_not_a_supported_prefix(schema):
    # Negative grammar inputs, not fabricated canonical cards or game effects.
    from rules_engine.oracle_effects import compile_exile_play_instruction
    result = compile_exile_play_instruction(schema)
    assert result.get('__unsupported_exile_play_duration')
    assert 'play_duration' not in result
    from rules_engine.oracle_effects import _infer_clause_effect
    state = position(1)
    source = put(state, 'Light Up the Stage', 1)
    before = serialize_match_snapshot(state)
    clause = _infer_clause_effect(state, state.cards[source], 1, schema.lower(), {}, 0)
    assert clause[0] == 'noop' and clause[1].get('__unsupported_exile_play_duration')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_charm_paid_main_grant_reaches_native_spell_and_land_provider(seat):
    state, land, bolt = scoped_grant(position(seat), seat, 'Riveteers Charm')
    assert_offered_and_play(state, seat, land, bolt)
