"""Adapter qualification with existing canonical decks/cards, no live DB."""
from copy import deepcopy
import json

import pytest

from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from training import TrainingEnvironment, decode_action, encode_action


def env(seed=17, blue=False):
    result = TrainingEnvironment()
    result.reset('Blue Control' if blue else 'Mono Red Aggro',
                 'Mono Red Aggro' if blue else 'Blue Control', seed=seed)
    return result


def keep(environment):
    environment.step({'type': 'keep_hand'})
    environment.step({'type': 'keep_hand'})


def place(environment, name, seat, zone):
    """Retained tactical position using an existing instance, not a made-up card."""
    state = environment._state
    card = next(card for card in state.cards.values() if card.name == name and card.owner == seat)
    player = state.players[seat]
    for key in ('library', 'hand', 'battlefield', 'graveyard', 'exile'):
        ids = getattr(player, key)
        if card.id in ids:
            ids.remove(card.id)
    getattr(player, zone.value).append(card.id)
    card.move_to_zone(zone)
    card.tapped = False
    return card.id


def position(seat, spell='Lightning Bolt'):
    environment = env(blue=(seat == 2) if spell == 'Lightning Bolt' else (seat == 1))
    keep(environment)
    state = environment._state
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    cid = place(environment, spell, seat, Zone.HAND)
    place(environment, 'Mountain' if spell == 'Lightning Bolt' else 'Island', seat, Zone.BATTLEFIELD)
    return environment, cid


def cast(environment, cid, **targets):
    prompt = next(prompt['hint'] for prompt in environment.prompts()
                  if prompt['hint']['type'] == 'cast_spell' and prompt['hint']['card_id'] == cid)
    return {'type': 'cast_spell', 'card_id': cid, 'targets': targets,
            'cost_choice': {'id': prompt['cost_options'][0]['id']}}


def resolve(environment):
    environment.step({'type': 'pass_priority'})
    return environment.step({'type': 'pass_priority'})


def test_seed_reset_provenance_and_snapshot_are_deterministic():
    first, second = env(), env()
    assert first.observe(1) == second.observe(1)
    assert first.snapshot() == second.snapshot()
    original = first.snapshot()
    first.step({'type': 'mulligan'})
    first.reset(seed=17)
    assert first.snapshot() == original
    assert env(seed=18).snapshot() != original
    provenance = original['provenance']
    assert len(provenance['engine_hash']) == 64
    assert all(len(value) == 64 for value in provenance['deck_hashes'])
    assert len(original['state']['cards']) == 120


@pytest.mark.parametrize('seed', [False, None, '17', 1.0])
def test_explicit_seed_required(seed):
    environment = env()
    before = environment.snapshot()
    with pytest.raises(ValueError):
        environment.reset(seed=seed)
    assert environment.snapshot() == before


def test_no_custom_decks_or_uncanonical_metadata():
    environment = env()
    before = environment.snapshot()
    with pytest.raises(ValueError):
        environment.reset('Invented balanced deck', seed=1)
    assert environment.snapshot() == before


def test_encoding_preserves_ordered_variable_choices_and_targets():
    actions = [
        {'type': 'choose_mechanic', 'card_ids': ['p1-001', 'p1-005']},
        {'type': 'cast_spell', 'card_id': 'p1-001', 'targets': {
            'target_distribution': {'p2-001': 2, '2': 1},
            'mode_texts': ['mode 2', 'mode 1'],
            'mode_targets': {'mode 1': {'target_player': 2}, 'mode 2': {'target_card_id': 'p2-001'}},
        }},
    ]
    for action in actions:
        encoded = encode_action(action)
        assert encode_action(dict(reversed(list(action.items())))) == encoded
        assert encode_action(decode_action(encoded)) == encoded
    assert encode_action(actions[0]) != encode_action({**actions[0], 'card_ids': ['p1-005', 'p1-001']})
    with pytest.raises(ActionRejected):
        decode_action('mtg.action.v0:{}')
    with pytest.raises(ActionRejected):
        decode_action('mtg.action.v1:{ "type": "mulligan" }')


@pytest.mark.parametrize('action', [
    None, [], 3, {}, {'type': 'unknown'}, {'type': 'pass_priority', 'effect_payload': {}},
    {'type': 'keep_hand', 'bottom_card_ids': ['missing']},
    {'type': 'keep_hand', 'bottom_card_ids': ['p1-001', 'p1-001']},
    {'type': 'choose_mechanic'}, {'type': 'choose_mechanic', 'card_ids': [], 'choice_id': 'x'},
    {'type': 'cast_spell', 'card_id': 'missing', 'targets': {'target_player': True}},
    {'type': 'attack', 'attackers': 'p1-001'},
    'mtg.action.v1:{broken',
])
def test_malformed_illegal_actions_do_not_change_any_state(action):
    environment = env()
    before = environment.snapshot()
    assert environment.action_mask([action]) == [False]
    with pytest.raises(ActionRejected):
        environment.step(action)
    assert environment.snapshot() == before


@pytest.mark.parametrize('seat', [True, 0, 3, '1', 2])
def test_wrong_seat_is_rejected_without_change(seat):
    environment = env()
    before = environment.snapshot()
    with pytest.raises(ActionRejected):
        environment.step({'type': 'keep_hand'}, seat)
    assert environment.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_both_seats_hidden_information_invariance(seat):
    environment = env()
    keep(environment)
    environment._state.priority_player = seat
    before_observation = environment.observe(seat)
    before_prompts = environment.prompts(seat)
    before_actions = environment.simple_actions()
    snapshot = environment.snapshot()
    environment.observe(seat)
    environment.prompts(seat)
    environment.action_mask([{'type': 'pass_priority'}, {'type': 'keep_hand'}], seat)
    assert environment.snapshot() == snapshot
    state = environment._state
    hidden = state.players[3-seat].hand + state.players[1].library + state.players[2].library
    # Exchange existing canonical card identities while retaining opaque IDs/zone counts.
    for zone_ids in (state.players[3-seat].hand, state.players[1].library, state.players[2].library):
        a, b = zone_ids[:2]
        one, two = deepcopy(state.cards[a]), deepcopy(state.cards[b])
        one.id, two.id = b, a
        state.cards[a], state.cards[b] = two, one
    state.players[1].library.reverse()
    state.players[2].library.reverse()
    state.starting_decks[3-seat] = deepcopy(state.starting_decks[seat])
    state.rng.random()
    state.log.append('Private replay contains hidden card names')
    assert environment.observe(seat) == before_observation
    assert environment.prompts(seat) == before_prompts
    assert environment.simple_actions() == before_actions
    observed = environment.observe(seat)
    assert not set(hidden).intersection(observed['known_cards'])
    assert 'hand' not in observed['players'][str(3-seat)]
    assert 'library' not in observed['players']['1']
    assert not {'rng_state', 'log', 'starting_decks', 'provenance'}.intersection(observed)


def test_mulligan_owned_pending_choices_round_trip_rng_and_order():
    first, second = env(), env()
    for environment in (first, second):
        environment.step({'type': 'mulligan'})
    restored = TrainingEnvironment()
    restored.restore(json.loads(json.dumps(first.snapshot())))
    assert restored.snapshot() == first.snapshot()
    for environment in (first, second, restored):
        environment.step({'type': 'mulligan'})
    for seat in (1, 2):
        options = first.prompts()[0]['hint']['options']
        assert first.acting_seat == seat
        assert first.prompts(3-seat) == []
        assert first.prompts()[0]['required_choices']
        before = first.snapshot()
        with pytest.raises(ActionRejected):
            first.step({'type': 'choose_mechanic', 'card_ids': []})
        assert first.snapshot() == before
        action = {'type': 'choose_mechanic', 'card_ids': options[-1:]}
        outputs = [environment.step(action) for environment in (first, second, restored)]
        assert outputs[0] == outputs[1] == outputs[2]
    assert first.snapshot() == second.snapshot() == restored.snapshot()
    assert first.observe(1)['players']['1']['hand_count'] == 6


@pytest.mark.parametrize('seat', [1, 2])
def test_real_bolt_priority_mask_actual_win_and_terminal_restore(seat):
    environment, cid = position(seat)
    environment._state.players[3-seat].life = 3
    action = cast(environment, cid, target_player=3-seat)
    proposals = [action, {**action, 'targets': {}}, {**action, 'card_id': 'missing'}]
    before = environment.snapshot()
    assert environment.action_mask(proposals) == [True, False, False]
    assert environment.snapshot() == before
    expected = checked_action(environment._state, RulesEngine(), seat, action)
    result = environment.step(environment.lookup(action)['id'])
    assert environment._state.players[seat].mana_pool == expected.players[seat].mana_pool
    assert environment._state.stack[0].payload == expected.stack[0].payload
    assert not result['terminated'] and result['rewards'] == {1: 0, 2: 0}
    assert environment.acting_seat == seat
    restored = TrainingEnvironment()
    restored.restore(environment.snapshot())
    assert resolve(environment) == resolve(restored)
    assert environment.terminated and environment._state.winner == seat
    assert environment.rewards == {seat: 1, 3-seat: -1}
    assert environment.snapshot() == restored.snapshot()
    assert environment.prompts() == [] and environment.simple_actions() == []
    before = environment.snapshot()
    with pytest.raises(ActionRejected):
        environment.step({'type': 'pass_priority'}, seat)
    assert environment.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_consider_private_surveil_selection_and_continuation(seat):
    environment, cid = position(seat, 'Consider')
    environment.step(cast(environment, cid))
    resolve(environment)
    assert environment.acting_seat == seat
    assert environment.observe(seat)['pending_choice']['kind'] == 'surveil'
    hint = environment.prompts()[0]['hint']
    options = hint['options']
    assert options and set(options).issubset(environment.observe(seat)['known_cards'])
    assert not set(options).intersection(environment.observe(3-seat)['known_cards'])
    before = environment.snapshot()
    with pytest.raises(ActionRejected):
        environment.step({'type': 'choose_mechanic', 'card_ids': options * 2})
    assert environment.snapshot() == before
    restored = TrainingEnvironment()
    restored.restore(environment.snapshot())
    action = {'type': 'choose_mechanic', 'card_ids': options}
    assert environment.step(action) == restored.step(action)
    assert environment.snapshot() == restored.snapshot()
    assert set(options).issubset(environment._state.players[seat].graveyard)


def test_missing_cost_target_and_color_are_explicit_not_defaulted():
    environment, cid = position(1)
    before = environment.snapshot()
    with pytest.raises(ActionRejected, match='cost_choice.id'):
        environment.step({'type': 'cast_spell', 'card_id': cid, 'targets': {'target_player': 2}})
    with pytest.raises(ActionRejected, match='Announce'):
        environment.step(cast(environment, cid))
    land = next(cid for cid in environment._state.players[1].battlefield)
    with pytest.raises(ActionRejected, match='color'):
        environment.step({'type': 'tap_land_for_mana', 'card_id': land})
    assert environment.snapshot() == before
    assert environment.action_mask([{'type': 'tap_land_for_mana', 'card_id': land, 'color': 'R'}]) == [True]


def test_real_phase_land_action_and_out_of_priority_prompts():
    environment = env()
    keep(environment)
    while environment.observe(1)['step'] != 'precombat_main':
        environment.step({'type': 'pass_priority'})
    assert environment.observe(1)['step'] == 'precombat_main'
    place(environment, 'Mountain', 1, Zone.HAND)
    action = next(item for item in environment.simple_actions() if item['action']['type'] == 'play_land')
    environment.step(action['id'])
    assert action['action']['card_id'] in environment._state.players[1].battlefield
    environment.step({'type': 'pass_priority'})
    assert environment.acting_seat == 2
    assert environment.prompts(1) == []
    environment.step({'type': 'pass_priority'})
    assert environment.observe(1)['step'] != 'precombat_main'


def test_actual_engine_simultaneous_loss_is_draw_not_nonterminal():
    environment = env()
    keep(environment)
    environment._state.players[1].life = environment._state.players[2].life = 0
    result = environment.step({'type': 'pass_priority'})
    assert environment._state.winner == 0
    assert result['terminated'] and result['acting_seat'] is None
    assert result['rewards'] == {1: 0, 2: 0}
    restored = TrainingEnvironment()
    restored.restore(environment.snapshot())
    assert restored.terminated and restored.rewards == {1: 0, 2: 0}


@pytest.mark.parametrize('tamper', ['version', 'engine', 'state', 'deck', 'steps'])
def test_invalid_snapshot_rejected_atomically(tamper):
    environment = env()
    before = environment.snapshot()
    modified = deepcopy(before)
    if tamper == 'version':
        modified['version'] = 'future'
    elif tamper == 'engine':
        modified['provenance']['engine_hash'] = 'different'
    elif tamper == 'state':
        modified['state']['players']['1']['life'] = 99
    elif tamper == 'deck':
        modified['provenance']['deck_hashes'][0] = 'different'
    else:
        modified['steps'] = True
    with pytest.raises(ValueError):
        environment.restore(modified)
    assert environment.snapshot() == before


def test_returned_objects_cannot_mutate_environment():
    environment = env()
    before = environment.snapshot()
    observation = environment.observe(1)
    observation['players']['1']['hand'].clear()
    snapshot = environment.snapshot()
    snapshot['state']['pending_mechanic_choice'] = {'kind': 'wrong'}
    snapshot['provenance']['deck_names'].clear()
    environment.prompts()[0]['hint']['type'] = 'wrong'
    environment.simple_actions()[0]['action']['type'] = 'wrong'
    assert environment.snapshot() == before


@pytest.mark.parametrize('seed', [3, 17, 41])
def test_repeated_real_phase_trajectory_and_mid_episode_restore(seed):
    first, second = env(seed), env(seed)
    restored = TrainingEnvironment()
    restored.restore(first.snapshot())
    for _ in range(60):
        prompts = first.prompts()
        mechanic = next((prompt['hint'] for prompt in prompts
                         if prompt['hint']['type'] == 'choose_mechanic'), None)
        if mechanic:
            assert mechanic['kind'] == 'cleanup_discard'
            action = {'type': 'choose_mechanic', 'card_ids': mechanic['options'][:mechanic['count']]}
        elif first.observe(first.acting_seat)['pregame_pending']:
            action = {'type': 'keep_hand'}
        else:
            actions = first.simple_actions()
            action = next((item['action'] for item in actions if item['action']['type'] == 'play_land'),
                          {'type': 'pass_priority'})
        outputs = [environment.step(action) for environment in (first, second, restored)]
        assert outputs[0] == outputs[1] == outputs[2]
        assert first.snapshot() == second.snapshot() == restored.snapshot()
    assert first._state.turn > 1


def test_multiple_mulligans_require_ordered_variable_length_bottoms():
    environment = env()
    environment.step({'type': 'mulligan'})
    environment.step({'type': 'keep_hand'})
    environment.step({'type': 'choose_mechanic', 'card_ids': environment.prompts()[0]['hint']['options'][:1]})
    environment.step({'type': 'mulligan'})
    hint = environment.prompts()[0]['hint']
    assert hint['kind'] == 'mulligan_bottom' and hint['count'] == 2
    selected = list(reversed(hint['options'][:2]))
    restored = TrainingEnvironment()
    restored.restore(environment.snapshot())
    action = {'type': 'choose_mechanic', 'card_ids': selected}
    assert environment.step(encode_action(action)) == restored.step(action)
    assert environment._state.players[1].library[:2] == selected
    assert environment.snapshot() == restored.snapshot()


def test_response_failure_before_commit_is_atomic(monkeypatch):
    environment = env()
    before = environment.snapshot()
    def broken_view(self, seat):
        raise RuntimeError('simulated observation failure')
    monkeypatch.setattr(TrainingEnvironment, 'observe', broken_view)
    with pytest.raises(RuntimeError):
        environment.step({'type': 'keep_hand'})
    assert environment.snapshot() == before
    with pytest.raises(RuntimeError):
        environment.restore(env_snapshot := before)
    assert environment.snapshot() == env_snapshot


def test_real_attack_block_actions_need_explicit_declarations():
    environment = env()
    keep(environment)
    attacker = place(environment, 'Monastery Swiftspear', 1, Zone.BATTLEFIELD)
    blocker = place(environment, 'Sheoldred, the Apocalypse', 2, Zone.BATTLEFIELD)
    state = environment._state
    state.cards[attacker].summoning_sick = False
    state.step, state.priority_player = Step.DECLARE_ATTACKERS, 1
    before = environment.snapshot()
    with pytest.raises(ActionRejected, match='attack_targets'):
        environment.step({'type': 'attack', 'attackers': [attacker]})
    assert environment.snapshot() == before
    action = {'type': 'attack', 'attackers': [attacker], 'attack_targets': {attacker: 'player:2'}}
    environment.step(encode_action(action))
    resolve(environment)
    assert environment._state.step == Step.DECLARE_BLOCKERS and environment.acting_seat == 2
    block = {'type': 'block', 'blocks': {attacker: [blocker]}}
    assert environment.action_mask([block, {'type': 'block', 'blocks': {attacker: [attacker]}}]) == [True, False]
    restored = TrainingEnvironment()
    restored.restore(environment.snapshot())
    assert environment.step(block) == restored.step(block)
    assert environment._state.blocks[attacker] == [blocker]


def test_state_only_smoke_forbids_database_and_network_connections(monkeypatch):
    import sqlite3
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('No database/network connections in training adapter')
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    environment = env()
    environment.step({'type': 'keep_hand'})
    restored = TrainingEnvironment()
    restored.restore(environment.snapshot())
    assert restored.snapshot() == environment.snapshot()


def test_real_oven_activation_does_not_guess_sacrifice_payment():
    environment = TrainingEnvironment()
    environment.reset('Drain Deck', 'Mono Red Aggro', seed=1)
    keep(environment)
    environment._state.step = Step.PRECOMBAT_MAIN
    oven = place(environment, "Witch's Oven", 1, Zone.BATTLEFIELD)
    familiar = place(environment, 'Cauldron Familiar', 1, Zone.BATTLEFIELD)
    action = {'type': 'activate_ability', 'card_id': oven, 'ability_index': 0, 'targets': {}}
    before = environment.snapshot()
    with pytest.raises(ActionRejected, match='payment_choices.sacrifice_card_ids'):
        environment.step(action)
    assert environment.snapshot() == before
    action['payment_choices'] = {'sacrifice_card_ids': [familiar]}
    assert environment.action_mask([action]) == [True]
    restored = TrainingEnvironment()
    restored.restore(environment.snapshot())
    assert environment.step(action) == restored.step(action)
    assert familiar in environment._state.players[1].graveyard
    assert environment.snapshot() == restored.snapshot()


def test_real_mana_ability_index_and_color_are_checked():
    environment, _ = position(1)
    hint = next(p['hint'] for p in environment.prompts() if p['hint']['type'] == 'activate_mana_ability')
    action = {'type': 'activate_mana_ability', 'card_id': hint['card_id'],
              'ability_index': hint['ability_index'], 'color': 'R'}
    before = environment.snapshot()
    assert environment.action_mask([action, {**action, 'color': 'U'}, {**action, 'ability_index': 99}]) == [True, False, False]
    assert environment.snapshot() == before
    environment.step(action)
    assert environment._state.players[1].mana_pool['R'] == 1
    assert environment._state.cards[hint['card_id']].tapped
