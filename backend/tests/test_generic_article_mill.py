"""Full canonical mill instructions; no invented Oracle/gameplay cards."""
from copy import copy, deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.oracle_text import without_reminder_text
from tests.test_linked_damage_targets import raw_card
from tests.test_training_choice_coverage import position
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


FIXTURE = Path(__file__).parent / 'fixtures/generic_article_mill/canonical.jsonl'
PROVENANCE = json.loads(FIXTURE.with_name('provenance.json').read_text())
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['fixture_sha256']
ROWS = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}
assert len(ROWS) == 7 and all(row['object'] == 'card' and row['oracle_id'] for row in ROWS.values())


def snapshot(state):
    return json.loads(json.dumps(serialize_match_snapshot(state)))


def restart_state(state):
    before = snapshot(state)
    state = deserialize_match_snapshot(before)
    assert snapshot(state) == before
    return state


def checked(state, actor, action):
    before = snapshot(state)
    result = checked_action(state, RulesEngine(), actor, action)
    assert snapshot(state) == before
    repeat = checked_action(deserialize_match_snapshot(before), RulesEngine(), actor, action)
    assert snapshot(result) == snapshot(repeat)
    return result


def resolve(state):
    for _ in range(16):
        if not state.stack:
            return state
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Canonical stack did not resolve within16passes')


def setup(seat):
    env = position(seat)
    card = raw_card(env._state, ROWS['Codex Shredder'], seat, Zone.BATTLEFIELD)
    env._state.players[seat].mana_pool = dict.fromkeys('WUBRGC', 0)
    assert card.oracle_text == ROWS[card.name]['oracle_text']
    return env, card.id


def activation(cid, target):
    return {'type': 'activate_ability', 'card_id': cid, 'ability_index': 0,
            'targets': {'target_player': target}}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Altar of the Brood', 'Codex Shredder'])
def test_complete_canonical_body_compiles_without_root_or_oracle_mutation(seat, name):
    env = position(seat)
    state = env._state
    card = raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD)
    proxy = copy(card)
    proxy.source_oracle_text = card.oracle_text
    proxy.oracle_text = (card.oracle_text.split(', ', 1)[1] if name == 'Altar of the Brood'
                         else extract_activated_abilities(card)[0]['text'])
    before = snapshot(state)
    spec = build_ability_spec(state, proxy, seat, {'target_player': seat}, report_unsupported=False)
    assert spec.effect.key == 'mill_cards'
    assert spec.effect.payload == {'amount': 1, 'target_player': 3-seat if name == 'Altar of the Brood' else seat}
    assert snapshot(state) == before
    assert card.oracle_text == ROWS[name]['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
def test_targeted_preview_does_not_guess_opponent_and_missing_target_is_atomic(seat):
    env, cid = setup(seat)
    state = env._state
    proxy = copy(state.cards[cid])
    proxy.oracle_text = extract_activated_abilities(proxy)[0]['text']
    before = snapshot(state)
    spec = build_ability_spec(state, proxy, seat, report_unsupported=False)
    assert spec.effect.key == 'mill_cards' and spec.effect.payload['target_player'] is None
    assert spec.target_hints.get('player_targets')
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'activate_ability', 'card_id': cid, 'ability_index': 0})
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('own_target', [False, True])
@pytest.mark.parametrize('departed', [False, True])
def test_actual_tap_activation_chosen_player_receipt_departure_restart_and_privacy(seat, own_target, departed):
    env, cid = setup(seat)
    state = env._state
    target = seat if own_target else 3-seat
    top = state.players[target].library[-1]
    libraries = {pid: list(player.library) for pid, player in state.players.items()}
    offered = RulesEngine().legal_moves(state, seat)
    assert any(move['type'] == 'activate_ability' and move['card_id'] == cid and move['ability_index'] == 0 for move in offered)
    state = checked(state, seat, activation(cid, target))
    assert state.cards[cid].tapped and not any(state.players[seat].mana_pool.values())
    assert {pid: player.library for pid, player in state.players.items()} == libraries
    item = state.stack[-1]
    assert item.controller == seat and item.source_card_id == cid and item.effect_key == 'mill_cards'
    assert item.payload['amount'] == 1 and item.payload['target_player'] == target
    if departed:
        # Controlled source departure after actual payment; not a claimed spell episode.
        resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': cid})
        assert state.cards[cid].zone == Zone.GRAVEYARD
    state = resolve(restart_state(state))
    assert state.players[target].library == libraries[target][:-1]
    assert state.players[3-target].library == libraries[3-target]
    assert top in state.players[target].graveyard and state.cards[top].zone == Zone.GRAVEYARD
    assert state.cards[cid].oracle_text == ROWS['Codex Shredder']['oracle_text']
    assert state.winner is None and not state.failed_draw_players
    assert restart_state(state).cards[top].zone == Zone.GRAVEYARD
    secret = state.players[3-seat].hand[0]
    view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    assert view.cards[secret].ai_unknown and not view.cards[secret].name
    assert not view.cards[secret].oracle_text


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_stifle_counters_paid_mill_without_cost_refund(seat):
    env, cid = setup(seat)
    state = env._state
    libraries = {pid: list(player.library) for pid, player in state.players.items()}
    counter = raw_card(state, ROWS['Stifle'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool['U'] = 1
    state = checked(state, seat, activation(cid, 3-seat))
    item_id = state.stack[-1].id
    state = checked(state, seat, {'type': 'pass_priority'})
    assert state.priority_player == 3-seat
    state = checked(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                                  'targets': {'target_stack_id': item_id}})
    assert state.players[3-seat].mana_pool['U'] == 0
    state = resolve(restart_state(state))
    assert {pid: player.library for pid, player in state.players.items()} == libraries
    assert state.cards[cid].tapped and state.cards[counter.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['replacement', 'empty', 'control'])
def test_actual_activation_replacement_empty_library_and_retained_controller(seat, mode):
    env, cid = setup(seat)
    state = env._state
    target = 3-seat
    if mode == 'empty':
        # Controlled retained position, not an invented draw/mill episode.
        for card_id in list(state.players[target].library):
            state.players[target].library.remove(card_id)
            state.players[target].graveyard.append(card_id)
            state.cards[card_id].move_to_zone(Zone.GRAVEYARD)
    if mode == 'replacement':
        spell = raw_card(state, ROWS['Rest in Peace'], seat, Zone.HAND)
        state.players[seat].mana_pool.update(W=1, C=1)
        state = resolve(checked(state, seat, {'type': 'cast_spell', 'card_id': spell.id}))
        assert state.cards[spell.id].zone == Zone.BATTLEFIELD
        state.players[seat].mana_pool = dict.fromkeys('WUBRGC', 0)
    library = list(state.players[target].library)
    state = checked(state, seat, activation(cid, target))
    if mode == 'control':
        # Controlled post-announcement control seam; captured receipt stays authoritative.
        state.players[seat].battlefield.remove(cid)
        state.players[target].battlefield.append(cid)
        state.cards[cid].controller = target
        assert state.stack[-1].controller == seat
    state = resolve(restart_state(state))
    assert state.players[target].library == library[:-1]
    if library:
        expected = Zone.EXILE if mode == 'replacement' else Zone.GRAVEYARD
        assert state.cards[library[-1]].zone == expected
        assert library[-1] in getattr(state.players[target], expected.value)
    assert state.winner is None and not state.failed_draw_players


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_canonical_artifact_cast_does_not_execute_activation_and_can_tap_same_turn(seat):
    env = position(seat)
    state = env._state
    card = raw_card(state, ROWS['Codex Shredder'], seat, Zone.HAND)
    state.players[seat].mana_pool = dict.fromkeys('WUBRGC', 0)
    state.players[seat].mana_pool['C'] = 1
    library = list(state.players[3-seat].library)
    state = resolve(checked(state, seat, {'type': 'cast_spell', 'card_id': card.id}))
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.players[3-seat].library == library
    assert not any(state.players[seat].mana_pool.values())
    state = resolve(checked(state, seat, activation(card.id, 3-seat)))
    assert state.cards[card.id].tapped and state.players[3-seat].library == library[:-1]


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_numeric_compound_thought_scour_still_mills_two_and_draws_one(seat):
    env = position(seat)
    state = env._state
    spell = raw_card(state, ROWS['Thought Scour'], seat, Zone.HAND)
    state.players[seat].mana_pool = dict.fromkeys('WUBRGC', 0)
    state.players[seat].mana_pool['U'] = 1
    own_library = list(state.players[seat].library)
    library = list(state.players[3-seat].library)
    state = resolve(restart_state(checked(state, seat, {'type': 'cast_spell', 'card_id': spell.id,
                                                      'targets': {'target_player': 3-seat}})))
    assert state.players[3-seat].library == library[:-2]
    assert set(library[-2:]).issubset(state.players[3-seat].graveyard)
    assert state.players[seat].library == own_library[:-1]
    assert own_library[-1] in state.players[seat].hand
    assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_offered_mill_and_private_view_do_not_depend_on_foreign_hidden_metadata(seat):
    env, cid = setup(seat)
    state = env._state
    before = snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    view, private_moves = decision_view(state, seat, moves)
    changed = deepcopy(state)
    # Privacy perturbation only, not a fabricated gameplay card or legal alteration.
    for hidden_id in changed.players[3-seat].hand + changed.players[3-seat].library:
        hidden = changed.cards[hidden_id]
        hidden.name = 'private metadata probe'
        hidden.oracle_text = 'private metadata probe'
        hidden.mana_cost = '{999}'
    repeated_moves = RulesEngine().legal_moves(changed, seat)
    repeated_view, repeated_private_moves = decision_view(changed, seat, repeated_moves)
    assert moves == repeated_moves and private_moves == repeated_private_moves
    assert snapshot(view) == snapshot(repeated_view)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['missing', 'boolean', 'invalid_player', 'foreign_actor', 'tapped', 'unfunded_second_ability'])
def test_invalid_targets_actor_and_payment_reject_without_any_state_change(seat, bad):
    env, cid = setup(seat)
    state = env._state
    action, actor = activation(cid, 3-seat), seat
    if bad == 'missing':
        action.pop('targets')
    elif bad == 'boolean':
        action['targets']['target_player'] = True
    elif bad == 'invalid_player':
        action['targets']['target_player'] = 3
    elif bad == 'foreign_actor':
        actor = 3-seat
    elif bad == 'tapped':
        state.cards[cid].tapped = True  # Controlled illegal input boundary.
    else:
        action['ability_index'] = 1
        action['targets'] = {'target_card_id': cid}
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), actor, action)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_http_typed_payment_targets_root_database_and_restart(game, seat):
    env, cid = setup(seat)
    client, match = game
    identifier = retain(match, env)
    action = activation(cid, 3-seat)
    rejected(client, match, {**action, 'targets': {}}, seat)
    rejected(client, match, {**action, 'targets': {'target_player': True}}, seat)
    rejected(client, match, action, 3-seat)
    library = list(match.state.players[3-seat].library)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    pending = restart(identifier).state
    assert pending.cards[cid].tapped and pending.stack[-1].effect_key == 'mill_cards'
    for _ in range(8):
        current = restart(identifier).state
        if not current.stack:
            break
        response = client.post(f'/matches/{identifier}/action', json={
            'player_id': current.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    final = restart(identifier).state
    assert not final.stack and final.players[3-seat].library == library[:-1]
    assert library[-1] in final.players[3-seat].graveyard
    secret = final.players[3-seat].hand[0]
    view = client.get(f'/matches/{identifier}/legal-moves?player_id={seat}')
    assert view.status_code == 200 and secret not in view.text


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', ['. Take an extra turn after this one.', ', then take an extra turn after this one.', '; you gain 2 life.'])
def test_parser_control_unknown_compound_is_not_partial_article_mill_or_free_reward(seat, tail):
    env, cid = setup(seat)
    proxy = copy(env._state.cards[cid])
    # Explicit parser seam, NOT a fabricated Oracle/card or legal game episode.
    proxy.oracle_text = 'Target player mills a card' + tail
    before = snapshot(env._state)
    spec = build_ability_spec(env._state, proxy, seat, {'target_player': 3-seat}, report_unsupported=False)
    assert spec.effect.key == 'noop'
    assert snapshot(env._state) == before
