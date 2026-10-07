"""Full canonical paid Fable: deliberate counted choices, no injected stack/events."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.linked_discard import linked_discard_effect, linked_discard_gaps
from training.environment import TrainingEnvironment


FIXTURES = Path(__file__).parent / 'fixtures'
DIRECTORY = FIXTURES / 'fable_optional_linked_discard'
FABLE = json.loads((DIRECTORY / 'fable.json').read_text())
ROWS = {row['name']: row for row in json.loads((FIXTURES / 'linked_discard.json').read_text())}
ROWS[FABLE['name']] = FABLE
NATURALIZE = json.loads((FIXTURES / 'soulscar_protection_boundaries/naturalize.json').read_text())
ROWS[NATURALIZE['name']] = NATURALIZE
BODY = 'You may discard up to two cards. If you do, draw that many cards.'


def snap(state):
    return serialize_match_snapshot(state)


def restored(state):
    before = snap(state)
    result = deserialize_match_snapshot(before)
    assert snap(result) == before
    return result


def act(state, seat, action):
    before = snap(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert snap(state) == before
    return result


def add(state, name, seat, zone=Zone.HAND):
    raw = ROWS.get(name) or fallback_card_payload(name)
    assert raw and (raw.get('oracle_text') is not None or raw.get('card_faces'))
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 1}], [], seed=7107)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card.id


def position(seat):
    raw = fallback_card_payload('Mountain')
    deck = [{**raw, 'card_name': 'Mountain', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=7107)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    # Explicit initial rules-fixture resources; never a natural-game claim.
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {}
    for owner in (1, 2):
        for name in ('Mountain',) * 4 + ('Forest',) * 2:
            add(state, name, owner, Zone.BATTLEFIELD)
    return state


def pass_once(state):
    return act(state, state.priority_player, {'type': 'pass_priority'})


def cast(state, seat, cid, targets=None):
    if state.priority_player != seat:
        state = pass_once(state)
    before_tapped = sum(state.cards[cid].tapped for cid in state.players[seat].battlefield)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid,
                             'targets': targets or {}, 'cost_choice': {'id': 'base'}})
    assert state.cards[cid].zone == Zone.STACK
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield) > before_tapped
    return restored(state)


def episode(seat, hand_count=3, before_resolve=None):
    state = position(seat)
    fable = add(state, FABLE['name'], seat)
    state = cast(state, seat, fable)
    for _ in range(16):
        if not state.stack:
            break
        state = pass_once(state)
    assert state.cards[fable].zone == Zone.BATTLEFIELD
    assert state.cards[fable].counters['__lore'] == 1
    assert any(state.cards[cid].is_token and state.cards[cid].name == 'Goblin Shaman'
               for cid in state.players[seat].battlefield)
    for _ in range(120):
        if any(item.source_card_id == fable and item.payload.get('__chapter_number') == 2
               for item in state.stack):
            break
        assert not state.pending_mechanic_choice
        state = pass_once(state)
    else:
        raise AssertionError('Chapter II was not reached through real priority/turn progression')
    assert state.active_player == seat and state.step == Step.PRECOMBAT_MAIN
    # Establish the chapter's current hand after the genuine draw step.
    while len(state.players[seat].hand) > hand_count:
        cid = state.players[seat].hand.pop()
        state.cards[cid].move_to_zone(Zone.LIBRARY)
        state.players[seat].library.append(cid)
    while len(state.players[seat].hand) < hand_count:
        add(state, 'Island', seat)
    if before_resolve:
        state = before_resolve(state, fable)
    hand = list(state.players[seat].hand)
    opposing_hand = list(state.players[3-seat].hand)
    before_draw = state.draws_this_turn.get(seat, 0)
    for _ in range(8):
        if state.pending_mechanic_choice or not state.stack:
            break
        state = pass_once(state)
    pending = state.pending_mechanic_choice
    if not hand_count:
        assert pending is None and not state.stack
        assert state.players[seat].hand == []
        assert state.players[3-seat].hand == opposing_hand
        assert state.draws_this_turn.get(seat, 0) == before_draw
        return restored(state), fable, hand, opposing_hand, before_draw
    assert pending and pending['kind'] == 'discard' and pending['player_id'] == seat
    assert pending['min_count'] == 0 and pending['count'] == min(2, hand_count)
    assert pending['options'] == hand
    assert state.players[3-seat].hand == opposing_hand
    return restored(state), fable, hand, opposing_hand, before_draw


def choose(state, seat, ids, wholeview=False):
    action = {'type': 'choose_mechanic', 'card_ids': ids}
    if wholeview:
        env = TrainingEnvironment()
        env._state = state
        view = RulesEngine().legal_moves(state, seat)[0]
        result = env.lookup_intent({**view, 'card_ids': ids}, seat)
        assert snap(state) == snap(env._state)
        assert result is not None
    return act(state, seat, action)


def test_complete_raw_faces_and_provenance_before_execution():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    for row in provenance['sources']:
        assert hashlib.sha256((Path(__file__).parents[1] / row['path']).read_bytes()).hexdigest() == row['sha256']
    assert FABLE['object'] == 'card' and FABLE['layout'] == 'transform'
    assert len(FABLE['card_faces']) == 2
    assert BODY in FABLE['card_faces'][0]['oracle_text']
    assert fallback_card_payload('Fable of the Mirror-Breaker')['card_faces'] == FABLE['card_faces'] or all(
        fallback_card_payload('Fable of the Mirror-Breaker')['card_faces'][i]['oracle_text'] == face['oracle_text']
        for i, face in enumerate(FABLE['card_faces']))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('hand_count,selected_count', [(1, 0), (1, 1), (2, 0), (2, 1), (2, 2), (3, 2)])
def test_paid_chapter_deliberate_identity_and_exact_count(seat, hand_count, selected_count):
    state, fable, hand, opposing, draws = episode(seat, hand_count)
    selected = hand[-selected_count:] if selected_count else []
    state = choose(state, seat, selected, wholeview=True)
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[fable].zone == Zone.BATTLEFIELD
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in selected)
    assert all(cid in state.players[seat].hand for cid in hand if cid not in selected)
    assert len(state.players[seat].hand) == hand_count
    assert state.draws_this_turn.get(seat, 0) - draws == selected_count
    assert state.players[3-seat].hand == opposing
    assert restored(state).discards_this_turn.get(seat, 0) == selected_count


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_eligible_cards_never_discards_opponents_hand(seat):
    state, fable, _, opposing, draws = episode(seat, 0)
    assert not state.pending_mechanic_choice
    assert state.players[3-seat].hand == opposing
    assert state.draws_this_turn.get(seat, 0) == draws
    assert state.cards[fable].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_owned_training_view_and_wrong_actor_do_not_expose_choices(seat):
    state, _, hand, _, _ = episode(seat)
    env = TrainingEnvironment()
    env._state = state
    before = snap(state)
    actor = env.observe(seat)
    other = env.observe(3-seat)
    assert actor['players'][str(seat)]['hand'] == hand
    assert 'hand' not in other['players'][str(seat)]
    assert all(cid not in other['known_cards'] for cid in hand)
    assert 'prompts' not in other['pending_choice']
    assert RulesEngine().legal_moves(state, 3-seat) == []
    assert snap(state) == before
    with pytest.raises(ActionRejected):
        env.lookup_intent({**RulesEngine().legal_moves(state, seat)[0], 'card_ids': []}, 3-seat)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['duplicate', 'too_many', 'foreign', 'stale', 'wrong_actor'])
def test_actual_choice_rejections_are_root_atomic(seat, invalid):
    state, _, hand, opposing, _ = episode(seat)
    actor = seat
    ids = hand[:1]
    if invalid == 'duplicate':
        ids *= 2
    elif invalid == 'too_many':
        ids = hand
    elif invalid == 'foreign':
        ids = opposing[:1]
    elif invalid == 'stale':
        cid = hand[0]
        state.players[seat].hand.remove(cid)
        state.cards[cid].move_to_zone(Zone.GRAVEYARD)
        state.players[seat].graveyard.append(cid)
    else:
        actor = 3-seat
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, actor, {'type': 'choose_mechanic', 'card_ids': ids})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_source_departure_does_not_change_choice_controller(seat):
    def departure(state, fable):
        source = add(state, 'Naturalize', 3-seat)
        state = cast(state, 3-seat, source, {'target_card_id': fable})
        state = pass_once(pass_once(state))
        assert state.cards[fable].zone == Zone.GRAVEYARD
        return restored(state)
    state, fable, hand, opposing, draws = episode(seat, before_resolve=departure)
    state = choose(state, seat, [hand[-1]])
    assert state.cards[fable].zone == Zone.GRAVEYARD
    assert state.draws_this_turn.get(seat, 0) - draws == 1
    assert state.players[3-seat].hand == opposing


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('replacement', ['discard_exile', 'dredge'])
def test_genuine_replacement_continuation_after_counted_discard(seat, replacement):
    def install(state, _):
        add(state, 'Leyline of the Void', 3-seat, Zone.BATTLEFIELD) if replacement == 'discard_exile' else add(
            state, 'Stinkweed Imp', seat, Zone.GRAVEYARD)
        return state
    state, fable, hand, opposing, draws = episode(seat, before_resolve=install)
    state = choose(state, seat, hand[-2:])
    if replacement == 'dredge':
        for _ in range(2):
            assert state.pending_mechanic_choice['kind'] == 'draw'
            state = restored(state)
            state = act(state, seat, {'type': 'choose_mechanic', 'choice_id': 'draw'})
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[fable].zone == Zone.BATTLEFIELD
    assert state.draws_this_turn.get(seat, 0) - draws == 2
    assert all(state.cards[cid].zone == (Zone.EXILE if replacement == 'discard_exile' else Zone.GRAVEYARD)
               for cid in hand[-2:])
    assert state.players[3-seat].hand == opposing
    assert restored(state).discards_this_turn[seat] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_chapter_one_and_final_face_continue_unchanged(seat):
    state, fable, _, _, _ = episode(seat, 1)
    state = choose(state, seat, [])
    for _ in range(120):
        if state.cards[fable].selected_face_index == 1:
            break
        state = pass_once(state)
    assert state.cards[fable].name == 'Reflection of Kiki-Jiki'
    assert state.cards[fable].zone == Zone.BATTLEFIELD
    assert state.cards[fable].counters == {} and state.cards[fable].summoning_sick
    assert restored(state).cards[fable].selected_face_index == 1


@pytest.mark.parametrize('count', ['one', 'two', 'three', '7'])
def test_complete_generic_optional_body_reuses_exact_existing_descriptor(count):
    result = linked_discard_effect(f'You may discard up to {count} cards. If you do, draw that many cards.')
    assert result == linked_discard_effect(f'Discard up to {count} cards, then draw that many cards.')
    assert result is not None
    assert linked_discard_gaps(f'You may discard up to {count} cards. If you do, draw that many cards.') == []


@pytest.mark.parametrize('body', [
    BODY + ' Gain 2 life.', BODY.replace('that many', 'two'),
    BODY.replace('You may', 'Target player may'), BODY.replace('If you do', 'If you control an artifact'),
    BODY.replace('draw that many cards.', 'draw that many cards unless an opponent pays {1}.'),
])
def test_unknown_suffix_recipient_condition_or_linkage_not_partially_admitted(body):
    # Compiler-only negative strings, never assigned to playable fake cards.
    assert linked_discard_effect(body) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['options', 'effect_controller', 'followup_effect', 'unknown_alias'])
def test_full_choice_view_tampering_fails_before_mutation(seat, field):
    state, _, _, _, _ = episode(seat)
    env = TrainingEnvironment()
    env._state = state
    before = snap(state)
    view = deepcopy(RulesEngine().legal_moves(state, seat)[0])
    if field == 'options':
        view[field] = []
    elif field == 'effect_controller':
        view[field] = 3-seat
    elif field == 'followup_effect':
        view[field]['payload']['amount'] = 99
    else:
        view[field] = {'card_ids': []}
    view['card_ids'] = []
    with pytest.raises(ActionRejected):
        env.lookup_intent(view, seat)
    assert snap(state) == before


@pytest.mark.parametrize('prefix', ['I', 'II', 'I, II'])
def test_exact_complete_chapter_envelope_and_body_share_admission(prefix):
    text = prefix + ' — ' + BODY
    assert linked_discard_effect(text) == linked_discard_effect(BODY)
    assert linked_discard_gaps(text) == []
    assert linked_discard_effect(text + ' Gain 2 life.') is None
    assert linked_discard_gaps(text + ' Gain 2 life.') == ['linked discard sequence fidelity']


def test_preimport_guard_denies_native_public_and_dbapi_sqlite_aliases():
    import _socket
    import _sqlite3
    import sqlite3
    for probe in (lambda: sqlite3.dbapi2.connect(':memory:'),
                  lambda: sqlite3.Connection(':memory:'),
                  lambda: _sqlite3.Connection(':memory:'),
                  lambda: _socket.socket.__new__(_socket.socket)):
        with pytest.raises(RuntimeError, match='SQL/socket denied'):
            probe()
