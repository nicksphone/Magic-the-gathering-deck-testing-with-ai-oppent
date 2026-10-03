"""Canonical wheel counts, continuation ordering and hand-defined stats."""
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_combat_stats
from rules_engine.state_based_actions import apply_state_based_actions
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_surveil_mill import add
from tests.test_legendary_channels import resolve_to_choice
from tests.test_legendary_channels import choice
from tests.test_api_input_contracts import game
from tests.test_offline_match_hydration import REAL_HYDRATE, forbid_network

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/wheel_draw.json').read_text())}
SPELLS = ['Wheel of Fortune', 'Windfall', 'Dark Deal', 'Incendiary Command', 'Chandra Ablaze']


def canonical(state, name, seat=1, zone=Zone.BATTLEFIELD):
    # Use the production factory for nonnumeric/signed characteristics.
    raw = ROWS[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=7)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def setup(name, seat=1, sizes=(3, 5), cast=True):
    state = board(seat)
    state.mechanic_choice_players = {1, 2}
    source = canonical(state, name, seat, Zone.BATTLEFIELD if name == 'Chandra Ablaze' else Zone.HAND)
    hand = {pid: [add(state, 'Swamp', pid, Zone.HAND) for _ in range(size)] for pid, size in [(seat, sizes[0]), (3-seat, sizes[1])]}
    state.players[seat].mana_pool.update(R=3, U=3, B=3, C=12)
    action = {'type': 'activate_loyalty', 'card_id': source.id, 'ability_index': 1} if name == 'Chandra Ablaze' else {'type': 'cast_spell', 'card_id': source.id}
    if name == 'Incendiary Command':
        from rules_engine.cast_choice import build_cast_hints
        modes = build_cast_hints(state, source, seat)['modes']
        chosen = [mode for mode in modes if mode.startswith('Each player') or 'damage to target player' in mode]
        action['targets'] = {'mode_texts': chosen, 'mode_targets': {mode: {'target_player': 3-seat} if 'target player' in mode else {} for mode in chosen}}
    if cast:
        state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    return state, source, hand, action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SPELLS)
def test_canonical_wheel_uses_actual_discarded_counts(seat, name):
    state, source, hand, _ = setup(name, seat)
    assert not state.pending_mechanic_choice
    expected = {seat: 7, 3-seat: 7} if name == 'Wheel of Fortune' else {seat: 5, 3-seat: 5} if name == 'Windfall' else {seat: 2, 3-seat: 4} if name == 'Dark Deal' else {seat: 3, 3-seat: 3} if name == 'Chandra Ablaze' else {seat: 3, 3-seat: 5}
    assert {pid: len(player.hand) for pid, player in state.players.items()} == expected
    assert state.discards_this_turn == {seat: 3, 3-seat: 5}
    assert all(state.cards[card.id].zone == Zone.GRAVEYARD for cards in hand.values() for card in cards)
    if name == 'Chandra Ablaze':
        assert state.cards[source.id].loyalty == 3
    else:
        assert state.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_hand_defined_stats_survive_refill_and_die_when_empty(seat):
    state, source, hand, action = setup('Wheel of Fortune', seat, cast=False)
    maro = canonical(state, 'Maro', seat)
    assert effective_combat_stats(state, maro.id) == (4, 4)
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    assert effective_combat_stats(state, maro.id) == (7, 7)
    assert state.cards[maro.id].zone == Zone.BATTLEFIELD
    from rules_engine.zone_actions import discard_selected
    assert discard_selected(state, seat, list(state.players[seat].hand))
    apply_state_based_actions(state)
    assert state.cards[maro.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_signed_canonical_printed_stats_are_preserved(seat):
    state = board(seat)
    card = canonical(state, 'Char-Rumbler', seat)
    assert (card.power, card.toughness) == (-1, 3)
    assert effective_combat_stats(state, card.id) == (-1, 3)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Wheel of Fortune', 'Windfall', 'Dark Deal'])
@pytest.mark.parametrize('sizes', [(0, 0), (0, 1), (1, 0), (1, 1), (2, 4)])
def test_empty_and_short_wheels_do_not_draw_negative_counts(seat, name, sizes):
    state, _, _, _ = setup(name, seat, sizes)
    expected = {seat: 7, 3-seat: 7} if name == 'Wheel of Fortune' else {seat: max(sizes), 3-seat: max(sizes)} if name == 'Windfall' else {seat: max(0, sizes[0]-1), 3-seat: max(0, sizes[1]-1)}
    assert {pid: len(player.hand) for pid, player in state.players.items()} == expected
    assert state.discards_this_turn == {seat: sizes[0], 3-seat: sizes[1]}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Wheel of Fortune', 'Windfall', 'Dark Deal'])
def test_wheel_draws_are_apnap_and_replacements_keep_actual_discard_count(seat, name):
    from tests.test_linked_discard import ROWS as LINKED
    from tests.test_draw_forecast import ROWS as DRAW
    state, source, hand, action = setup(name, seat, cast=False)
    raw_add(state, 'Leyline of the Void', 3-seat, cards=LINKED)
    raw_add(state, 'Thought Reflection', seat, cards=DRAW)
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    base = 7 if name == 'Wheel of Fortune' else 5 if name == 'Windfall' else 2
    assert len(state.players[seat].hand) == base*2
    assert len(state.players[3-seat].hand) == (4 if name == 'Dark Deal' else base)
    assert all(state.cards[card.id].zone == Zone.EXILE for card in hand[seat])
    assert state.discards_this_turn == {seat: 3, 3-seat: 5}
    draws = [line for line in state.log if 'draws a card' in line]
    own = state.players[seat].name
    assert all(own in line for line in draws[:base*2])
    assert all(own not in line for line in draws[base*2:])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('failed', ['self', 'other', 'both'])
def test_wheel_empty_libraries_lose_only_after_full_resolution(seat, failed):
    state, source, _, action = setup('Wheel of Fortune', seat, cast=False)
    targets = [seat] if failed == 'self' else [3-seat] if failed == 'other' else [1, 2]
    for pid in targets:
        state.players[pid].library = state.players[pid].library[:2]
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    assert state.winner == (3-seat if failed == 'self' else seat if failed == 'other' else 0)
    assert state.failed_draw_players == set(targets)
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert len(state.players[seat].hand) == (2 if seat in targets else 7)
    assert len(state.players[3-seat].hand) == (2 if 3-seat in targets else 7)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Wheel of Fortune', 'Windfall', 'Dark Deal'])
def test_opposing_spell_copy_recounts_hands_and_does_not_pay_again(seat, name):
    from effects.registry import resolve_effect
    state, source, hand, action = setup(name, seat, cast=False)
    state = checked_action(state, RulesEngine(), seat, action)
    pool = dict(state.players[seat].mana_pool)
    resolve_effect(state, 3-seat, 'copy_spell', {'target_stack_id': state.stack[-1].id})
    state = resolve_to_choice(state)
    count = 7 if name == 'Wheel of Fortune' else 5 if name == 'Windfall' else 3
    assert len(state.players[3-seat].hand) == count
    assert len(state.players[seat].hand) == (1 if name == 'Dark Deal' else count)
    assert state.players[seat].mana_pool == pool
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert state.discards_this_turn == {seat: 5 if name == 'Dark Deal' else 10 if name == 'Wheel of Fortune' else 8,
                                       3-seat: 9 if name == 'Dark Deal' else 12 if name == 'Wheel of Fortune' else 10}


@pytest.mark.parametrize('seat', [1, 2])
def test_countered_wheel_does_not_discard_or_draw(seat):
    from effects.registry import resolve_effect
    state, source, hand, action = setup('Windfall', seat, cast=False)
    state = checked_action(state, RulesEngine(), seat, action)
    resolve_effect(state, 3-seat, 'counter_spell', {'target_stack_id': state.stack[-1].id})
    assert state.discards_this_turn == {1: 0, 2: 0}
    assert all(state.cards[card.id].zone == Zone.HAND for cards in hand.values() for card in cards)


@pytest.mark.parametrize('seat', [1, 2])
def test_maro_loses_defining_ability_without_inventing_printed_stats(seat):
    from effects.registry import resolve_effect
    state, _, _, _ = setup('Wheel of Fortune', seat, cast=False)
    maro = canonical(state, 'Maro', seat)
    assert (maro.power, maro.toughness) == (None, None)
    resolve_effect(state, seat, 'temporary_ability_loss', {'target_card_id': maro.id})
    assert effective_combat_stats(state, maro.id) == (0, 0)
    apply_state_based_actions(state)
    assert state.cards[maro.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('level', ['casual', 'strong', 'master'])
def test_ai_wheel_keeps_known_good_hand_and_does_not_inspect_opposing_cards(seat, level):
    from ai.agent import AIAgent
    state, source, hand, _ = setup('Wheel of Fortune', seat, sizes=(0, 0), cast=False)
    for _ in range(5):
        add(state, 'Counterspell', seat, Zone.HAND)
    agent = AIAgent(level, archetype='Control')
    move = {'type': 'cast_spell', 'card_id': source.id}
    before = serialize_match_snapshot(state)
    assert agent._bad_shared_draw_cast(state, move, seat)
    assert serialize_match_snapshot(state) == before
    opponents = [add(state, 'Swamp', 3-seat, Zone.HAND) for _ in range(5)]
    value = agent._wheel_exchange_value(state, seat, {'kind': 'fixed', 'amount': 7}, source.id)
    for card in opponents:
        card.oracle_text = 'Hidden identities must not be inspected'
        card.mana_cost = '{10}'
        card.types = ['Creature']
    assert agent._wheel_exchange_value(state, seat, {'kind': 'fixed', 'amount': 7}, source.id) == value


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('level', ['casual', 'strong', 'master'])
def test_ai_wheel_prices_refill_and_exhaustion_with_public_counts(seat, level):
    from ai.agent import AIAgent
    from tests.test_draw_forecast import ROWS as DRAW
    state, source, _, _ = setup('Wheel of Fortune', seat, sizes=(0, 5), cast=False)
    agent = AIAgent(level, archetype='Burn')
    move = {'type': 'cast_spell', 'card_id': source.id}
    assert not agent._bad_shared_draw_cast(state, move, seat)
    raw_add(state, 'Thought Reflection', seat, cards=DRAW)
    full_library = list(state.players[seat].library)
    state.players[seat].library = state.players[seat].library[:10]
    assert agent._bad_shared_draw_cast(state, move, seat)
    state.players[seat].library = full_library
    state.players[3-seat].library = state.players[3-seat].library[:2]
    assert not agent._bad_shared_draw_cast(state, move, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('level', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('scenario', ['retain', 'refill'])
def test_production_ai_retains_known_hand_or_legally_casts_refill(seat, level, scenario):
    from ai.agent import AIAgent
    state, source, _, _ = setup('Wheel of Fortune', seat, sizes=(0, 5), cast=False)
    if scenario == 'retain':
        for _ in range(6):
            add(state, 'Counterspell', seat, Zone.HAND)
    agent = AIAgent(level, archetype='Control' if scenario == 'retain' else 'Burn')
    action = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert (action.get('card_id') == source.id) == (scenario == 'refill')
    state = checked_action(state, RulesEngine(), seat, action)
    if scenario == 'refill':
        state = resolve_to_choice(state)
        assert len(state.players[seat].hand) == 7
        assert state.cards[source.id].zone == Zone.GRAVEYARD
    else:
        assert state.cards[source.id].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Wheel of Fortune', 'Windfall', 'Dark Deal'])
def test_both_dredge_continuations_keep_maro_alive_during_resolution(seat, name):
    from tests.test_linked_discard import ROWS as LINKED
    state, source, _, action = setup(name, seat, cast=False)
    maro = canonical(state, 'Maro', seat)
    imps = {pid: raw_add(state, 'Stinkweed Imp', pid, Zone.HAND, cards=LINKED) for pid in [1, 2]}
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    assert state.pending_mechanic_choice['kind'] == 'draw'
    assert state.pending_mechanic_choice['player_id'] == seat
    assert effective_combat_stats(state, maro.id) == (0, 0)
    assert state.cards[maro.id].zone == Zone.BATTLEFIELD
    expected = {seat: 7, 3-seat: 7} if name == 'Wheel of Fortune' else {seat: 6, 3-seat: 6} if name == 'Windfall' else {seat: 3, 3-seat: 5}
    for pid in [seat, 3-seat]:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        assert state.pending_mechanic_choice['player_id'] == pid
        state = checked_action(state, RulesEngine(), pid, {'type': 'choose_mechanic', 'choice_id': imps[pid].id})
        assert len(state.players[pid].hand) == expected[pid]
    assert not state.pending_mechanic_choice
    assert not state.stack
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert state.cards[maro.id].zone == Zone.BATTLEFIELD
    assert effective_combat_stats(state, maro.id) == (expected[seat], expected[seat])
    assert state.discards_this_turn == {seat: 4, 3-seat: 6}
    assert sum(line == f'{name} resolves.' for line in state.log) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Maro', 'Sturmgeist'])
def test_hand_defined_stats_share_counter_pump_and_base_layers(seat, name):
    from effects.registry import resolve_effect
    state, _, _, _ = setup('Wheel of Fortune', seat, cast=False)
    card = canonical(state, name, seat)
    card.counters['+1/+1'] = 2
    assert effective_combat_stats(state, card.id) == (6, 6)
    resolve_effect(state, seat, 'temporary_pt_buff', {'target_card_id': card.id, 'power': 2, 'toughness': 3})
    assert effective_combat_stats(state, card.id) == (8, 9)
    resolve_effect(state, seat, 'set_base_stats', {'target_card_id': card.id, 'base_power': 1, 'base_toughness': 1})
    assert effective_combat_stats(state, card.id) == (5, 6)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert effective_combat_stats(restored, card.id) == (5, 6)


@pytest.mark.parametrize('seat', [1, 2])
def test_discard_payoff_triggers_resolve_after_wheel_draws(seat):
    from rules_engine.stack_engine import resolve_top_of_stack
    state, source, _, action = setup('Windfall', seat, cast=False)
    canonical(state, 'Megrim', seat)
    state = checked_action(state, RulesEngine(), seat, action)
    assert resolve_top_of_stack(state)
    assert len(state.players[seat].hand) == len(state.players[3-seat].hand) == 5
    assert state.players[3-seat].life == 20
    assert len(state.stack) == 5
    state = resolve_to_choice(state)
    assert state.players[3-seat].life == 10
    assert state.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Wheel of Fortune', 'Windfall', 'Dark Deal'])
def test_wheel_http_and_sqlite_resume_retains_both_draw_sequences(game, seat, name):
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    from tests.test_api_input_contracts import persist, rejected
    from tests.test_linked_discard import ROWS as LINKED
    import main
    client, controller = game
    state, source, _, action = setup(name, seat, cast=False)
    imp = raw_add(state, 'Stinkweed Imp', seat, Zone.HAND, cards=LINKED)
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    rejected(client, controller, {'type': 'choose_mechanic', 'choice_id': imp.id}, 3-seat)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    controller = main.ACTIVE_MATCHES[state.id]
    assert controller.state.pending_mechanic_choice['resolving_item']
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id': seat, 'action': {'type': 'choose_mechanic', 'choice_id': imp.id},
    })
    assert response.status_code == 200, response.text
    final = controller.state
    expected = {seat: 7, 3-seat: 7} if name == 'Wheel of Fortune' else {seat: 5, 3-seat: 5} if name == 'Windfall' else {seat: 3, 3-seat: 4}
    assert {pid: len(player.hand) for pid, player in final.players.items()} == expected
    assert not final.stack and not final.pending_mechanic_choice
    assert final.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Maro', 'Sturmgeist', 'Char-Rumbler'])
def test_cached_printed_stats_survive_names_only_http_start(game, monkeypatch, seat, name):
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    from card_data.hydration import hydrate_deck_cards
    import main
    client, _ = game
    monkeypatch.setattr(main, '_hydrate_deck_cards', REAL_HYDRATE)
    forbid_network(monkeypatch)
    raw = ROWS[name]
    deck = [{'quantity': 4, 'card_name': name}, {'quantity': 56, 'card_name': 'Swamp'}]
    with Session(engine) as session:
        repo = Repository(session)
        repo.upsert_card({'scryfall_id': raw['id'], 'name': name, 'oracle_text': raw['oracle_text'],
                         'mana_cost': raw['mana_cost'], 'type_line': raw['type_line'],
                         'power': raw['power'], 'toughness': raw['toughness'], 'colors': ','.join(raw['colors'])})
        assert REAL_HYDRATE(repo, deck) == hydrate_deck_cards(repo, deck)
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck, 'seed': 113})
    assert response.status_code == 200, response.text
    state = main.ACTIVE_MATCHES[response.json()['id']].state
    card = next(card for card in state.cards.values() if card.name == name and card.owner == seat)
    if card.id in state.players[seat].library:
        state.players[seat].library.remove(card.id)
    else:
        state.players[seat].hand.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(card.id)
    expected = (-1, 3) if name == 'Char-Rumbler' else (len(state.players[seat].hand),) * 2
    assert (card.power, card.toughness) == ((-1, 3) if name == 'Char-Rumbler' else (None, None))
    assert effective_combat_stats(state, card.id) == expected
    from tests.test_api_input_contracts import persist
    persist(main.ACTIVE_MATCHES[state.id])
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id].state
    assert effective_combat_stats(restored, card.id) == expected
    view = client.get(f'/matches/{state.id}').json()['players'][str(seat)]['battlefield'][0]
    assert (view['power'], view['toughness']) == expected
