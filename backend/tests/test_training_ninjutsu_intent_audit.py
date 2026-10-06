"""Official full-card ninjutsu intake; sole unsupported rejection expectations."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from card_data.fallback_cards import fallback_card_payload
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from training.environment import TrainingEnvironment, encode_action, decode_action
from training.dataset import EpisodeAliases, canonical
from tests.test_training_choice_coverage import position, card
from tests.test_training_environment import resolve
from tests.test_linked_damage_targets import raw_card
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


FIXTURE = Path(__file__).parent / 'fixtures/ninjutsu_canonical/ninja-of-the-deep-hours.json'
PROVENANCE = json.loads(FIXTURE.with_name('ninja-of-the-deep-hours.provenance.json').read_bytes())
RAW = json.loads(FIXTURE.read_bytes())
assert sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['response_sha256']
assert RAW['object'] == 'card' and RAW['name'] == 'Ninja of the Deep Hours'


def scenario(seat, blocked=False, before_blocks=False):
    env = position(seat)
    state = env._state
    ninja = raw_card(state, RAW, seat, Zone.HAND)
    ninja.keywords = deepcopy(RAW['keywords'])
    for key in ('name', 'mana_cost', 'oracle_text', 'type_line', 'keywords'):
        assert getattr(ninja, key) == RAW[key]
    assert (ninja.power, ninja.toughness) == (int(RAW['power']), int(RAW['toughness']))
    attackers = [card(env, 'Grizzly Bears', seat, Zone.BATTLEFIELD) for _ in range(2)]
    lands = [raw_card(state, fallback_card_payload('Island'), seat, Zone.BATTLEFIELD).id
             for _ in range(2)]
    for cid in attackers:
        state.cards[cid].summoning_sick = False
    state.players[seat].mana_pool = {}
    state.step = Step.DECLARE_ATTACKERS
    env.step({'type': 'attack', 'attackers': attackers,
              'attack_targets': {cid: f'player:{3-seat}' for cid in attackers}})
    action = {'type': 'ninjutsu', 'card_id': ninja.id, 'return_card_id': attackers[1]}
    info = {'ninja': ninja.id, 'attackers': attackers, 'lands': lands}
    if before_blocks:
        return env, action, None, info
    for _ in range(4):
        if env._state.step == Step.DECLARE_BLOCKERS and not env._state.blockers_declared:
            break
        env.step({'type': 'pass_priority'})
    assert env._state.step == Step.DECLARE_BLOCKERS and not env._state.blockers_declared
    groups = {}
    if blocked:
        blocker = card(env, 'Grizzly Bears', 3-seat, Zone.BATTLEFIELD)
        groups[attackers[1]] = [blocker]
    env.step({'type': 'block', 'blocks': groups})
    assert env._state.blockers_declared and env.acting_seat == seat
    moves = env._rules.legal_moves(deepcopy(env._state), seat)
    hints = [move for move in moves if move['type'] == 'ninjutsu' and move['card_id'] == ninja.id]
    if blocked:
        assert {move['return_card_id'] for move in hints} == {attackers[0]}
        hint = None
    else:
        assert {move['return_card_id'] for move in hints} == set(attackers)
        hint = next(move for move in hints if move['return_card_id'] == attackers[1])
        assert hint['mana_cost'] == '{1}{U}'
    return env, action, hint, info


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field,value', [
    ('return_card_ids', ['not-the-chosen-return']), ('return_card_ids', None),
    ('targets', {'target_player': 1}), ('targets', None),
    ('cost_choice', {'id': 'requested-cost'}), ('cost_choice', None),
    ('resolving_item', {'source_card_id': 'requested-context'}), ('resolving_item', None),
])
def test_unsupported_ninjutsu_intent_fields_must_reject(game, seat, field, value):
    env, action, _, _ = scenario(seat)
    request = {**action, field: value}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ActionRejected):
        env.lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request, seat)
    finally:
        assert env.snapshot() == before and request == original


def assert_activation(state, seat, info):
    selected, untouched = info['attackers'][1], info['attackers'][0]
    assert selected in state.players[seat].hand and selected not in state.attackers
    assert untouched in state.attackers and untouched in state.players[seat].battlefield
    assert info['ninja'] in state.players[seat].hand
    assert len(state.stack) == 1 and state.stack[0].effect_key == 'ninjutsu'
    assert state.stack[0].payload['attack_target'] == f'player:{3-seat}'
    assert all(state.cards[cid].tapped for cid in info['lands'])
    assert sum(state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('whole_view', [False, True])
def test_independent_actual_selected_return_exact_payment_and_restart(game, seat, whole_view):
    env, action, hint, info = scenario(seat)
    before = env.snapshot()
    assert env.lookup_intent(hint if whole_view else action, seat) == env.lookup(action, seat)
    assert decode_action(encode_action(action)) == action
    assert env.snapshot() == before
    fork = TrainingEnvironment()
    fork.restore(before)
    assert env.step(encode_action(action)) == fork.step(action)
    assert env.snapshot() == fork.snapshot()
    assert_activation(env._state, seat, info)
    resolve(env)
    ninja = env._state.cards[info['ninja']]
    assert ninja.zone == Zone.BATTLEFIELD and ninja.tapped
    assert ninja.id in env._state.attackers
    assert env._state.attack_targets[ninja.id] == f'player:{3-seat}'
    client, match = game
    original = TrainingEnvironment()
    original.restore(before)
    identifier = retain(match, original)
    restart(identifier)
    public = next(move for move in client.get(
        f'/matches/{identifier}/legal-moves?player_id={seat}').json()['moves']
        if move['type'] == 'ninjutsu' and move['return_card_id'] == action['return_card_id'])
    assert public['card_view']['oracle_text'] == RAW['oracle_text']
    assert original.lookup_intent(public, seat) == original.lookup(action, seat)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    pending = restart(identifier)
    assert_activation(pending.state, seat, info)
    for _ in range(2):
        pending = restart(identifier)
        response = client.post(f'/matches/{identifier}/action', json={
            'player_id': pending.state.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    entered = restart(identifier)
    assert entered.state.cards[info['ninja']].zone == Zone.BATTLEFIELD
    assert entered.state.attack_targets[info['ninja']] == f'player:{3-seat}'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['blocked', 'timing', 'source_zone', 'foreign_return',
                                   'insufficient', 'missing', 'null', 'nested_alias'])
def test_independent_invalid_ninjutsu_choices_are_root_database_atomic(game, seat, fault):
    env, action, _, info = scenario(seat, blocked=fault == 'blocked', before_blocks=fault == 'timing')
    state = env._state
    if fault == 'source_zone':
        state.players[seat].hand.remove(info['ninja'])
        state.players[seat].graveyard.append(info['ninja'])
        state.cards[info['ninja']].move_to_zone(Zone.GRAVEYARD)
    elif fault == 'foreign_return':
        action['return_card_id'] = card(env, 'Grizzly Bears', 3-seat, Zone.BATTLEFIELD)
    elif fault == 'insufficient':
        state.players[seat].battlefield.remove(info['lands'][0])
        state.players[seat].hand.append(info['lands'][0])
        state.cards[info['lands'][0]].move_to_zone(Zone.HAND)
    elif fault == 'missing':
        del action['return_card_id']
    elif fault in {'null', 'nested_alias'}:
        action['return_card_id'] = None if fault == 'null' else {'id': info['attackers'][1]}
    before = env.snapshot()
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(action, seat)
        assert env.snapshot() == before
    client, match = game
    retain(match, env)
    assert rejected(client, match, action, seat).status_code == 422


@pytest.mark.parametrize('seat', [1, 2])
def test_independent_hidden_identity_permutation_and_no_return_inference(seat):
    env, action, hint, info = scenario(seat)
    assert info['ninja'] not in env.observe(3-seat)['known_cards']
    before = env.snapshot()
    public_input = canonical(EpisodeAliases().observation(env.observe(seat)))
    opponent = env._state.players[3-seat]
    first, second = opponent.hand[0], opponent.library[-1]
    env._state.cards[first], env._state.cards[second] = (
        deepcopy(env._state.cards[second]), deepcopy(env._state.cards[first]))
    env._state.cards[first].id, env._state.cards[second].id = first, second
    opponent.hand.reverse()
    opponent.library.reverse()
    assert canonical(EpisodeAliases().observation(env.observe(seat))) == public_input
    env.restore(before)
    incomplete = {key: value for key, value in hint.items() if key != 'return_card_id'}
    with pytest.raises(ActionRejected):
        env.lookup_intent(incomplete, seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_canonical_combat_damage_actual_optional_draw_and_http_restart(game, seat, accept):
    env, action, _, info = scenario(seat)
    env.step(action)
    resolve(env)
    resolve(env)
    assert env._state.step == Step.COMBAT_DAMAGE
    assert env._state.players[3-seat].life == 16
    assert len(env._state.stack) == 1
    assert env._state.stack[0].source_card_id == info['ninja']
    resolve(env)
    hint = next(move for move in env._rules.legal_moves(deepcopy(env._state), seat)
                if move['type'] == 'choose_optional_effect')
    selected = {'type': 'choose_optional_effect', 'stack_id': hint['stack_id'], 'accept': accept}
    before = env.snapshot()
    top = env._state.players[seat].library[-1]
    hand_count = len(env._state.players[seat].hand)
    assert top not in env.observe(seat)['known_cards']
    restored = TrainingEnvironment()
    restored.restore(before)
    assert env.step(encode_action(selected)) == restored.step(selected)
    assert env.snapshot() == restored.snapshot()
    assert len(env._state.players[seat].hand) == hand_count + int(accept)
    assert (top in env._state.players[seat].hand) == accept
    assert top not in env.observe(3-seat)['known_cards']
    client, match = game
    pending = TrainingEnvironment()
    pending.restore(before)
    identifier = retain(match, pending)
    restart(identifier)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': selected})
    assert response.status_code == 200, response.text
    result = restart(identifier)
    assert len(result.state.players[seat].hand) == hand_count + int(accept)
    assert (top in result.state.players[seat].hand) == accept


@pytest.mark.parametrize('seat', [1, 2])
def test_ninjutsu_pending_source_incarnation_does_not_move_reentered_card(seat):
    env, action, _, info = scenario(seat)
    env.step(action)
    state = env._state
    ninja = state.cards[info['ninja']]
    old_sequence = ninja.zone_change_sequence
    state.players[seat].hand.remove(ninja.id)
    ninja.move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(ninja.id)
    state.players[seat].exile.remove(ninja.id)
    ninja.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(ninja.id)
    assert ninja.zone_change_sequence > old_sequence
    restored = TrainingEnvironment()
    restored.restore(env.snapshot())
    resolve(env)
    resolve(restored)
    assert env.snapshot() == restored.snapshot()
    assert env._state.cards[ninja.id].zone == Zone.HAND
    assert ninja.id not in env._state.attackers
