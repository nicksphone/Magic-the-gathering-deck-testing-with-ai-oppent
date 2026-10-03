"""Canonical surface goldens and coherent negative-stat target decisions."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_toughness
from rules_engine.costs import collect_cost_options, additional_cost_candidates
from rules_engine.engine import RulesEngine
from rules_engine.kicker import kicker_surfaces
from tests.test_activation_modifiers import board, ROWS as MODIFIERS
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_permanent_kicker import ROWS as PERMANENTS
from tests.test_surveil_mill import add, resolve
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/kicker_goldens.json').read_text())}
SPELLS = [name for name, row in ROWS.items() if 'Kicker' in row['keywords']]
REMOVAL = [name for name in SPELLS if name != 'Hypnotic Cloud']


def setup(name, seat=1, free=False):
    state = board(seat)
    spell = raw_add(state, name, seat, Zone.GRAVEYARD if free else Zone.HAND, cards=ROWS)
    artifact = raw_add(state, 'Darksteel Relic', seat, cards=ROWS)
    creature = add(state, 'Grizzly Bears', seat)
    target = raw_add(state, 'Baloth Gorger', 3-seat, cards=PERMANENTS)
    state.players[seat].mana_pool.update(B=10, C=20)
    if name == 'Hypnotic Cloud':
        for land in ['Island','Swamp','Island']:
            add(state, land, 3-seat, Zone.HAND)
    if free:
        state.mechanic_choice_players = {seat}
        resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    return state, spell, artifact, creature, target


def cast_action(spell, seat, kicked, payer=None, target=None, free=False):
    return {'type':'cast_spell','card_id':spell.id,'from_graveyard':free,
            'cost_choice':{'id':'kicker' if kicked else 'base',
                           'sacrifice_card_ids':[payer.id] if payer and kicked else []},
            'targets':{'target_player':3-seat} if spell.name == 'Hypnotic Cloud' else {'target_card_id':target.id}}


@pytest.mark.parametrize('seat', [1,2])
@pytest.mark.parametrize('name', SPELLS)
@pytest.mark.parametrize('free', [False,True])
@pytest.mark.parametrize('kicked', [False,True])
@pytest.mark.parametrize('payment', ['artifact','creature'])
def test_paid_unpaid_resource_effect_and_snapshot_goldens(seat, name, free, kicked, payment):
    state, spell, artifact, creature, target = setup(name,seat,free)
    payer = artifact if payment == 'artifact' else creature
    mana_before = sum(state.players[seat].mana_pool.values())
    text = spell.oracle_text
    assert kicker_surfaces(text) is not None
    state = checked_action(state,RulesEngine(),seat,
        cast_action(spell,seat,kicked,None if name == 'Hypnotic Cloud' else payer,target,free))
    assert state.stack[-1].payload['__kicked'] is kicked
    expected_mana = (0 if free else 2) + (4 if kicked and name == 'Hypnotic Cloud' else 0)
    assert mana_before - sum(state.players[seat].mana_pool.values()) == expected_mana
    if name != 'Hypnotic Cloud':
        assert state.cards[payer.id].zone == (Zone.GRAVEYARD if kicked else Zone.BATTLEFIELD)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    assert state.cards[spell.id].oracle_text == text
    if name == 'Hypnotic Cloud':
        assert len(state.players[3-seat].hand) == (0 if kicked else 2)
    elif kicked:
        assert state.cards[target.id].zone == Zone.GRAVEYARD
    else:
        assert effective_toughness(state,target.id) == 2


@pytest.mark.parametrize('seat', [1,2])
@pytest.mark.parametrize('name', REMOVAL)
def test_union_candidates_exclude_owned_enchantments_and_opponent_creatures(seat,name):
    state,spell,artifact,creature,target = setup(name,seat)
    enchantment = raw_add(state,'Training Grounds',seat,cards=MODIFIERS)
    option = collect_cost_options(state,seat,spell)[1]
    assert option.sacrifice_kind == 'artifact_or_creature'
    assert set(additional_cost_candidates(state,seat,spell.id,option)['sacrifice_card_ids']) == {artifact.id,creature.id}
    for wrong in [enchantment,target]:
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state,RulesEngine(),seat,cast_action(spell,seat,True,wrong,target))
        assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1,2])
@pytest.mark.parametrize('difficulty', ['casual','strong','master'])
@pytest.mark.parametrize('name', REMOVAL)
def test_ai_paid_branch_targets_killable_creature_not_unproductive_larger_one(seat,difficulty,name):
    state,spell,artifact,_,target = setup(name,seat)
    large = raw_add(state,'Baloth Gorger',3-seat,cards=PERMANENTS)
    large.counters['+1/+1'] = 4
    move = next(m for m in RulesEngine().legal_moves(state,seat) if m.get('card_id') == spell.id)
    action = AIAgent(difficulty)._materialize_action(state,move,seat)
    assert action['cost_choice']['id'] == 'kicker'
    assert action['cost_choice']['sacrifice_card_ids'] == [artifact.id]
    assert action['targets']['target_card_id'] == target.id
    state = checked_action(state,RulesEngine(),seat,action)
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert effective_toughness(state,large.id) == 8


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name', REMOVAL)
def test_copy_keeps_paid_toughness_change_without_another_payment(seat,name):
    state,spell,artifact,_,target = setup(name,seat)
    state = checked_action(state,RulesEngine(),seat,cast_action(spell,seat,True,artifact,target))
    resolve_effect(state,seat,'copy_spell',{'target_stack_id':state.stack[-1].id})
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert state.cards[artifact.id].zone == Zone.GRAVEYARD
    assert state.kicked_spells_cast_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('indestructible', [False, True])
@pytest.mark.parametrize('anthem', [False, True])
@pytest.mark.parametrize('reduction', [2, 3, 4, 5, 6])
def test_negative_stat_projection_matches_actual_layers_without_mutating_state(
        seat, indestructible, anthem, reduction):
    from ai.pending_effects import negative_pt_would_be_lethal
    from rules_engine.state_based_actions import apply_state_based_actions
    state = board(seat)
    if indestructible:
        target = raw_add(state, 'Darksteel Myr', 3-seat, cards=ROWS)
        target.counters['+1/+1'] = 3
    else:
        target = raw_add(state, 'Baloth Gorger', 3-seat, cards=PERMANENTS)
    target.counters['__damage_marked'] = 2
    if anthem:
        raw_add(state, 'Glorious Anthem', 3-seat, cards=ROWS)
    before = serialize_match_snapshot(state)
    predicted = negative_pt_would_be_lethal(state, target.id, -reduction, -reduction)
    assert serialize_match_snapshot(state) == before
    assert predicted == (reduction >= (4 + int(anthem) - (0 if indestructible else 2)))
    resolve_effect(state, seat, 'temporary_pt_buff', {
        'target_card_id': target.id, 'power': -reduction, 'toughness': -reduction})
    apply_state_based_actions(state)
    assert (state.cards[target.id].zone == Zone.GRAVEYARD) == predicted


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('name', REMOVAL)
def test_ai_does_not_count_marked_damage_as_lethal_on_indestructible(seat, difficulty, name):
    state, spell, artifact, _, target = setup(name, seat)
    immune = raw_add(state, 'Darksteel Myr', 3-seat, cards=ROWS)
    immune.counters.update({'+1/+1': 7, '__damage_marked': 6})
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m.get('card_id') == spell.id)
    action = AIAgent(difficulty)._materialize_action(state, move, seat)
    assert action['cost_choice']['id'] == 'kicker'
    assert action['cost_choice']['sacrifice_card_ids'] == [artifact.id]
    assert action['targets']['target_card_id'] == target.id
    state = resolve(checked_action(state, RulesEngine(), seat, action))
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert state.cards[immune.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SPELLS)
@pytest.mark.parametrize('kicked', [False, True])
def test_http_canonical_payment_and_sqlite_restore(game, seat, name, kicked):
    import main
    from persistence.repository import Repository
    from persistence.db import engine
    from sqlmodel import Session
    client, controller = game
    state, spell, artifact, _, target = setup(name, seat)
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    moves = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}').json()['moves']
    move = next(m for m in moves if m.get('card_id') == spell.id)
    option = next(o for o in move['cost_options'] if o['id'] == 'kicker')
    if name != 'Hypnotic Cloud':
        assert artifact.id in option['sacrifice_card_ids']
        invalid = cast_action(spell, seat, True, None, target)
        rejected(client, controller, invalid, player_id=seat)
    action = cast_action(spell, seat, kicked, None if name == 'Hypnotic Cloud' else artifact, target)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    saved = serialize_match_snapshot(controller.state)
    main.ACTIVE_MATCHES.pop(state.id, None)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == saved
    restored = main.ACTIVE_MATCHES[state.id].state
    assert restored.stack[-1].payload['__kicked'] == kicked
    restored = resolve(restored)
    if name == 'Hypnotic Cloud':
        assert len(restored.players[3-seat].hand) == (0 if kicked else 2)
    else:
        assert (restored.cards[target.id].zone == Zone.GRAVEYARD) == kicked
