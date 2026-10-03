"""Canonical kicker payment, branch targets/effects, and durable provenance."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.costs import collect_cost_options
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.kicker import kicker_surfaces
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_surveil_mill import add, resolve
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/kicker.json').read_text())}


def setup(name, seat=1, free=False):
    state = board(seat)
    spell = raw_add(state, name, seat, Zone.GRAVEYARD if free else Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool.update(R=10, C=20, U=10, G=10)
    target = add(state, 'Grizzly Bears', seat if name == 'Gift of Growth' else 3-seat)
    if name == 'Shivan Fire':
        target.counters['+1/+1'] = 2
    if name == 'Gift of Growth':
        target.tapped = True
    if free:
        state.mechanic_choice_players = {seat}
        resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    return state, spell, target


def action(spell, target, seat, kicked, free=False):
    targets = {'target_card_id': target.id}
    if spell.name == 'Burst Lightning':
        targets = {'target_player': 3-seat}
    if spell.name == 'Fight with Fire' and kicked:
        targets = {'target_distribution': {target.id: 3, str(3-seat): 7}}
    return {'type': 'cast_spell', 'card_id': spell.id, 'from_graveyard': free,
            'cost_choice': {'id': 'kicker' if kicked else 'base'}, 'targets': targets}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
@pytest.mark.parametrize('kicked', [False, True])
@pytest.mark.parametrize('free', [False, True])
def test_canonical_effects_and_payments_preserve_printed_card(seat, name, kicked, free):
    state, spell, target = setup(name, seat, free)
    oracle = spell.oracle_text
    before_hand = len(state.players[seat].hand)
    before_mana = sum(state.players[seat].mana_pool.values())
    state = checked_action(state, RulesEngine(), seat, action(spell, target, seat, kicked, free))
    item = next(item for item in state.stack if item.source_card_id == spell.id)
    assert item.payload['__kicked'] is kicked
    assert state.cards[spell.id].oracle_text == oracle
    from rules_engine.mana import mana_value
    expected = (0 if free else mana_value(spell.mana_cost)) + (mana_value(kicker_surfaces(oracle)[0]) if kicked else 0)
    assert before_mana - sum(state.players[seat].mana_pool.values()) == expected
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    assert state.cards[spell.id].oracle_text == oracle
    if name == 'Burst Lightning':
        assert state.players[3-seat].life == (16 if kicked else 18)
    elif name == 'Shivan Fire':
        assert state.cards[target.id].zone == (Zone.GRAVEYARD if kicked else Zone.BATTLEFIELD)
    elif name == 'Gift of Growth':
        assert not state.cards[target.id].tapped
        assert effective_power(state, target.id) == effective_toughness(state, target.id) == (6 if kicked else 4)
    elif name == 'Into the Roil':
        assert target.id in state.players[3-seat].hand
        assert len(state.players[seat].hand) == before_hand - (0 if free else 1) + int(kicked)
    elif name == 'Fight with Fire':
        assert state.players[3-seat].life == (13 if kicked else 20)
        assert state.cards[target.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_only_kicked_branch_has_targets_without_creatures(seat):
    state, spell, target = setup('Fight with Fire', seat)
    state.players[3-seat].battlefield.remove(target.id)
    target.move_to_zone(Zone.GRAVEYARD)
    state.players[3-seat].graveyard.append(target.id)
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell.id)
    assert [option['id'] for option in move['cost_options']] == ['kicker']
    assert move['target_hints']['supports_divide']
    assert move['target_hints']['player_targets']


@pytest.mark.parametrize('seat', [1, 2])
def test_base_branch_hints_do_not_borrow_kicked_targets(seat):
    state, spell, _ = setup('Fight with Fire', seat)
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell.id)
    base, kicked = move['cost_options']
    assert not base['target_hints'].get('supports_divide')
    assert not base['target_hints'].get('player_targets')
    assert kicked['target_hints']['supports_divide']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id,
                       'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unaffordable_kicker_rejected_without_mutation(seat):
    state, spell, target = setup('Burst Lightning', seat)
    for color in state.players[seat].mana_pool:
        state.players[seat].mana_pool[color] = int(color == 'R')
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action(spell, target, seat, True))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('scenario', ['lethal', 'overkill', 'draw', 'division'])
def test_ai_materializes_useful_kicker_and_preserves_mana_when_redundant(seat, difficulty, scenario):
    name = {'lethal': 'Burst Lightning', 'overkill': 'Shivan Fire', 'draw': 'Into the Roil', 'division': 'Fight with Fire'}[scenario]
    state, spell, target = setup(name, seat)
    if scenario == 'lethal':
        state.players[3-seat].life = 4
    if scenario == 'overkill':
        target.counters.clear()
    if scenario == 'division':
        target.counters['+1/+1'] = 6
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell.id)
    materialized = AIAgent(difficulty=difficulty)._materialize_action(state, move, seat)
    assert materialized['cost_choice']['id'] == ('base' if scenario == 'overkill' else 'kicker')
    result = checked_action(state, RulesEngine(), seat, materialized)
    assert result.cards[spell.id].zone == Zone.STACK
    if scenario == 'division':
        assert sum(materialized['targets']['target_distribution'].values()) == 10


@pytest.mark.parametrize('seat', [1, 2])
def test_http_provenance_survives_restore_and_wrong_branch_target_rejected(game, seat):
    client, controller = game
    state, spell, target = setup('Fight with Fire', seat)
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    rejected(client, controller, {'type': 'cast_spell', 'card_id': spell.id,
              'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat}}, seat)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat,
                  'action': action(spell, target, seat, True)})
    assert response.status_code == 200, response.text
    assert controller.state.stack[-1].payload['__kicked'] is True
    from main import ACTIVE_MATCHES
    ACTIVE_MATCHES.pop(state.id)
    from main import _restore_active_matches
    from persistence.repository import Repository
    from persistence.db import engine
    from sqlmodel import Session
    with Session(engine) as session:
        _restore_active_matches(Repository(session))
    assert client.get(f'/matches/{state.id}').status_code == 200
    assert ACTIVE_MATCHES[state.id].state.stack[-1].payload['__kicked'] is True


def test_coverage_only_closes_recognized_single_mana_spell_surfaces():
    for row in ROWS.values():
        assert 'kicker' not in known_unsupported_mechanics(row['oracle_text'])
    for text in ['Kicker {B} and/or {R}.', 'Multikicker {1}.',
                 'Kicker {2}\nIf this creature was kicked, it enters with a counter.',
                 'Kicker {2}\nIf this spell was kicked, draw a card for each creature you control.',
                 'Kicker {2}\nIf this spell was kicked, gain one life.',
                 'Kicker {X}\nIf this spell was kicked, draw a card.']:
        assert kicker_surfaces(text) is None


def test_graveyard_alternative_keeps_its_method_when_kicked():
    from types import SimpleNamespace
    state, spell, _ = setup('Burst Lightning')
    # Syntax-only cost composition; no invented playable card or deck.
    syntax = SimpleNamespace(**vars(spell))
    syntax.oracle_text += '\nFlashback {2}{R}'
    syntax.zone = Zone.GRAVEYARD
    options = collect_cost_options(state, 1, syntax)
    assert [option.id for option in options] == ['flashback', 'flashback_kicker']
    assert options[1].kicked and options[1].kicker_base_id == 'flashback'


@pytest.mark.parametrize('seat', [1, 2])
def test_kicked_copy_keeps_effect_provenance_without_paying_again(seat):
    from effects.handlers import copy_spell
    state, spell, target = setup('Fight with Fire', seat)
    state = checked_action(state, RulesEngine(), seat, action(spell, target, seat, True))
    mana = dict(state.players[seat].mana_pool)
    copy_spell(state, seat, {'target_stack_id': state.stack[-1].id})
    assert state.stack[-1].payload['__kicked'] is True
    assert state.stack[-1].payload['__copied_card']['oracle_text'] == spell.oracle_text
    assert state.players[seat].mana_pool == mana
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    assert state.players[3-seat].life == 6


@pytest.mark.parametrize('seat', [1, 2])
def test_bounce_conditional_draw_does_not_resolve_after_sole_target_leaves(seat):
    state, spell, target = setup('Into the Roil', seat)
    state = checked_action(state, RulesEngine(), seat, action(spell, target, seat, True))
    resolve_effect(state, 3-seat, 'return_permanent_to_hand', {'target_card_id': target.id})
    state = resolve(state)
    assert not state.players[seat].hand
    assert any('does not resolve' in line for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('barrier', ['hexproof', 'indestructible'])
def test_ai_does_not_buy_damage_breakpoint_against_immune_creature(seat, difficulty, barrier):
    state, spell, target = setup('Burst Lightning', seat)
    target.counters['+1/+1'] = 2
    target.counters[barrier] = 1
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell.id)
    materialized = AIAgent(difficulty=difficulty)._materialize_action(state, move, seat)
    assert materialized['cost_choice']['id'] == 'base'
    checked_action(state, RulesEngine(), seat, materialized)


@pytest.mark.parametrize('seat', [1, 2])
def test_human_kicked_copy_offer_uses_enhanced_recipient_surface(seat):
    from effects.handlers import copy_spell
    state, spell, target = setup('Fight with Fire', seat)
    state = checked_action(state, RulesEngine(), seat, action(spell, target, seat, True))
    state.mechanic_choice_players = {seat}
    copy_spell(state, seat, {'target_stack_id': state.stack[-1].id, 'may_choose_new_targets': True})
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'copy_target'
    assert any(option.startswith('target_player:') for option in pending['options'])
    assert state.stack[-1].payload['__copied_card']['oracle_text'] == spell.oracle_text
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic',
                           'card_ids': [f'target_player:{seat}']})
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    state = resolve(state)
    assert state.players[seat].life == 17
    assert state.players[3-seat].life == 6
