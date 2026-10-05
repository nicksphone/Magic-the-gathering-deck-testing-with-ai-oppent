"""Canonical graveyard permission families; costs and timing are not waived."""
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add
from tests.test_ai_search_prefix import bare_state


DIRECTORY = Path(__file__).parent / 'fixtures/graveyard_permissions'
RAW = json.loads((DIRECTORY / 'canonical.json').read_text())
ROWS = {row['name']: {**row, 'power': row.get('power'), 'toughness': row.get('toughness')}
        for row in RAW['data']}
for file in ('haakon.json', 'black-knight.json', 'dryad-arbor.json', 'weathered-runestone.json'):
    row = json.loads((DIRECTORY / file).read_text())
    ROWS[row['name']] = {**row, 'power': row.get('power'), 'toughness': row.get('toughness')}


def position(seat):
    state = bare_state(seat)
    state.turn = 5
    state.players[seat].mana_pool = {'B': 1}
    return state


def moves(state, seat, cid):
    return [move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == cid]


def modal_land(state, seat):
    raw = json.loads((DIRECTORY / 'bala-ged-recovery.json').read_text())
    face = {**raw['card_faces'][0], 'power': None, 'toughness': None, 'keywords': []}
    card = add(state, face['name'], seat, Zone.GRAVEYARD, cards={face['name']: face})
    card.layout, card.card_faces = raw['layout'], raw['card_faces']
    return card


def test_canonical_data_is_complete_and_unchanged():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert len(RAW['data']) == len(provenance['names']) == 13
    assert not RAW.get('not_found')
    assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == provenance['sha256']
    for file in ('bala-ged-recovery.json', 'haakon.json', 'black-knight.json', 'dryad-arbor.json', 'weathered-runestone.json', 'limited-permissions.json'):
        provenance = json.loads((DIRECTORY / (file + '.provenance.json')).read_text())
        assert hashlib.sha256((DIRECTORY / file).read_bytes()).hexdigest() == provenance['sha256']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zombie', ['Diregraf Ghoul', 'Changeling Outcast'])
def test_conditional_self_permission_uses_actual_controlled_creature_type(seat, zombie):
    state = position(seat)
    spell = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    assert not moves(state, seat, spell.id)
    body = add(state, zombie, seat, cards=ROWS)
    available = moves(state, seat, spell.id)
    assert available and available[0]['from_graveyard']
    result = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': spell.id, 'from_graveyard': True})
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.players[seat].mana_pool['B'] == 0
    assert result.cards[body.id].zone == Zone.BATTLEFIELD
    restored = deserialize_match_snapshot(serialize_match_snapshot(result))
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(result)


@pytest.mark.parametrize('seat', [1, 2])
def test_opponent_zombie_and_wrong_source_flags_do_not_grant_permission(seat):
    state = position(seat)
    spell = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    add(state, 'Diregraf Ghoul', 3-seat, cards=ROWS)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'from_graveyard': True})
    assert serialize_match_snapshot(state) == before
    add(state, 'Diregraf Ghoul', seat, cards=ROWS)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant', ['Crucible of Worlds', 'Ramunap Excavator', 'Ancient Greenwarden'])
def test_land_permission_does_not_add_land_plays_or_ignore_timing(seat, grant):
    state = position(seat)
    land = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    assert not moves(state, seat, land.id)
    add(state, grant, seat, cards=ROWS)
    assert any(move['type'] == 'play_land' and move['from_graveyard'] for move in moves(state, seat, land.id))
    result = checked_action(state, RulesEngine(), seat, {'type': 'play_land', 'card_id': land.id, 'from_graveyard': True})
    assert result.cards[land.id].zone == Zone.BATTLEFIELD
    assert result.players[seat].lands_played_this_turn == 1
    other = add(result, 'Swamp', seat, Zone.GRAVEYARD, cards=ROWS)
    assert not moves(result, seat, other.id)
    state.step = Step.UPKEEP
    assert not moves(state, seat, land.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_cage_forbids_graveyard_spells_but_not_lands(seat):
    state = position(seat)
    spell = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    add(state, 'Diregraf Ghoul', seat, cards=ROWS)
    add(state, "Grafdigger's Cage", 3-seat, cards=ROWS)
    assert not any(move['type'] == 'cast_spell' for move in moves(state, seat, spell.id))
    add(state, 'Crucible of Worlds', seat, cards=ROWS)
    land = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    assert any(move['type'] == 'play_land' for move in moves(state, seat, land.id))


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_land_departure_emits_real_watcher_event(seat):
    state = position(seat)
    add(state, 'Crucible of Worlds', seat, cards=ROWS)
    watcher = add(state, 'Tormod, the Desecrator', seat, cards=ROWS)
    land = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    result = checked_action(state, RulesEngine(), seat, {'type': 'play_land', 'card_id': land.id, 'from_graveyard': True})
    assert any(item.source_card_id == watcher.id and item.payload.get('__trigger_event') == 'leaves_graveyard'
               for item in result.stack)


@pytest.mark.parametrize('seat', [1, 2])
def test_hogaak_graveyard_cast_uses_real_hybrid_convoke_delve_cost(seat):
    state = position(seat)
    spell = add(state, 'Hogaak, Arisen Necropolis', seat, Zone.GRAVEYARD, cards=ROWS)
    bodies = [add(state, name, seat, cards=ROWS).id for name in ('Ramunap Excavator', 'Ancient Greenwarden')]
    fodder = [add(state, 'Sol Ring', seat, Zone.GRAVEYARD, cards=ROWS).id for _ in range(5)]
    before = serialize_match_snapshot(state)
    action = {'type': 'cast_spell', 'card_id': spell.id, 'from_graveyard': True,
              'hybrid_choices': ['G', 'G'], 'cost_choice': {'id': 'base'},
              'resource_payment': {'delve': fodder, 'convoke': [{'card_id': cid, 'pay_as': 'G'} for cid in bodies]}}
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.players[seat].mana_pool == state.players[seat].mana_pool
    assert result.stack[-1].payload['mana_spent'] == 0
    assert set(result.players[seat].exile) == set(fodder)
    assert all(result.cards[cid].tapped for cid in bodies)


@pytest.mark.parametrize('seat', [1, 2])
def test_modal_land_face_can_be_played_from_graveyard_but_not_front_spell(seat):
    state = position(seat)
    card = modal_land(state, seat)
    add(state, 'Crucible of Worlds', seat, cards=ROWS)
    available = moves(state, seat, card.id)
    assert len(available) == 1 and available[0]['type'] == 'play_land'
    assert available[0]['selected_face_index'] == 1
    result = checked_action(state, RulesEngine(), seat, {
        'type': 'play_land', 'card_id': card.id, 'from_graveyard': True, 'selected_face_index': 1})
    assert result.cards[card.id].zone == Zone.BATTLEFIELD
    assert result.cards[card.id].tapped
    assert result.cards[card.id].types == ['Land']
    restored = deserialize_match_snapshot(serialize_match_snapshot(result))
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(result)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,grant', [('Gravecrawler', 'Diregraf Ghoul'), ('Forest', 'Crucible of Worlds')])
def test_ai_prices_reusable_graveyard_cards_only_when_permission_exists(seat, name, grant):
    from ai.casting_resources import _graveyard_loss
    state = position(seat)
    card = add(state, name, seat, Zone.GRAVEYARD, cards=ROWS)
    ai = AIAgent(archetype='Reanimator')
    before = _graveyard_loss(ai, state, card.id, seat)
    add(state, grant, seat, cards=ROWS)
    snapshot = serialize_match_snapshot(state)
    assert _graveyard_loss(ai, state, card.id, seat) > before
    assert serialize_match_snapshot(state) == snapshot


@pytest.mark.parametrize('seat', [1, 2])
def test_suppressed_land_grant_and_changeling_do_not_keep_permission(seat):
    state = position(seat)
    land = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    add(state, 'Ramunap Excavator', seat, cards=ROWS)
    spell = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    add(state, 'Changeling Outcast', seat, cards=ROWS)
    assert moves(state, seat, land.id) and moves(state, seat, spell.id)
    add(state, 'Humility', 3-seat, cards=ROWS)
    assert not moves(state, seat, land.id)
    assert not moves(state, seat, spell.id)
    add(state, 'Crucible of Worlds', seat, cards=ROWS)
    assert moves(state, seat, land.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_permission_does_not_follow_an_opponent_controlled_source(seat):
    state = position(seat)
    land = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    grant = add(state, 'Crucible of Worlds', seat, cards=ROWS)
    assert moves(state, seat, land.id)
    state.players[seat].battlefield.remove(grant.id)
    state.players[3-seat].battlefield.append(grant.id)
    grant.controller = 3-seat
    assert not moves(state, seat, land.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_spell_permission_does_not_waive_sorcery_timing_or_mana(seat):
    state = position(seat)
    card = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    add(state, 'Diregraf Ghoul', seat, cards=ROWS)
    state.players[seat].mana_pool = {}
    assert not any(move['type'] == 'cast_spell' for move in moves(state, seat, card.id))
    state.players[seat].mana_pool = {'B': 1}
    state.step = Step.UPKEEP
    assert not any(move['type'] == 'cast_spell' for move in moves(state, seat, card.id))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Tribal', 'Tokens', 'Ramp', 'Control'])
def test_ai_can_use_graveyard_land_and_creature_actions(seat, style):
    state = position(seat)
    add(state, 'Crucible of Worlds', seat, cards=ROWS)
    land = add(state, 'Forest', seat, Zone.GRAVEYARD, cards=ROWS)
    add(state, 'Diregraf Ghoul', seat, cards=ROWS)
    spell = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    ai = AIAgent(difficulty='master', archetype=style)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['type'] == 'play_land'
    assert decision.action['card_id'] == land.id and decision.action['from_graveyard']
    state = checked_action(state, RulesEngine(), seat, decision.action)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['card_id'] == spell.id and decision.action['from_graveyard']
    result = checked_action(state, RulesEngine(), seat, decision.action)
    assert result.cards[spell.id].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_only_self_permission_does_not_allow_hand_cast(seat):
    state = position(seat)
    state.players[seat].mana_pool = {'B': 3}
    hand = add(state, 'Haakon, Stromgald Scourge', seat, Zone.HAND, cards=ROWS)
    grave = add(state, 'Haakon, Stromgald Scourge', seat, Zone.GRAVEYARD, cards=ROWS)
    assert not any(move['type'] == 'cast_spell' for move in moves(state, seat, hand.id))
    assert any(move['type'] == 'cast_spell' for move in moves(state, seat, grave.id))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': hand.id})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Black Knight', 'Changeling Outcast'])
def test_tribal_spell_permission_requires_live_unsuppressed_grant(seat, name):
    state = position(seat)
    state.players[seat].mana_pool = {'B': 2}
    spell = add(state, name, seat, Zone.GRAVEYARD, cards=ROWS)
    assert not moves(state, seat, spell.id)
    add(state, 'Haakon, Stromgald Scourge', seat, cards=ROWS)
    assert any(move['type'] == 'cast_spell' for move in moves(state, seat, spell.id))
    add(state, 'Humility', 3-seat, cards=ROWS)
    assert not any(move['type'] == 'cast_spell' for move in moves(state, seat, spell.id))


@pytest.mark.parametrize('seat', [1, 2])
def test_ai_materializes_actual_graveyard_combined_resource_cast(seat):
    state = position(seat)
    spell = add(state, 'Hogaak, Arisen Necropolis', seat, Zone.GRAVEYARD, cards=ROWS)
    for name in ('Ramunap Excavator', 'Ancient Greenwarden'):
        add(state, name, seat, cards=ROWS)
    for _ in range(5):
        add(state, 'Sol Ring', seat, Zone.GRAVEYARD, cards=ROWS)
    ai = AIAgent(difficulty='master', archetype='Reanimator')
    before = serialize_match_snapshot(state)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'cast_spell' and decision.action['card_id'] == spell.id
    assert decision.action['from_graveyard']
    result = checked_action(state, RulesEngine(), seat, decision.action)
    assert result.cards[spell.id].zone == Zone.STACK
    assert result.players[seat].mana_pool == state.players[seat].mana_pool
    assert result.stack[-1].payload['mana_spent'] == 0


def test_limited_permission_families_are_reported_not_assumed_unlimited():
    from rules_engine.coverage import known_unsupported_mechanics
    from rules_engine.graveyard_permissions import permission_gaps
    rows = json.loads((DIRECTORY / 'limited-permissions.json').read_text())['data']
    assert len(rows) == 3
    for row in rows:
        expected = []
        assert permission_gaps(row['oracle_text'], row['name']) == expected
        assert ('unsupported graveyard play permission' in known_unsupported_mechanics(row['oracle_text'], card_name=row['name'])) == bool(expected)
    for name in ('Gravecrawler', 'Hogaak, Arisen Necropolis', 'Haakon, Stromgald Scourge', 'Crucible of Worlds'):
        assert permission_gaps(ROWS[name]['oracle_text'], name) == []
