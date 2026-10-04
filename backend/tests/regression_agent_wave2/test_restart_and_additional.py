"""Alternative X costs, canonical discard, split choices and SQLite restart."""
import json

import pytest
from sqlmodel import Session, create_engine
from persistence.models import ActiveMatchRecord
from persistence.repository import Repository
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from tests.regression_agent_wave2.support import (
    RULES, position, add, moves, cast, reject, resume, settle, record,
)
from tests.regression_agent_wave2.test_casting_contracts import RETURN, DISCARD, command_position


@pytest.mark.parametrize('seat,flashback,x', [(1, False, 2), (2, True, 0), (1, True, 2)],
                         ids=['front-positive', 'flashback-zero', 'flashback-positive'])
def test_devils_play_variable_alternative_price(seat, flashback, x):
    s = position(seat)
    c = add(s, "Devil's Play", seat, Zone.GRAVEYARD if flashback else Zone.HAND)
    s.players[seat].mana_pool.update(R=3 if flashback else 1, U=x)
    offered = moves(s, c)
    assert offered
    s = cast(s, c, {'x_value': x, 'target_player': 3-seat}, from_graveyard=flashback,
             cost_choice={'id': 'flashback' if flashback else 'base'})
    assert sum(s.players[seat].mana_pool.values()) == 0
    s = settle(resume(s))
    assert s.players[3-seat].life == 20-x
    assert s.cards[c.id].zone == (Zone.EXILE if flashback else Zone.GRAVEYARD)


def test_discard_cost_rejects_wrong_zone_then_pays_mdfc_before_draw():
    s = position(2)
    c = add(s, 'Tormenting Voice', 2)
    discard = add(s, 'Bala Ged Recovery // Bala Ged Sanctuary', 2)
    wrong = add(s, 'Grizzly Bears', 2, Zone.BATTLEFIELD)
    s.players[2].mana_pool.update(R=1, U=1)
    assert moves(s, c)
    reject(s, 2, {'type': 'cast_spell', 'card_id': c.id,
                  'cost_choice': {'id': 'base', 'discard_card_ids': [wrong.id]}})
    s = cast(s, c, cost_choice={'id': 'base', 'discard_card_ids': [discard.id]})
    assert not s.players[2].hand and s.cards[discard.id].zone == Zone.GRAVEYARD
    assert s.cards[discard.id].types == ['Sorcery']
    assert sum(s.players[2].mana_pool.values()) == 0
    s = settle(resume(s))
    assert len(s.players[2].hand) == 2
    assert s.cards[wrong.id].zone == Zone.BATTLEFIELD


def disk_restart(s, path):
    """Close writer and engine, reopen a real repository; no live app DB."""
    engine = create_engine('sqlite:///' + str(path))
    ActiveMatchRecord.__table__.create(engine)
    with Session(engine) as session:
        Repository(session).save_active_match(s.id, json.dumps(serialize_match_snapshot(s)), '{}')
    engine.dispose()
    fresh = create_engine('sqlite:///' + str(path))
    with Session(fresh) as session:
        row = Repository(session).get_active_match(s.id)
        assert row is not None
        restored = deserialize_match_snapshot(json.loads(row.state_json))
    fresh.dispose()
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(s)
    record('sqlite-reopened', restored)
    return restored


def test_pending_modal_discard_choice_survives_sqlite_restart(tmp_path):
    s, c, grave, target, _ = command_position()
    first = add(s, 'Forest', 2)
    second = add(s, 'Lightning Bolt', 2)
    s.mechanic_choice_players = {2}
    targets = {'mode_texts': [DISCARD, RETURN], 'mode_targets': {
        DISCARD: {'target_player': 2}, RETURN: {'target_card_id': grave.id}}}
    s = cast(s, c, targets)
    for _ in range(8):
        if s.pending_mechanic_choice:
            break
        s = checked_action(s, RULES, s.priority_player, {'type': 'pass_priority'})
    assert s.pending_mechanic_choice and s.pending_mechanic_choice['player_id'] == 2
    s = disk_restart(s, tmp_path / 'wave2-choice.db')
    reject(s, 1, {'type': 'choose_mechanic', 'card_ids': [first.id]})
    reject(s, 2, {'type': 'choose_mechanic', 'card_ids': []})
    reject(s, 2, {'type': 'choose_mechanic', 'card_ids': [first.id, second.id]})
    s = checked_action(s, RULES, 2, {'type': 'choose_mechanic', 'card_ids': [first.id]})
    s = settle(resume(s))
    assert s.pending_mechanic_choice is None
    assert s.cards[first.id].zone == Zone.GRAVEYARD
    assert s.cards[second.id].zone == Zone.HAND
    assert s.cards[grave.id].zone == Zone.HAND
    assert s.cards[c.id].zone == Zone.GRAVEYARD


def test_split_only_affordable_tear_half_resolves_after_snapshot():
    s = position(2)
    c = add(s, 'Wear // Tear', 2)
    enchantment = add(s, 'Rancor', 1, Zone.BATTLEFIELD)
    # Attach the canonical aura in the starting position so SBA will not remove it.
    bear = add(s, 'Grizzly Bears', 1, Zone.BATTLEFIELD)
    enchantment.attached_to = bear.id
    artifact = add(s, 'Memnite', 1, Zone.BATTLEFIELD)
    s.players[2].mana_pool['W'] = 1
    assert {m.get('selected_face_index') for m in moves(s, c)} == {1}
    reject(s, 2, {'type': 'cast_spell', 'card_id': c.id, 'selected_face_index': 0,
                  'targets': {'target_card_id': artifact.id}})
    s = cast(s, c, {'target_card_id': enchantment.id}, selected_face_index=1)
    assert s.cards[c.id].mana_cost == '{W}' and s.cards[c.id].types == ['Instant']
    assert sum(s.players[2].mana_pool.values()) == 0
    s = settle(resume(s))
    assert s.cards[enchantment.id].zone == Zone.HAND  # actual Rancor death trigger
    assert s.cards[artifact.id].zone == Zone.BATTLEFIELD
    assert s.cards[c.id].name == 'Wear // Tear' and s.cards[c.id].zone == Zone.GRAVEYARD
