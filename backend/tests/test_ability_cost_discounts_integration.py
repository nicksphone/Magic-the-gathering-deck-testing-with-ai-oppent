"""Selected ability payment across HTTP recovery and mana-source consumption."""
import pytest

from card_data.token_definitions import named_artifact_token
from effects.handlers import create_token
from game_state.state import Zone
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_ability_cost_discounts import source, board, add, view, resolve
from tests.test_api_input_contracts import game, persist, rejected, snapshot


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ["Tamiyo's Logbook", 'Deepwood Denizen', 'Battlefield Butcher'])
def test_http_scoped_cost_payment_is_atomic_and_restored(game, seat, name):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state = board(seat)
    card = source(state, name, seat)
    if name == "Tamiyo's Logbook":
        for _ in range(4):
            add(state, 'Mind Stone', seat).tapped = True
        color = 'U'
    elif name == 'Deepwood Denizen':
        card.counters['+1/+1'] = 4
        color = 'G'
    else:
        for _ in range(4):
            add(state, 'Azure Mage', seat, Zone.GRAVEYARD)
        color = None
    if color:
        state.players[seat].mana_pool[color] = 1
    state.id = match.state.id
    match.state = state
    persist(match)
    action = {'type': 'activate_ability', 'card_id': card.id, 'ability_index': 0, 'targets': {}}
    rejected(client, match, action, seat)
    match.state.players[seat].mana_pool['C'] = 1
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert sum(match.state.players[seat].mana_pool.values()) == 0
    committed = snapshot(match)[0]
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert snapshot(main.ACTIVE_MATCHES[state.id])[0] == committed


@pytest.mark.parametrize('seat', [1, 2])
def test_artifact_discount_is_locked_before_treasure_is_consumed_for_mana(seat):
    state = board(seat)
    card = source(state, "Tamiyo's Logbook", seat)
    create_token(state, seat, {**named_artifact_token('Treasure'), 'amount': 5, 'types': ['Artifact', 'Token']})
    assert view(state, card)['generic'] == 0
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'activate_ability' and m['card_id'] == card.id)
    result = checked_action(state, RulesEngine(), seat, move)
    assert sum(result.players[seat].mana_pool.values()) == 0
    assert sum(result.cards[cid].name == 'Treasure' for cid in result.players[seat].battlefield) == 4
    assert view(result, result.cards[card.id])['generic'] == 1
    assert len(resolve(result).players[seat].hand) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_another_tap_target_rejects_its_source_without_costs(seat):
    from tests.test_ai_recurring_engines import add as raw_add
    from game_state.serializers import serialize_match_snapshot
    state = board(seat)
    card = source(state, 'Starport Security', seat)
    raw_add(state, 'Sheoldred, the Apocalypse', seat).counters['+1/+1'] = 1
    state.players[seat].mana_pool.update(C=1, W=1)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'activate_ability', 'card_id': card.id,
                      'ability_index': 0, 'targets': {'target_card_id': card.id}})
    assert serialize_match_snapshot(state) == before
