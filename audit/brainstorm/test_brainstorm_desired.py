"""Canonical paid continuation baseline; no production changes or injected events."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle

ROWS = {r['name']: r for r in (json.loads(p.read_text()) for p in
        (Path(__file__).parent / 'fixtures').glob('*.json'))}
RULES = RulesEngine()

def add(state, name, seat, zone):
    row = ROWS[name]
    sample = MatchFactory.from_decks([{**row, 'card_name': name, 'quantity': 1}], [], seed=4)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card.id

def position(seat):
    row = ROWS['Forest']
    deck = [{**row, 'card_name': row['name'], 'quantity': 30}]
    state = MatchFactory.from_decks(deck, deck, seed=4)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()
    return state

def act(state, seat, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RULES, seat, action)
    assert serialize_match_snapshot(state) == before
    return result

def cold(state):
    packet = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(json.loads(json.dumps(packet)))
    assert serialize_match_snapshot(result) == packet
    return result

def advance(state, predicate):
    for _ in range(64):
        if predicate(state):
            return state
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('actual priority boundary exceeded')

def cast(state, seat, cid, pool, targets=None):
    state.players[seat].mana_pool = pool
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid,
                             'cost_choice': {'id': 'base'}, 'targets': targets or {}})
    assert sum(state.players[seat].mana_pool.values()) == 0
    return state, next(i.id for i in state.stack if i.source_card_id == cid)

def brainstorm(state, seat):
    cid = add(state, 'Brainstorm', seat, Zone.HAND)
    hand = set(state.players[seat].hand) - {cid}
    library = list(state.players[seat].library)
    state, frame = cast(state, seat, cid, {'U': 1})
    state = advance(cold(state), lambda s: bool(s.pending_mechanic_choice) or
                    all(i.id != frame for i in s.stack))
    assert set(state.players[seat].hand) == hand | set(library[-3:])
    assert state.players[seat].library == library[:-3]
    assert state.pending_mechanic_choice, 'complete Brainstorm must offer put-two after draw-three'
    return cold(state), cid

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pair', [(0, 1), (1, 0), (2, 3), (3, 2)])
def test_paid_draw_three_then_explicit_ordered_put_two(seat, pair):
    state = position(seat)
    add(state, 'Counterspell', seat, Zone.HAND)
    state, source = brainstorm(state, seat)
    hand = list(state.players[seat].hand)
    chosen = [hand[index] for index in pair]
    before = len(state.players[seat].library)
    pending = state.pending_mechanic_choice
    assert pending['player_id'] == seat
    assert set(pending['options']) == set(hand)
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    assert not state.pending_mechanic_choice
    assert len(state.players[seat].library) == before + 2
    assert set(state.players[seat].library[-2:]) == set(chosen)
    assert not set(chosen) & set(state.players[seat].hand)
    assert state.cards[source].zone == Zone.GRAVEYARD
    cold(state)

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('select_returned', [False, True])
def test_real_hand_channel_return_then_private_brainstorm_choice(seat, select_returned):
    state = position(seat)
    source = add(state, 'Twinshot Sniper', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'R': 1}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source,
                'ability_index': 0, 'targets': {'target_player': 3-seat}})
    state = advance(state, lambda s: not s.stack)
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.players[3-seat].life == 18
    regrowth = add(state, 'Regrowth', seat, Zone.HAND)
    state, frame = cast(state, seat, regrowth, {'C': 1, 'G': 1}, {'target_card_id': source})
    state = advance(state, lambda s: all(i.id != frame for i in s.stack))
    assert state.cards[source].zone == Zone.HAND
    state, _ = brainstorm(cold(state), seat)
    others = [cid for cid in state.players[seat].hand if cid != source]
    selected = [source, others[0]] if select_returned else others[:2]
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': selected})
    assert (source in state.players[seat].library) is select_returned
    cold(state)

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_real_counterspell_prevents_both_instructions(seat, restore):
    state = position(seat)
    source = add(state, 'Brainstorm', seat, Zone.HAND)
    library = list(state.players[seat].library)
    state, frame = cast(state, seat, source, {'U': 1})
    state = act(state, seat, {'type': 'pass_priority'})
    counter = add(state, 'Counterspell', 3-seat, Zone.HAND)
    state, _ = cast(state, 3-seat, counter, {'U': 2}, {'target_stack_id': frame})
    state = advance(cold(state) if restore else state, lambda s: not s.stack)
    assert state.players[seat].library == library
    assert not state.pending_mechanic_choice
    assert state.cards[source].zone == Zone.GRAVEYARD

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['wrong-seat', 'unpaid'])
def test_invalid_cast_root_atomic(seat, bad):
    state = position(seat)
    source = add(state, 'Brainstorm', seat, Zone.HAND)
    state.players[seat].mana_pool = {} if bad == 'unpaid' else {'U': 1}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RULES, 3-seat if bad == 'wrong-seat' else seat,
                       {'type': 'cast_spell', 'card_id': source, 'targets': {}})
    assert serialize_match_snapshot(state) == before

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suffix', [' Then invent an unknown reward.', ' If an unspecified condition holds.'])
def test_unknown_complete_body_has_no_partial_reward(seat, suffix):
    # Explicit compiler negative; modified strings are not canonical gameplay fixtures.
    state = position(seat)
    source = add(state, 'Brainstorm', seat, Zone.HAND)
    state.cards[source].oracle_text += suffix
    key, payload = infer_effect_from_oracle(state, state.cards[source], seat, {})
    assert key == 'noop' and payload.get('__unsupported_instruction'), (key, payload)
