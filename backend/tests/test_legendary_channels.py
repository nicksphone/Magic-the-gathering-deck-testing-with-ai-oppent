"""Canonical legendary Channel lands and their shared, non-card-specific mechanics."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone, Step
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities, search_card_matches
from rules_engine.continuous import effective_keywords
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add, resolve
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/legendary_channels.json').read_text())}
LANDS = [name for name, row in ROWS.items() if 'Channel' in row['keywords']]


def add(state, name, seat=1, zone=Zone.BATTLEFIELD):
    card = raw_add(state, name, seat, zone, cards=ROWS)
    card.summoning_sick = False
    if ROWS[name].get('loyalty'):
        card.loyalty = int(ROWS[name]['loyalty'])
    return card


def ability(source):
    return next(item for item in extract_activated_abilities(source) if item['activation_zone'] == 'hand')


def action(source, **targets):
    return {'type': 'activate_ability', 'card_id': source.id,
            'ability_index': ability(source)['index'], 'targets': targets}


def activate(state, source, **targets):
    return checked_action(state, RulesEngine(), source.controller, action(source, **targets))


def choice(state, seat, ids):
    return checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ids})


def resolve_to_choice(state):
    rules = RulesEngine()
    for _ in range(64):
        if state.pending_mechanic_choice or not state.stack:
            return state
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('No terminal resolution or owned choice')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', LANDS)
def test_legend_count_prices_hand_ability_not_land_play_or_mana_ability(seat, name):
    from rules_engine.activation_modifiers import activation_cost_view
    state = board(seat)
    source = add(state, name, seat, Zone.HAND)
    selected = ability(source)
    before = activation_cost_view(state, seat, source.id, selected['mana_cost'], ability_index=selected['index'])['requirements'][0]
    add(state, 'Isamaru, Hound of Konda', seat)
    add(state, 'Jasmine Boreal', seat)
    add(state, 'Isamaru, Hound of Konda', 3-seat)
    add(state, 'Boseiju, Who Endures', seat)  # Legendary land is not a creature.
    after = activation_cost_view(state, seat, source.id, selected['mana_cost'], ability_index=selected['index'])['requirements'][0]
    assert after['generic'] == max(0, before['generic']-2)
    for color in 'WUBRGC':
        assert after[color] == before[color]
    assert activation_cost_view(state, seat, source.id, '', ability_index=0)['requirements'][0]['generic'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_bounce_union_targets_noncreatures_but_not_lands_and_rechecks(seat):
    state = board(seat)
    source = add(state, 'Otawara, Soaring City', seat, Zone.HAND)
    artifact = add(state, 'Mind Stone', 3-seat)
    land = add(state, 'Hallowed Fountain', 3-seat)
    state.players[seat].mana_pool.update(C=3, U=1)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        activate(state, source, target_card_id=land.id)
    assert serialize_match_snapshot(state) == before
    result = resolve(activate(state, source, target_card_id=artifact.id))
    assert result.cards[artifact.id].zone == Zone.HAND
    assert result.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('decision', ['search', 'decline'])
def test_opponent_search_is_owned_optional_and_accepts_typed_nonbasic_land(seat, decision):
    state = board(seat)
    source = add(state, 'Boseiju, Who Endures', seat, Zone.HAND)
    target = add(state, 'Mind Stone', 3-seat)
    dual = add(state, 'Hallowed Fountain', 3-seat, Zone.LIBRARY)
    add(state, 'Boseiju, Who Endures', 3-seat, Zone.LIBRARY)
    state.players[seat].mana_pool.update(C=1, G=1)
    state.mechanic_choice_players = {1, 2}
    result = resolve_to_choice(activate(state, source, target_card_id=target.id))
    assert result.cards[target.id].zone == Zone.GRAVEYARD
    assert result.pending_mechanic_choice['kind'] == 'optional_search'
    assert result.pending_mechanic_choice['player_id'] == 3-seat
    result = deserialize_match_snapshot(serialize_match_snapshot(result))
    before = serialize_match_snapshot(result)
    with pytest.raises(ActionRejected):
        choice(result, seat, [decision])
    assert serialize_match_snapshot(result) == before
    result = choice(result, 3-seat, [decision])
    if decision == 'search':
        assert result.pending_mechanic_choice['kind'] == 'search_library'
        assert result.pending_mechanic_choice['options'] == [dual.id]
        result = choice(result, 3-seat, [dual.id])
        # The searched shock land has its own entry replacement choice.
        if result.pending_mechanic_choice:
            result = checked_action(result, RulesEngine(), 3-seat,
                {'type': 'choose_mechanic', 'choice_id': 'tapped'})
        assert result.cards[dual.id].zone == Zone.BATTLEFIELD
    else:
        assert result.cards[dual.id].zone == Zone.LIBRARY
    assert not result.pending_mechanic_choice and not result.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_destroy_union_excludes_basic_lands_and_keeps_opponents_only(seat):
    state = board(seat)
    source = add(state, 'Boseiju, Who Endures', seat, Zone.HAND)
    basic = add(state, 'Forest', 3-seat)
    own = add(state, 'Mind Stone', seat)
    dual = add(state, 'Hallowed Fountain', 3-seat)
    state.players[seat].mana_pool.update(C=1, G=1)
    for target in [basic, own]:
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            activate(state, source, target_card_id=target.id)
        assert serialize_match_snapshot(state) == before
    assert search_card_matches(dual, 'land_with_basic_type')
    assert not search_card_matches(source, 'land_with_basic_type')
    assert resolve(activate(state, source, target_card_id=dual.id)).cards[dual.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_mill_then_return_chooses_fresh_creature_or_planeswalker_without_target(seat):
    state = board(seat)
    source = add(state, 'Takenuma, Abandoned Mire', seat, Zone.HAND)
    creature = add(state, 'Grizzly Bears', seat, Zone.LIBRARY)
    walker = add(state, 'Ugin, the Spirit Dragon', seat, Zone.LIBRARY)
    land = add(state, 'Swamp', seat, Zone.LIBRARY)
    state.players[seat].mana_pool.update(C=3, B=1)
    state.mechanic_choice_players = {seat}
    result = resolve_to_choice(activate(state, source))
    assert set(result.pending_mechanic_choice['options']) == {creature.id, walker.id}
    assert result.cards[land.id].zone == Zone.GRAVEYARD
    assert sum(' mills ' in line for line in result.log) == 3
    result = deserialize_match_snapshot(serialize_match_snapshot(result))
    result = choice(result, seat, [walker.id])
    assert result.cards[walker.id].zone == Zone.HAND
    assert result.cards[creature.id].zone == Zone.GRAVEYARD
    assert sum(' mills ' in line for line in result.log) == 3
    assert not result.pending_mechanic_choice and not result.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_milling_empty_library_is_not_drawing_and_does_not_lose(seat):
    state = board(seat)
    source = add(state, 'Takenuma, Abandoned Mire', seat, Zone.HAND)
    state.players[seat].library.clear()
    state.players[seat].mana_pool.update(C=3, B=1)
    result = resolve(activate(state, source))
    assert result.winner is None and not result.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_combat_only_damage_rejects_idle_creatures_and_rechecks_status(seat):
    state = board(seat)
    source = add(state, 'Eiganjo, Seat of the Empire', seat, Zone.HAND)
    creature = add(state, 'Grizzly Bears', 3-seat)
    state.players[seat].mana_pool.update(C=2, W=1)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        activate(state, source, target_card_id=creature.id)
    assert serialize_match_snapshot(state) == before
    state.attackers = [creature.id]
    result = resolve(activate(state, source, target_card_id=creature.id))
    assert result.cards[creature.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_created_tokens_have_only_temporary_haste_and_keep_their_colors(seat):
    state = board(seat)
    source = add(state, 'Sokenzan, Crucible of Defiance', seat, Zone.HAND)
    state.players[seat].mana_pool.update(C=3, R=1)
    result = resolve(activate(state, source))
    tokens = [result.cards[cid] for cid in result.players[seat].battlefield]
    assert len(tokens) == 2
    for token in tokens:
        assert token.name == 'Spirit' and token.colors == []
        assert (token.power, token.toughness) == (1, 1)
        assert 'haste' in {key.lower() for key in effective_keywords(result, token.id)}
        assert 'haste' not in {key.lower() for key in token.keywords}
    result = deserialize_match_snapshot(serialize_match_snapshot(result))
    result.step = Step.END_STEP
    RulesEngine().next_step(result)
    for token in tokens:
        assert 'haste' not in {key.lower() for key in effective_keywords(result, token.id)}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Tokens', 'Tempo', 'Midrange', 'Control'])
def test_master_uses_winning_hand_token_ability_instead_of_forced_land(seat, style):
    from ai.agent import AIAgent
    state = board(seat)
    source = add(state, 'Sokenzan, Crucible of Defiance', seat, Zone.HAND)
    state.players[seat].mana_pool.update(C=3, R=1)
    state.players[3-seat].life = 2
    for _ in range(4):
        add(state, 'Forest', seat)
    ai = AIAgent(archetype=style, difficulty='master')
    before = serialize_match_snapshot(state)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['type'] == 'activate_ability', decision
    assert decision.action['card_id'] == source.id
    assert serialize_match_snapshot(state) == before
    result = resolve(checked_action(state, RulesEngine(), seat, decision.action))
    assert len([cid for cid in result.players[seat].battlefield if result.cards[cid].is_token]) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Tokens', 'Tempo', 'Midrange', 'Control'])
def test_master_keeps_bounce_land_for_winning_public_line_without_hand_peeking(seat, style):
    from ai.agent import AIAgent
    state = board(seat)
    source = add(state, 'Otawara, Soaring City', seat, Zone.HAND)
    add(state, 'Jasmine Boreal', seat)
    blocker = add(state, 'Grizzly Bears', 3-seat)
    state.players[seat].mana_pool.update(C=3, U=1)
    state.players[3-seat].life = 2
    for hidden_name in ['Grizzly Bears', 'Ugin, the Spirit Dragon']:
        projected = deserialize_match_snapshot(serialize_match_snapshot(state))
        add(projected, hidden_name, 3-seat, Zone.HAND)
        ai = AIAgent(archetype=style, difficulty='master')
        before = serialize_match_snapshot(projected)
        decision = ai.choose_action(projected, RulesEngine().legal_moves(projected, seat), seat)
        assert decision.action['type'] == 'activate_ability', decision
        assert decision.action['card_id'] == source.id
        assert decision.action['targets']['target_card_id'] == blocker.id
        assert serialize_match_snapshot(projected) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_attack_target_stopping_combat_before_resolution_fizzles_damage(seat):
    state = board(seat)
    source = add(state, 'Eiganjo, Seat of the Empire', seat, Zone.HAND)
    creature = add(state, 'Grizzly Bears', 3-seat)
    state.attackers = [creature.id]
    state.players[seat].mana_pool.update(C=2, W=1)
    result = activate(state, source, target_card_id=creature.id)
    result.attackers = []
    result = resolve(result)
    assert result.cards[creature.id].zone == Zone.BATTLEFIELD
    assert result.cards[creature.id].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_destroy_target_becoming_own_permanent_fizzles_without_search(seat):
    state = board(seat)
    source = add(state, 'Boseiju, Who Endures', seat, Zone.HAND)
    target = add(state, 'Mind Stone', 3-seat)
    state.players[seat].mana_pool.update(C=1, G=1)
    state.mechanic_choice_players = {1, 2}
    result = activate(state, source, target_card_id=target.id)
    result.players[3-seat].battlefield.remove(target.id)
    result.players[seat].battlefield.append(target.id)
    result.cards[target.id].controller = seat
    result = resolve_to_choice(result)
    assert result.cards[target.id].zone == Zone.BATTLEFIELD
    assert not result.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_discounted_hand_damage_spends_only_colored_mana(seat):
    state = board(seat)
    source = add(state, 'Eiganjo, Seat of the Empire', seat, Zone.HAND)
    add(state, 'Isamaru, Hound of Konda', seat)
    add(state, 'Jasmine Boreal', seat)
    target = add(state, 'Grizzly Bears', 3-seat)
    state.attackers = [target.id]
    state.players[seat].mana_pool['W'] = 1
    result = resolve(activate(state, source, target_card_id=target.id))
    assert result.cards[target.id].zone == Zone.GRAVEYARD
    assert sum(result.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_milled_replaced_cards_are_not_offered_for_graveyard_return(seat):
    from tests.test_opening_hand import CARDS
    raw = {'power': None, 'toughness': None, 'keywords': [], **CARDS['Leyline of the Void']}
    state = board(seat)
    raw_add(state, 'Leyline of the Void', 3-seat, cards={'Leyline of the Void': raw})
    source = add(state, 'Takenuma, Abandoned Mire', seat, Zone.HAND)
    creature = add(state, 'Grizzly Bears', seat, Zone.LIBRARY)
    state.players[seat].mana_pool.update(C=3, B=1)
    state.mechanic_choice_players = {seat}
    result = resolve_to_choice(activate(state, source))
    assert result.cards[creature.id].zone == Zone.EXILE
    assert result.cards[source.id].zone == Zone.EXILE
    assert not result.pending_mechanic_choice and not result.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_wrong_or_stale_graveyard_choice_is_rejected_atomically(seat):
    state = board(seat)
    source = add(state, 'Takenuma, Abandoned Mire', seat, Zone.HAND)
    creature = add(state, 'Grizzly Bears', seat, Zone.LIBRARY)
    state.players[seat].mana_pool.update(C=3, B=1)
    state.mechanic_choice_players = {seat}
    result = resolve_to_choice(activate(state, source))
    result.cards[creature.id].zone = Zone.EXILE
    result.players[seat].graveyard.remove(creature.id)
    result.players[seat].exile.append(creature.id)
    before = serialize_match_snapshot(result)
    with pytest.raises(ActionRejected):
        choice(result, seat, [creature.id])
    assert serialize_match_snapshot(result) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_optional_search_decline_does_not_shuffle_but_failed_find_does(seat):
    state = board(seat)
    source = add(state, 'Boseiju, Who Endures', seat, Zone.HAND)
    target = add(state, 'Mind Stone', 3-seat)
    state.players[seat].mana_pool.update(C=1, G=1)
    state.mechanic_choice_players = {1, 2}
    result = resolve_to_choice(activate(state, source, target_card_id=target.id))
    declined = choice(deserialize_match_snapshot(serialize_match_snapshot(result)), 3-seat, ['decline'])
    accepted = choice(result, 3-seat, ['search'])
    assert not any('shuffles their library' in line for line in declined.log)
    assert sum('shuffles their library' in line for line in accepted.log) == 1
    assert not accepted.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_sqlite_restores_owned_mill_return_without_milling_twice(game, seat):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, controller = game
    state = board(seat)
    state.id = controller.state.id
    source = add(state, 'Takenuma, Abandoned Mire', seat, Zone.HAND)
    target = add(state, 'Grizzly Bears', seat, Zone.LIBRARY)
    state.players[seat].mana_pool.update(C=3, B=1)
    state.mechanic_choice_players = {1, 2}
    controller.state = state
    persist(controller)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action(source)})
    assert response.status_code == 200, response.text
    for _ in range(2):
        current = main.ACTIVE_MATCHES[state.id].state
        response = client.post(f'/matches/{state.id}/action', json={
            'player_id': current.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    rejected(client, restored, {'type': 'choose_mechanic', 'card_ids': [target.id]}, 3-seat)
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': [target.id]}})
    assert response.status_code == 200, response.text
    result = main.ACTIVE_MATCHES[state.id].state
    assert result.cards[target.id].zone == Zone.HAND
    assert sum(' mills ' in line for line in result.log) == 3
    assert not result.pending_mechanic_choice and not result.stack
