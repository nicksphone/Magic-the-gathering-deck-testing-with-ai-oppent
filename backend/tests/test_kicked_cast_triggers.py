"""Canonical kicked-cast consumers, first-kicked discounts and payoff guards."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Zone, Step
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.continuous import effective_power, has_keyword, printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_surveil_mill import resolve
from tests.test_kicker import setup as spell_setup
from tests.test_permanent_kicker import setup as permanent_setup

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent/'fixtures/kicked_cast_triggers.json').read_text())}


def source(state, name, seat=1, zone=Zone.BATTLEFIELD):
    card = raw_add(state, name, seat, zone, cards=ROWS)
    card.summoning_sick = False
    return card


def cast(state, spell, seat, kicked=True):
    return checked_action(state, RulesEngine(), seat, {
        'type':'cast_spell', 'card_id':spell.id, 'cost_choice':{'id':'kicker' if kicked else 'base'},
        'targets':{'target_player':3-seat} if spell.name == 'Burst Lightning' else {}})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
@pytest.mark.parametrize('kicked', [False, True])
@pytest.mark.parametrize('opponent_source', [False, True])
def test_only_actual_controller_kicked_cast_triggers(seat, name, kicked, opponent_source):
    state, spell, _ = spell_setup('Burst Lightning', seat)
    payoff = source(state, name, 3-seat if opponent_source else seat)
    state = cast(state, spell, seat, kicked)
    triggers = [item for item in state.stack if item.source_card_id == payoff.id]
    assert len(triggers) == int(kicked and not opponent_source)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    if kicked and not opponent_source:
        if name == 'Risen Riptide':
            assert effective_power(state, payoff.id) == 5
            assert state.cards[payoff.id].power == 0
            assert not printed_abilities_suppressed(state, payoff.id)
            RulesEngine()._clear_marked_damage(state)
            assert effective_power(state, payoff.id) == 0
        elif name == 'Vine Gecko':
            assert state.cards[payoff.id].counters['+1/+1'] == 1
        else:
            tokens = [c for c in state.cards.values() if c.is_token and c.zone == Zone.BATTLEFIELD]
            assert len(tokens) == 1 and has_keyword(state, tokens[0].id, 'flying')


@pytest.mark.parametrize('name', list(ROWS))
def test_spell_copy_does_not_publish_another_cast_trigger(name):
    state, spell, _ = spell_setup('Burst Lightning')
    payoff = source(state, name)
    state = cast(state, spell, 1)
    spell_item = next(i for i in state.stack if i.source_card_id == spell.id)
    resolve_effect(state, 1, 'copy_spell', {'target_stack_id':spell_item.id})
    assert len([i for i in state.stack if i.source_card_id == payoff.id]) == 1
    assert state.kicked_spells_cast_this_turn[1] == 1


@pytest.mark.parametrize('name', ['Risen Riptide', 'Vine Gecko'])
def test_self_payoff_does_not_follow_blinked_source(name):
    state, spell, _ = spell_setup('Burst Lightning')
    payoff = source(state, name)
    state = cast(state, spell, 1)
    resolve_effect(state, 1, 'return_permanent_to_hand', {'target_card_id':payoff.id})
    card = state.cards[payoff.id]
    state.players[1].hand.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[1].battlefield.append(card.id)
    from game_state.state import assign_static_order_on_battlefield_entry
    assign_static_order_on_battlefield_entry(state, card.id)
    state = resolve(state)
    assert effective_power(state, card.id) == card.power
    assert not state.cards[card.id].counters.get('+1/+1')


@pytest.mark.parametrize('seat', [1, 2])
def test_first_kicked_discount_counts_casts_not_copies_and_resets_each_turn(seat):
    state, spell, _ = spell_setup('Burst Lightning', seat)
    source(state, 'Vine Gecko', seat)
    state.players[seat].mana_pool = {'R':1, 'C':3, 'W':0, 'U':0, 'B':0, 'G':0}
    state = cast(state, spell, seat)
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.kicked_spells_cast_this_turn[seat] == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    from tests.test_kicker import ROWS as SPELLS
    second = raw_add(state, 'Burst Lightning', seat, Zone.HAND, cards=SPELLS)
    state.players[seat].mana_pool.update(R=1, C=3)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, second, seat)
    assert serialize_match_snapshot(state) == before
    state.players[seat].mana_pool['C'] = 4
    state = cast(state, second, seat)
    assert state.kicked_spells_cast_this_turn[seat] == 2
    state = resolve(state)
    state.step = Step.CLEANUP
    state.active_player = seat
    RulesEngine().next_step(state)
    assert state.kicked_spells_cast_this_turn == {1:0, 2:0}


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('name', ['Baloth Gorger', 'Citanul Woodreaders'])
def test_ai_does_not_pay_for_prohibited_or_decking_payoff(difficulty, name):
    state, card, _ = permanent_setup(name)
    if name == 'Baloth Gorger':
        from tests.test_counter_prohibitions import source as prohibition
        prohibition(state, 'Solemnity')
    else:
        state.players[1].library = state.players[1].library[:1]
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == card.id)
    action = AIAgent(difficulty)._materialize_action(state, move, 1)
    assert action['cost_choice']['id'] == 'base'


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_ai_values_ready_kicked_cast_payoff_without_always_paying(difficulty):
    state, spell, _ = spell_setup('Burst Lightning')
    source(state, 'Risen Riptide')
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == spell.id)
    assert AIAgent(difficulty)._materialize_action(state, move, 1)['cost_choice']['id'] == 'kicker'
    state = cast(state, spell, 1)
    state = resolve(state)
    from tests.test_kicker import ROWS as SPELLS
    second = raw_add(state, 'Burst Lightning', 1, Zone.HAND, cards=SPELLS)
    state.players[1].mana_pool.update(R=10,C=10)
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == second.id)
    assert AIAgent(difficulty)._materialize_action(state, move, 1)['cost_choice']['id'] == 'base'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kicked', [False, True])
def test_roost_entry_and_later_cast_are_distinct_trigger_events(seat, kicked):
    state, _, _ = spell_setup('Burst Lightning', seat)
    roost = source(state, 'Roost of Drakes', seat, Zone.HAND)
    state = cast(state, roost, seat, kicked)
    assert len(state.stack) == 1  # An off-battlefield Roost cannot see its own cast.
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    tokens = lambda: [card for card in state.cards.values() if card.is_token and card.zone == Zone.BATTLEFIELD]
    assert len(tokens()) == int(kicked)
    from tests.test_kicker import ROWS as SPELLS
    bolt = raw_add(state, 'Burst Lightning', seat, Zone.HAND, cards=SPELLS)
    state = cast(state, bolt, seat)
    state = resolve(state)
    assert len(tokens()) == int(kicked) + 1
    assert all(card.name == 'Drake' and card.colors == ['U'] and has_keyword(state, card.id, 'flying') for card in tokens())


@pytest.mark.parametrize('name', list(ROWS))
def test_suppressed_payoffs_and_discounts_do_not_apply(name):
    state, spell, _ = spell_setup('Burst Lightning')
    payoff = source(state, name)
    resolve_effect(state, 2, 'temporary_ability_loss', {'target_card_id':payoff.id})
    before = sum(state.players[1].mana_pool.values())
    state = cast(state, spell, 1)
    assert not [item for item in state.stack if item.source_card_id == payoff.id]
    assert before - sum(state.players[1].mana_pool.values()) == 5


@pytest.mark.parametrize('seat', [1, 2])
def test_two_first_kicked_discounts_stack_but_do_not_reduce_unpaid_base(seat):
    state, spell, _ = spell_setup('Burst Lightning', seat)
    source(state, 'Vine Gecko', seat)
    source(state, 'Vine Gecko', seat)
    state.players[seat].mana_pool = {'R':1,'C':2,'W':0,'U':0,'B':0,'G':0}
    state = cast(state, spell, seat)
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.kicked_spells_cast_this_turn[seat] == 1


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_ai_does_not_buy_draws_blocked_by_existing_limit(difficulty):
    from tests.test_static_ability_suppression import add
    state, card, _ = permanent_setup('Citanul Woodreaders')
    add(state, 'Spirit of the Labyrinth', 2)
    state.draws_this_turn[1] = 1
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m.get('card_id') == card.id)
    action = AIAgent(difficulty)._materialize_action(state, move, 1)
    assert action['cost_choice']['id'] == 'base'


def test_unknown_kicked_trigger_and_multiple_cost_forms_remain_warned():
    assert 'kicked-cast trigger fidelity' in known_unsupported_mechanics(
        'Whenever you cast a kicked spell, exile each opponent.')
    for row in ROWS.values():
        assert 'kicked-cast trigger fidelity' not in known_unsupported_mechanics(row['oracle_text'])
    assert 'kicker' not in known_unsupported_mechanics(ROWS['Roost of Drakes']['oracle_text'])
    assert 'kicker' in known_unsupported_mechanics('Kicker {U} and/or {R}.')


@pytest.mark.parametrize('seat', [1, 2])
def test_countered_cast_still_consumes_first_kicked_discount(seat):
    state, spell, _ = spell_setup('Burst Lightning', seat)
    source(state, 'Vine Gecko', seat)
    state = cast(state, spell, seat)
    item = next(item for item in state.stack if item.source_card_id == spell.id)
    resolve_effect(state, 3-seat, 'counter_spell', {'target_stack_id':item.id})
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert state.kicked_spells_cast_this_turn[seat] == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    from tests.test_kicker import ROWS as SPELLS
    second = raw_add(state, 'Burst Lightning', seat, Zone.HAND, cards=SPELLS)
    state.players[seat].mana_pool = {'R':1,'C':3,'W':0,'U':0,'B':0,'G':0}
    with pytest.raises(ActionRejected):
        cast(state, second, seat)
