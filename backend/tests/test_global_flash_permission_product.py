"""Canonical timing/payment controls; constructed positions, not natural games.

Layer removal and control transfer below exercise existing effect APIs directly;
they do not claim a particular spell's resolution produced those effects.
"""
import json
import os
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.restrictions import can_cast_in_current_timing, has_global_flash_permission
from tests.test_canonical_global_flash_audit import GRANTS, SPELLS, ROWS, cast, offered, position, snapshot
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
def test_permission_follows_current_controller_not_owner(seat, grant):
    state, source, card = position(seat, grant)
    assert offered(state, seat, card.id)
    resolve_effect(state, 3-seat, 'change_control', {'target_card_id': source.id})
    state = deserialize_match_snapshot(snapshot(state))
    assert state.cards[source.id].owner == seat
    assert state.cards[source.id].controller == 3-seat
    before = snapshot(state)
    assert not has_global_flash_permission(state, seat)
    assert has_global_flash_permission(state, 3-seat)
    assert not offered(state, seat, card.id)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, cast(card))
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
def test_supported_layer_loss_and_expiry_gate_printed_permission(seat, grant):
    state, source, card = position(seat, grant)
    assert offered(state, seat, card.id)
    add_keyword_effect(state, source.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    state = deserialize_match_snapshot(snapshot(state))
    before = snapshot(state)
    assert printed_abilities_suppressed(state, source.id)
    assert not has_global_flash_permission(state, seat)
    assert not offered(state, seat, card.id)
    assert snapshot(state) == before
    RulesEngine()._clear_marked_damage(state)
    assert not printed_abilities_suppressed(state, source.id)
    assert offered(state, seat, card.id)
    assert state.cards[source.id].oracle_text == ROWS[grant]['oracle_text']
    assert state.cards[source.id].keywords == ROWS[grant]['keywords']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
def test_flash_mentioned_in_hand_is_not_intrinsic_flash_or_a_grant(seat, grant):
    state, _, card = position(seat, grant, source=False)
    uncast_source = raw_card(state, ROWS[grant], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 4, 'U': 2, 'G': 1}
    before = snapshot(state)
    assert not has_global_flash_permission(state, seat)
    for spell in (card, uncast_source):
        assert not can_cast_in_current_timing(state, spell, seat)[0]
        assert not offered(state, seat, spell.id)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, cast(spell))
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
def test_grant_does_not_supply_priority_or_mana(seat, grant):
    state, _, card = position(seat, grant)
    state.priority_player = 3-seat
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, cast(card))
    assert snapshot(state) == before
    state.priority_player = seat
    state.players[seat].mana_pool = {}
    before = snapshot(state)
    assert has_global_flash_permission(state, seat)
    assert not offered(state, seat, card.id)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, cast(card))
    assert snapshot(state) == before


@pytest.fixture
def isolated_api(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine
    from persistence.repository import Repository
    import persistence.db as db
    import main

    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve() / 'backend' == root
    assert Path(main.__file__).resolve().parent == root
    assert (root.parent / '.private-choice-audit-source').is_file()
    assert not (root.parent / '.git').exists()
    database = root / 'mtg_lab.db'
    assert not database.is_symlink()
    database_before = database.read_bytes() if database.exists() else None
    memory = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(memory)
    monkeypatch.setattr(db, 'engine', memory)
    monkeypatch.setattr(main, 'engine', memory)
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {})

    def repository():
        with Session(memory) as session:
            yield Repository(session)

    assert main.get_repo not in main.app.dependency_overrides
    main.app.dependency_overrides[main.get_repo] = repository
    # ASGI HTTP routes, without application lifespan or bulk/deck hydration.
    client = TestClient(main.app)
    try:
        yield main, memory, client
    finally:
        client.close()
        del main.app.dependency_overrides[main.get_repo]
        memory.dispose()
        assert (database.read_bytes() if database.exists() else None) == database_before


def database_dump(engine):
    connection = engine.raw_connection()
    try:
        return tuple(connection.driver_connection.iterdump())
    finally:
        connection.close()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
@pytest.mark.parametrize('spell', SPELLS)
@pytest.mark.parametrize('funded', [True, False])
def test_actual_http_payment_privacy_atomic_rejection_and_sqlite_restore(isolated_api, seat, grant, spell, funded):
    from sqlmodel import Session
    from persistence.repository import Repository
    main, database, client = isolated_api
    state, source, card = position(seat, grant, spell)
    hidden = raw_card(state, ROWS['Opt'], 3-seat, Zone.HAND)
    if not funded:
        state.players[seat].mana_pool = {}
    controller = main.MatchController(state=state, rules=RulesEngine(),
        controllers={seat: 'human', 3-seat: 'ai'}, ai={}, mode='human_vs_ai',
        deck_ids=(None, None), mainboards={1: [], 2: []}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=1)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(database) as session:
        main._persist_active_match(Repository(session), controller)
    before = snapshot(controller.state)
    before_db = database_dump(database)
    legal = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}')
    assert legal.status_code == 200
    moves = legal.json()['moves']
    assert any(m.get('card_id') == card.id and m['type'] == 'cast_spell' for m in moves) == funded
    assert hidden.id not in json.dumps(moves)
    assert snapshot(controller.state) == before and database_dump(database) == before_db
    action = cast(card)
    expected = checked_action(state, RulesEngine(), seat, action) if funded else None
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == (200 if funded else 422), response.text
    if funded:
        assert controller.state.cards[card.id].zone == Zone.STACK
        assert sum(controller.state.players[seat].mana_pool.values()) == 0
        assert snapshot(controller.state) == snapshot(expected)
        assert response.json()['players'][str(3-seat)]['hand'] == []
        assert hidden.id not in json.dumps(response.json())
    else:
        assert response.json()['detail']['code'] == 'illegal_action'
        assert snapshot(controller.state) == before
        assert database_dump(database) == before_db
    after = snapshot(controller.state)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(database) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert snapshot(restored.state) == after
    assert restored.state.cards[source.id].oracle_text == ROWS[grant]['oracle_text']
    evidence = os.environ.get('MTG_FLASH_PRODUCT_HTTP_EVIDENCE')
    if evidence:
        path = Path(evidence) / f'{seat}-{grant}-{spell}-{funded}.json'
        with path.open('x') as stream:
            json.dump({'before': before, 'after': after, 'legal_response': legal.json(),
                'action_response': response.json(), 'status': response.status_code,
                'sqlite_restore_exact': True, 'paid': funded,
                'database': 'isolated in-memory SQLite; no application lifespan',
                'transport': 'ASGI HTTP, no live server', 'private_enemy_hand_absent': True}, stream, indent=2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', GRANTS)
@pytest.mark.parametrize('spell', SPELLS)
def test_actual_http_paid_response_preserves_existing_real_spell_stack(isolated_api, seat, grant, spell):
    from sqlmodel import Session
    from persistence.repository import Repository
    main, database, client = isolated_api
    state, _, card = position(seat, grant, spell)
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    opt = raw_card(state, ROWS['Opt'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    state = checked_action(state, RulesEngine(), 3-seat, cast(opt))
    assert sum(state.players[3-seat].mana_pool.values()) == 0
    state = checked_action(state, RulesEngine(), 3-seat, {'type': 'pass_priority'})
    assert state.priority_player == seat
    assert len(state.stack) == 1 and state.stack[0].source_card_id == opt.id
    hidden = raw_card(state, ROWS['Grizzly Bears'], 3-seat, Zone.HAND)
    controller = main.MatchController(state=state, rules=RulesEngine(),
        controllers={seat: 'human', 3-seat: 'ai'}, ai={}, mode='human_vs_ai',
        deck_ids=(None, None), mainboards={1: [], 2: []}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=1)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(database) as session:
        main._persist_active_match(Repository(session), controller)
    before = snapshot(state)
    db_before = database_dump(database)
    legal = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}')
    assert legal.status_code == 200
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == card.id
               for move in legal.json()['moves'])
    assert hidden.id not in json.dumps(legal.json())
    assert snapshot(state) == before and database_dump(database) == db_before
    expected = checked_action(state, RulesEngine(), seat, cast(card))
    assert snapshot(state) == before
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': cast(card)})
    assert response.status_code == 200, response.text
    after = snapshot(controller.state)
    assert after == snapshot(expected)
    assert len(controller.state.stack) == 2
    assert controller.state.stack[0].source_card_id == opt.id
    assert controller.state.stack[1].source_card_id == card.id
    assert sum(controller.state.players[seat].mana_pool.values()) == 0
    assert hidden.id not in json.dumps(response.json())
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(database) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert snapshot(main.ACTIVE_MATCHES[state.id].state) == after
    evidence = os.environ.get('MTG_FLASH_PRODUCT_HTTP_EVIDENCE')
    if evidence:
        with (Path(evidence) / f'response-{seat}-{grant}-{spell}.json').open('x') as stream:
            json.dump({'before': before, 'after': after, 'legal_response': legal.json(),
                'action_response': response.json(), 'status': 200,
                'existing_opt_paid': True, 'response_paid': True,
                'real_spell_stack_tail_preserved': True, 'sqlite_restore_exact': True,
                'private_enemy_hand_absent': True, 'transport': 'ASGI HTTP, no live server'}, stream, indent=2)
