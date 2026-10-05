"""DB-free canonical activated inspections, including the zero-hit UX contract."""
import json
import random
from copy import deepcopy
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from api_contracts import ActionRequest
from effects.registry import resolve_effect
from game_state.observations import remembered_hand_card
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, MatchState, PlayerState, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.draw_restrictions import can_draw_card
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.stack_engine import add_to_stack


FIXTURES = Path(__file__).parent / 'fixtures/activated_top_selection'
ENGINE = RulesEngine()


def card(state, name, seat, zone=Zone.LIBRARY):
    raw = json.loads((FIXTURES / (name + '.json')).read_text())
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 8}], [], seed=17)
    instance = deepcopy(next(iter(sample.cards.values())))
    instance.id = state.allocate_object_id()
    instance.owner = instance.controller = seat
    instance.image_uri = raw.get('image_uris', {}).get('normal')
    instance.move_to_zone(zone)
    state.cards[instance.id] = instance
    getattr(state.players[seat], zone.value).append(instance.id)
    return instance


def position(seat, names=('savannah-lions', 'militia-bugler', 'serra-angel', 'opt'), prefix=True):
    state = MatchState(id='activated-inspection-test', cards={}, stack=[], players={
        pid: PlayerState(id=pid, name=f'P{pid}') for pid in (1, 2)})
    state.rng = random.Random(617)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    source = card(state, 'recruitment-officer', seat, Zone.BATTLEFIELD)
    outside = [card(state, name, seat).id for name in ('forest', 'llanowar-elves')] if prefix else []
    top = [card(state, name, seat).id for name in names]
    card(state, 'forest', 3-seat)
    state.players[seat].mana_pool = {'W': 1, 'C': 3}
    return state, source, outside, top


def api_action(state, seat, action):
    request = ActionRequest.model_validate({'player_id': seat, 'action': action})
    return checked_action(state, ENGINE, seat, request.action.model_dump(exclude_none=True))


def activate(state, source, seat):
    return api_action(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0})


def resolve_activation(state):
    for _ in range(2):
        state = api_action(state, state.priority_player, {'type': 'pass_priority'})
    return state


def choose(state, seat, ids):
    return api_action(state, seat, {'type': 'choose_mechanic', 'card_ids': ids})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('chosen_index', [0, 1, None])
def test_canonical_paid_activation_selection_or_decline_after_restart(seat, chosen_index):
    state, source, outside, top = position(seat)
    source.tapped = source.summoning_sick = True  # No tap symbol in this cost.
    move = next(m for m in ENGINE.legal_moves(state, seat) if m['type'] == 'activate_ability')
    assert move['mana_cost'] == '{3}{W}'
    assert not any(cid in json.dumps(move) for cid in outside + top)
    original_library = list(state.players[seat].library)
    state = activate(state, source, seat)
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.players[seat].library == original_library and not state.players[seat].hand
    assert state.stack[-1].effect_key == 'topdeck_reveal_creature_to_hand'
    assert state.stack[-1].payload['mv_max'] == 3
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve_activation(state)
    pending = state.pending_mechanic_choice
    assert pending['options'] == top[:2] + ['__none__']
    assert pending['inspected_card_ids'] == list(reversed(top))
    assert pending['bottom_random'] and not pending['bottom_any_order']
    assert state.players[seat].library == original_library
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert ENGINE.legal_moves(state, 3-seat) == []
    move = ENGINE.legal_moves(state, seat)[0]
    assert [c['id'] for c in move['inspected_cards']] == list(reversed(top))
    assert [c['name'] for c in move['inspected_cards']] == [state.cards[cid].name for cid in reversed(top)]
    assert set(move['options']) == set(top[:2] + ['__none__'])
    chosen = top[chosen_index] if chosen_index is not None else None
    remainder = [cid for cid in top if cid != chosen]
    expected_rng = random.Random()
    expected_rng.setstate(state.rng.getstate())
    expected_rng.shuffle(remainder)
    state = choose(state, seat, [chosen or '__none__'])
    assert state.players[seat].hand == ([chosen] if chosen else [])
    assert state.players[seat].library == remainder + outside
    assert state.rng.getstate() == expected_rng.getstate()
    assert not state.pending_mechanic_choice and not state.stack and not state.trigger_staging
    assert state.draws_this_turn[seat] == 0
    assert not state.failed_draw_players
    assert source.id in state.players[seat].battlefield
    for cid in top:
        known = remembered_hand_card(state, 3-seat, state.cards[cid])
        assert bool(known) == (cid == chosen)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('size', [0, 1, 2, 3, 4])
def test_zero_eligible_retains_private_inspection_until_acknowledged(seat, size):
    names = ('opt', 'serra-angel', 'forest', 'opt')[:size]
    state, source, _, top = position(seat, names, prefix=False)
    before_draws = dict(state.draws_this_turn)
    state = resolve_activation(activate(state, source, seat))
    if not size:
        assert state.pending_mechanic_choice is None and not state.failed_draw_players
        return
    assert state.players[seat].library == top and not state.players[seat].hand
    assert state.pending_mechanic_choice['options'] == ['__none__']
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    legal = ENGINE.legal_moves(state, seat)
    assert [row['id'] for row in legal[0]['inspected_cards']] == list(reversed(top))
    assert legal[0]['option_labels']['__none__'] == 'Acknowledge inspected cards'
    assert not ENGINE.legal_moves(state, 3-seat)
    _, private_moves = decision_view(state, seat, legal)
    assert len(private_moves[0]['inspected_cards']) == size
    opponent_view, opponent_moves = decision_view(state, 3-seat, [])
    assert opponent_moves == []
    assert all(not opponent_view.cards[cid].name for cid in top)
    assert not any(state.cards[cid].name in json.dumps(state.pending_mechanic_choice) for cid in top)
    state = choose(state, seat, ['__none__'])
    assert not state.pending_mechanic_choice and not state.players[seat].hand
    assert set(state.players[seat].library) == set(top)
    assert state.draws_this_turn == before_draws
    assert all(cid not in state.card_observations.get(3-seat, {}) for cid in top)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pool', [{'C': 4}, {'W': 1, 'C': 2}, {'R': 4}, {}])
def test_wrong_or_insufficient_cost_is_atomic(seat, pool):
    state, source, _, _ = position(seat)
    state.players[seat].mana_pool = pool
    before = serialize_match_snapshot(state)
    assert not any(m['type'] == 'activate_ability' for m in ENGINE.legal_moves(state, seat))
    with pytest.raises(ActionRejected):
        activate(state, source, seat)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['outside', 'noncreature', 'above_threshold', 'duplicate', 'multiple', 'empty', 'opponent', 'stale'])
def test_invalid_choice_is_atomic(seat, invalid):
    state, source, outside, top = position(seat)
    state = resolve_activation(activate(state, source, seat))
    ids = {'outside': [outside[-1]], 'noncreature': [top[3]], 'above_threshold': [top[2]],
           'duplicate': [top[0], top[0]], 'multiple': top[:2], 'empty': [],
           'opponent': [top[0]], 'stale': [top[0]]}[invalid]
    if invalid == 'stale':
        state.players[seat].library[-2:] = reversed(state.players[seat].library[-2:])
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choose(state, 3-seat if invalid == 'opponent' else seat, ids)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('step', [Step.UPKEEP, Step.DECLARE_BLOCKERS, Step.END_STEP])
def test_instant_timing_on_opponents_turn_and_stack_response(seat, step):
    state, source, _, _ = position(seat)
    state.active_player = 3-seat
    state.step = step
    add_to_stack(state, source.id, 3-seat, 'Existing ability', 'noop', {}, is_spell=False)
    state.priority_player = seat
    assert any(m['type'] == 'activate_ability' for m in ENGINE.legal_moves(state, seat))
    state = activate(state, source, seat)
    assert len(state.stack) == 2 and state.stack[-1].controller == seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('eligible', [True, False])
def test_actual_bounded_ai_activates_and_completes_private_choice(seat, eligible):
    names = ('savannah-lions', 'militia-bugler', 'serra-angel', 'opt') if eligible else ('forest', 'opt', 'serra-angel', 'forest')
    state, source, _, top = position(seat, names)
    ai = AIAgent(difficulty='strong', archetype='Midrange')
    before = serialize_match_snapshot(state)
    decision = ai.choose_action(state, ENGINE.legal_moves(state, seat), seat).action
    assert serialize_match_snapshot(state) == before
    assert decision['type'] == 'activate_ability' and decision['card_id'] == source.id
    state = checked_action(state, ENGINE, seat, decision)
    state = resolve_activation(state)
    decision = ai.choose_action(state, ENGINE.legal_moves(state, seat), seat).action
    assert decision['type'] == 'choose_mechanic'
    assert decision['card_ids'][0] in top[:2] if eligible else decision['card_ids'] == ['__none__']
    state = api_action(state, seat, decision)
    assert state.pending_mechanic_choice is None
    assert len(state.players[seat].hand) == int(eligible)
    assert sum(state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_power_filter_and_shared_choice_continuation(seat):
    state, _, outside, top = position(seat)
    bugler = card(state, 'militia-bugler', seat, Zone.BATTLEFIELD)
    key, payload = infer_effect_from_oracle(state, bugler, seat)
    assert payload['power_max'] == 2 and 'mv_max' not in payload
    resolve_effect(state, seat, 'effect_sequence', {'effects': [
        {'effect_key': key, 'payload': payload},
        {'effect_key': 'gain_life', 'payload': {'amount': 3, 'target_player': seat}},
    ]})
    assert state.players[seat].life == 20
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, seat, [top[0]])
    assert state.players[seat].life == 23
    assert state.players[seat].library[-len(outside):] == outside


@pytest.mark.parametrize('seat', [1, 2])
def test_any_order_payload_uses_existing_bottom_order_choice_and_resume(seat):
    state, _, outside, top = position(seat)
    resolve_effect(state, seat, 'effect_sequence', {'effects': [
        {'effect_key': 'topdeck_reveal_creature_to_hand', 'payload': {
            'top_n': 4, 'mv_max': 3, 'optional': True, 'bottom_any_order': True}},
        {'effect_key': 'gain_life', 'payload': {'amount': 3, 'target_player': seat}},
    ]})
    state = choose(state, seat, ['__none__'])
    assert state.pending_mechanic_choice['kind'] == 'topdeck_bottom_order'
    assert state.players[seat].life == 20
    order = list(reversed(top))
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choose(state, seat, order[:-1])
    assert serialize_match_snapshot(state) == before
    state = choose(state, seat, order)
    assert state.players[seat].library == order + outside
    assert state.players[seat].life == 23 and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('size', [1, 2, 3])
def test_short_library_can_select_its_only_qualifying_card(seat, size):
    state, source, _, top = position(seat, ('savannah-lions', 'forest', 'opt')[:size], prefix=False)
    state = resolve_activation(activate(state, source, seat))
    assert state.pending_mechanic_choice['options'] == [top[0], '__none__']
    state = choose(state, seat, [top[0]])
    assert state.players[seat].hand == [top[0]]
    assert set(state.players[seat].library) == set(top[1:])
    assert not state.failed_draw_players


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_look_is_not_limited_by_narset_draw_restriction(seat):
    state, source, _, top = position(seat)
    card(state, 'narset-parter-of-veils', 3-seat, Zone.BATTLEFIELD)
    state.draws_this_turn[seat] = 1
    assert not can_draw_card(state, seat)
    state = choose(resolve_activation(activate(state, source, seat)), seat, [top[1]])
    assert state.players[seat].hand == [top[1]]
    assert state.draws_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_payment_uses_three_generic_and_one_white_land(seat):
    state, source, _, top = position(seat)
    state.players[seat].mana_pool = {}
    lands = [card(state, name, seat, Zone.BATTLEFIELD) for name in ('forest', 'forest', 'forest', 'plains')]
    state = activate(state, source, seat)
    assert all(state.cards[land.id].tapped for land in lands)
    assert not state.cards[source.id].tapped
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.players[seat].library[-4:] == top


@pytest.mark.parametrize('top_n,mv_max', [(1, 1), (2, 5), (3, 3), (6, 1)])
def test_shared_filter_is_bounded_by_payload_not_officer_or_full_library(top_n, mv_max):
    state, _, _, _ = position(1)
    library = list(state.players[1].library)
    viewed = library[-top_n:]
    resolve_effect(state, 1, 'topdeck_reveal_creature_to_hand', {
        'top_n': top_n, 'mv_max': mv_max, 'optional': True, 'bottom_random': True})
    move = ENGINE.legal_moves(state, 1)[0]
    assert [row['id'] for row in move['inspected_cards']] == list(reversed(viewed))
    from rules_engine.mana import mana_value
    expected = [cid for cid in viewed if 'Creature' in state.cards[cid].types
                and mana_value(state.cards[cid].mana_cost) <= mv_max]
    assert move['options'] == expected + ['__none__']
    state = choose(state, 1, [expected[0] if expected else '__none__'])
    assert state.players[1].library[len(viewed) - bool(expected):] == library[:-top_n]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['impulse', 'memory-deluge'])
def test_shared_draw_selection_inspection_contract_still_resumes(seat, name):
    state, _, outside, top = position(seat)
    spell = card(state, name, seat, Zone.HAND)
    key, payload = infer_effect_from_oracle(state, spell, seat)
    assert key == 'look_top_select_hand'
    resolve_effect(state, seat, key, {**payload, 'mana_spent_to_cast': 4})
    count = 1 if name == 'impulse' else 2
    move = ENGINE.legal_moves(state, seat)[0]
    assert len(move['inspected_cards']) == 4 and move['count'] == count
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, seat, top[:count])
    assert all(cid in state.players[seat].hand for cid in top[:count])
    assert state.players[seat].library[-len(outside):] == outside
    if name == 'impulse':
        assert state.pending_mechanic_choice['kind'] == 'topdeck_bottom_order'
        order = list(reversed(top[count:]))
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = choose(state, seat, order)
        assert state.players[seat].library == order + outside
    assert not state.pending_mechanic_choice
    assert state.draws_this_turn[seat] == 0


def test_generic_frontend_inspector_and_acknowledgement_are_not_name_special_cases():
    root = Path(__file__).parents[2]
    controls = (root / 'frontend/src/components/Controls.tsx').read_text()
    assert 'mechanicMove.inspected_cards.map' in controls
    assert 'Privately inspected cards' in controls
    assert 'mechanicMove.options[0] === "__none__"' in controls
    assert 'Recruitment Officer' not in controls
    assert 'inspected_cards?: CardView[]' in (root / 'frontend/src/types/index.ts').read_text()
