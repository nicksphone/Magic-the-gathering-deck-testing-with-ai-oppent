"""Canonical life/typed-sacrifice kicker, not modified competitive decks."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.costs import collect_cost_options, additional_cost_candidates
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.kicker import kicker_cost
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_permanent_kicker import ROWS as PERMANENTS
from tests.test_surveil_mill import add, resolve
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/nonmana_kicker.json').read_text())}


def setup(name, seat=1, free=False):
    state = board(seat)
    spell = raw_add(state, name, seat, Zone.GRAVEYARD if free else Zone.HAND, cards=ROWS)
    payers = ([add(state, 'Grizzly Bears', seat)] if name == 'Vicious Offering' else
              [add(state, 'Swamp', seat), add(state, 'Island', seat)] if name == 'Bog Down' else [])
    target = raw_add(state, 'Baloth Gorger', 3-seat, cards=PERMANENTS)
    if name == 'Bog Down':
        for land in ['Swamp', 'Island', 'Swamp']:
            add(state, land, 3-seat, Zone.HAND)
    state.players[seat].mana_pool.update(B=10, C=20)
    if free:
        state.mechanic_choice_players = {seat}
        if name != 'Phyrexian Scuta':
            resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    return state, spell, payers, target


def announcement(spell, seat, kicked, payers=(), target=None, free=False):
    targets = ({'target_player':3-seat} if spell.name == 'Bog Down' else
               {'target_card_id':target.id} if spell.name == 'Vicious Offering' else {})
    return {'type':'cast_spell', 'card_id':spell.id, 'from_graveyard':free, 'targets':targets,
            'cost_choice':{'id':'kicker' if kicked else 'base',
                           'sacrifice_card_ids':[card.id for card in payers] if kicked else []}}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
@pytest.mark.parametrize('free', [False, True])
@pytest.mark.parametrize('kicked', [False, True])
def test_real_paid_unpaid_resolution_and_snapshot(seat, name, free, kicked):
    state, spell, payers, target = setup(name, seat, free)
    text = spell.oracle_text
    options = collect_cost_options(state, seat, spell, without_mana=free)
    assert [o.id for o in options] == ['base','kicker']
    assert 'kicker' not in known_unsupported_mechanics(text)
    before_mana = sum(state.players[seat].mana_pool.values())
    action = announcement(spell, seat, kicked, payers, target, free)
    if free and name == 'Phyrexian Scuta':
        # Core authorized-cost contract only: do not invent a creature permission
        # on the existing instant/sorcery-only graveyard-cast effect.
        from rules_engine.effect_casts import admit_cast
        admit_cast(state, seat, action, {'target_card_id': spell.id})
    else:
        state = checked_action(state, RulesEngine(), seat, action)
    assert state.stack[-1].payload['__kicked'] is kicked
    assert state.players[seat].life == 20 - (3 if kicked and name == 'Phyrexian Scuta' else 0)
    for payer in payers:
        assert state.cards[payer.id].zone == (Zone.GRAVEYARD if kicked else Zone.BATTLEFIELD)
    from rules_engine.mana import mana_value
    assert before_mana - sum(state.players[seat].mana_pool.values()) == (0 if free else mana_value(spell.mana_cost))
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    assert state.cards[spell.id].oracle_text == text
    if name == 'Phyrexian Scuta':
        assert effective_power(state, spell.id) == effective_toughness(state, spell.id) == (5 if kicked else 3)
    elif name == 'Bog Down':
        assert len(state.players[3-seat].hand) == (0 if kicked else 1)
    elif kicked:
        assert state.cards[target.id].zone == Zone.GRAVEYARD
    else:
        assert effective_toughness(state, target.id) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Vicious Offering','Bog Down'])
@pytest.mark.parametrize('bad', ['missing','duplicate','opponent','wrong-type'])
def test_invalid_payment_is_atomic_before_mana_and_departures(seat, name, bad):
    state, spell, payers, target = setup(name, seat)
    action = announcement(spell, seat, True, payers, target)
    ids = action['cost_choice']['sacrifice_card_ids']
    if bad == 'missing': ids.pop()
    elif bad == 'duplicate': ids[:] = [payers[0].id] * 2
    elif bad == 'opponent': ids[0] = target.id
    else:
        wrong = add(state, 'Island' if name == 'Vicious Offering' else 'Grizzly Bears', seat)
        ids[0] = wrong.id
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected): checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_insufficient_life_rejected_but_unpaid_branch_remains_legal(seat):
    state, spell, _, _ = setup('Phyrexian Scuta', seat)
    state.players[seat].life = 2
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, announcement(spell, seat, True))
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat, announcement(spell, seat, False))
    assert state.players[seat].life == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_copied_permanent_preserves_paid_choice_without_second_life_payment(seat):
    state, spell, _, _ = setup('Phyrexian Scuta', seat)
    state = checked_action(state, RulesEngine(), seat, announcement(spell, seat, True))
    resolve_effect(state, seat, 'copy_spell', {'target_stack_id':state.stack[-1].id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    copies = [c for c in state.cards.values() if c.name == spell.name and c.zone == Zone.BATTLEFIELD]
    assert len(copies) == 2 and all(effective_power(state, c.id) == 5 for c in copies)
    assert state.players[seat].life == 17
    assert state.kicked_spells_cast_this_turn[seat] == 1


@pytest.mark.parametrize('difficulty', ['casual','strong','master'])
@pytest.mark.parametrize('life,choice', [(20,'kicker'),(5,'base'),(3,'base')])
def test_ai_trades_life_for_counters_without_buying_a_losing_branch(difficulty, life, choice):
    state, spell, _, _ = setup('Phyrexian Scuta')
    state.players[1].life = life
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == spell.id)
    action = AIAgent(difficulty)._materialize_action(state, move, 1)
    assert action['cost_choice']['id'] == choice


@pytest.mark.parametrize('difficulty', ['casual','strong','master'])
@pytest.mark.parametrize('useful', [False, True])
def test_ai_sacrifice_requires_a_payoff_and_selects_checked_cost_card(difficulty, useful):
    state, spell, payers, target = setup('Vicious Offering')
    if not useful:
        resolve_effect(state, 1, 'deal_damage', {'target_card_id':target.id,'amount':2})
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == spell.id)
    action = AIAgent(difficulty)._materialize_action(state, move, 1)
    assert action['cost_choice']['id'] == ('kicker' if useful else 'base')
    if useful:
        assert action['cost_choice']['sacrifice_card_ids'] == [payers[0].id]
    checked_action(state, RulesEngine(), 1, action)


def test_unknown_nonmana_forms_and_mixed_mandatory_types_warn():
    # Syntax-only diagnostics, not invented playable card fixtures.
    unknown = 'Kicker\u2014Tap an untapped Vampire you control.\nIf this creature was kicked, it enters with two +1/+1 counters on it.'
    assert 'kicker' in known_unsupported_mechanics(unknown)
    mixed = ROWS['Vicious Offering']['oracle_text'] + '\nAs an additional cost to cast this spell, sacrifice a land.'
    assert 'unsupported mixed sacrifice cost' in known_unsupported_mechanics(mixed)


def test_fixed_cost_components_are_shared_and_land_candidates_are_exact():
    state, spell, payers, target = setup('Bog Down')
    assert kicker_cost(spell) == {'mana_cost':'','sacrifice_creatures':2,'sacrifice_kind':'land'}
    option = collect_cost_options(state, 1, spell)[1]
    assert set(additional_cost_candidates(state, 1, spell.id, option)['sacrifice_card_ids']) == {c.id for c in payers}
    assert target.id not in additional_cost_candidates(state, 1, spell.id, option)['sacrifice_card_ids']


@pytest.mark.parametrize('seat', [1, 2])
def test_sacrifice_cost_preserves_real_dies_payoff(seat):
    state, spell, payers, target = setup('Vicious Offering', seat)
    artist = raw_add(state, 'Zulaport Cutthroat', seat)
    state = checked_action(state, RulesEngine(), seat, announcement(spell, seat, True, payers, target))
    assert any(item.source_card_id == artist.id for item in state.stack)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    assert state.players[3-seat].life == 19 and state.players[seat].life == 21


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
def test_http_payment_metadata_atomic_rejection_and_restore(game, seat, name):
    client, controller = game
    state, spell, payers, target = setup(name, seat)
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    moves = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}').json()['moves']
    move = next(m for m in moves if m.get('card_id') == spell.id)
    option = next(o for o in move['cost_options'] if o['id'] == 'kicker')
    if payers:
        assert set(option['sacrifice_card_ids']) == {c.id for c in payers}
    else:
        assert option['pay_life'] == 3
    invalid = announcement(spell, seat, True, payers, target)
    if payers:
        invalid['cost_choice']['sacrifice_card_ids'] = []
    else:
        state.players[seat].life = 2
        persist(controller)
    rejected(client, controller, invalid, player_id=seat)
    controller.state.players[seat].life = 20
    persist(controller)
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id':seat,'action':announcement(spell, seat, True, payers, target)})
    assert response.status_code == 200, response.text
    import main
    main.ACTIVE_MATCHES.pop(state.id, None)
    from persistence.repository import Repository
    from persistence.db import engine
    from sqlmodel import Session
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = client.get(f'/matches/{state.id}')
    assert restored.status_code == 200
    assert restored.json()['players'][str(seat)]['life'] == (17 if name == 'Phyrexian Scuta' else 20)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('victim', ['self', 'friendly', 'opponent'])
def test_controller_scoped_self_or_other_dies_is_exact(seat, victim):
    state = board(seat)
    source = raw_add(state, 'Zulaport Cutthroat', seat)
    dead = source if victim == 'self' else add(state, 'Grizzly Bears', seat if victim == 'friendly' else 3-seat)
    from rules_engine.zone_actions import sacrifice_selected
    assert sacrifice_selected(state, dead.controller, [dead.id])
    assert len([item for item in state.stack if item.source_card_id == source.id]) == int(victim != 'opponent')
