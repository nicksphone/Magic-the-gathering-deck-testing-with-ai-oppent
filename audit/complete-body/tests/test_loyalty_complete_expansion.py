"""Printed full bodies, generic variants, and paid complete loyalty execution."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import test_paid_context_goldens as c
from test_closed_loyalty import synthetic_receipt, TAILS
from game_state.state import Step, Zone
from rules_engine.closed_loyalty import compile_body
from rules_engine.oracle_effects import extract_loyalty_abilities
from rules_engine.continuous import effective_power, has_keyword
from tests.test_counter_replacements import ROWS as REPLACEMENTS
from tests.test_counter_prohibitions import ROWS as PROHIBITIONS

ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT.parents[1]/'backend/card_data/builtin_oracle_seed.json').read_text())['cards']
WALKERS = {name: row for name, row in SEED.items() if 'Planeswalker' in row.get('type_line', '')}
WALKERS["Elspeth, Sun's Champion"] = PROHIBITIONS["Elspeth, Sun's Champion"]
facts = c.facts


def test_public_body_receipt_rejects_invalid_types_and_unbounded_numeric_tokens():
    assert compile_body(None, 'Generic') is None
    assert compile_body('+1: Draw a card.', None) is None
    for digits in ('9' * 11, '9' * 5000):
        assert compile_body('+1: You gain ' + digits + ' life.', 'Generic') is None
        assert compile_body('+1: You gain ' + digits + ' life, draw one card, then put up to one permanent card from your hand onto the battlefield.', 'Generic') is None


@pytest.mark.parametrize('name', list(WALKERS))
@pytest.mark.parametrize('renamed', [False, True])
def test_every_printed_whole_body_and_generic_source_rename(name, renamed):
    raw = WALKERS[name]
    new_name = 'Renamed, Generic Walker' if renamed else name
    text = raw['oracle_text']
    if renamed:
        text = text.replace(name, new_name).replace(name.split(',', 1)[0] + "'s", "Renamed's")
        text = text.replace(name.split(',', 1)[0] + ' deals', 'Renamed deals')
    compiled = compile_body(text, new_name)
    assert compiled is not None
    assert len(compiled['abilities']) == sum(':' in line and line.strip()[0] in '+-\u22120123456789' for line in text.splitlines())
    for tail in TAILS:
        assert compile_body(text + tail, new_name) is None


def settle(state, bound=144):
    """Only actual public choices/passes; snapshot recovery at every boundary."""
    for _ in range(bound):
        state = c.cold(state)
        if state.pending_mechanic_choice:
            pending = state.pending_mechanic_choice
            seat = pending['player_id']
            moves = c.offers(state, seat)
            assert moves and moves[0]['type'] == 'choose_mechanic'
            if pending['kind'] in {'loyalty_cards', 'search_library', 'discard', 'cleanup_discard'}:
                ids = list(pending['options'])[:pending['count']]
                state = c.act(state, seat, {'type': 'choose_mechanic', 'card_ids': ids})
            else:
                assert pending['kind'] == 'land_entry', pending
                state = c.act(state, seat, {'type': 'choose_mechanic', 'choice_id': pending['options'][0]})
        elif state.pending_replacement_choice:
            pending = state.pending_replacement_choice
            state = c.act(state, pending['player_id'], c.offers(state, pending['player_id'])[0])
        elif state.pending_trigger_order:
            seat = state.pending_trigger_order['current_controller']
            state = c.act(state, seat, c.offers(state, seat)[0])
        elif state.stack:
            state = c.act(state, state.priority_player, {'type': 'pass_priority'})
        else:
            return state
    raise AssertionError('144 public action bound')


CASES = [(name, index) for name, raw in WALKERS.items()
         for index in range(sum(':' in line and line.strip()[0] in '+-\u22120123456789' for line in raw['oracle_text'].splitlines()))]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,index', CASES)
def test_real_paid_printed_ability_resolution(facts, seat, name, index, request):
    c.ACTIONS.clear()
    rows = deepcopy(facts)
    rows.update(deepcopy(WALKERS))
    rows['Doubling Season'] = deepcopy(REPLACEMENTS['Doubling Season'])
    state = c.g.position(rows, seat)
    for owner in (1, 2):
        for _ in range(24):
            c.g.add(state, rows, 'Forest', owner, Zone.LIBRARY)
    # Declared canonical resident counter/token modifier makes all printed costs affordable.
    c.g.add(state, rows, 'Doubling Season', seat)
    land = c.g.add(state, rows, 'Forest', seat)
    state.cards[land].tapped = True
    creature = c.g.add(state, rows, 'Suncleanser', seat)
    other = c.g.add(state, rows, 'Suncleanser', 3-seat)
    binding = c.g.add(state, rows, 'Leyline Binding', 3-seat)
    # Two actual library Forests seed later optional hand entry after draws.
    source = c.g.add(state, rows, name, seat, Zone.HAND)
    from rules_engine.mana import parse_mana_cost
    mana = parse_mana_cost(rows[name]['mana_cost'])
    # Printed phyrexian costs paid entirely with colored mana, not a life waiver.
    pool = {key: value for key, value in mana.items() if key in 'WUBRGC' and value}
    if mana.get('generic'):
        pool['C'] = pool.get('C', 0) + mana['generic']
    state, frame = c.paid(state, seat, source, pool)
    state = settle(state)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    state = c.priority(state, seat)
    ability = extract_loyalty_abilities(state.cards[source])[index]
    assert effective_power(state, creature) == 1
    assert not has_keyword(state, creature, 'flying')
    text = ability['text'].lower()
    targets = {}
    if 'damage to any target' in text or 'target player' in text:
        targets = {'target_player': 3-seat}
    elif 'target noncreature land' in text:
        targets = {'target_card_id': land}
    elif 'target tapped creature' in text:
        state.cards[creature].tapped = True
        targets = {'target_card_id': creature}
    elif 'target creature' in text:
        targets = {'target_card_id': creature}
    elif 'target artifact' in text or 'target nonland permanent' in text:
        targets = {'target_card_id': binding}
    if ability['x_cost']:
        targets['x_value'] = 2
    loyalty_before = state.cards[source].loyalty
    hand_before = len(state.players[seat].hand)
    life_before = state.players[seat].life
    enemy_life = state.players[3-seat].life
    tokens_before = {cid for cid, card in state.cards.items() if card.is_token}
    emblem_before = len(state.emblems)
    state = c.act(state, seat, {'type': 'activate_loyalty', 'card_id': source,
        'ability_index': index, 'targets': targets})
    expected_cost = -2 if ability['x_cost'] else ability['delta']
    if state.cards[source].zone == Zone.BATTLEFIELD:
        assert state.cards[source].loyalty == loyalty_before + expected_cost
    else:
        assert loyalty_before + expected_cost == 0
        assert state.cards[source].last_known_battlefield['loyalty'] == 0
    state = settle(state)
    if 'create' in text:
        tokens = [card for cid, card in state.cards.items() if card.is_token and cid not in tokens_before]
        assert tokens
        if 'loyalty' in text:
            assert len(tokens) == 2 and all(card.power == state.cards[source].loyalty for card in tokens)
    if 'damage to any target' in text:
        assert state.players[3-seat].life == enemy_life - 3
    if 'destroy target' in text:
        assert state.cards[binding].zone == Zone.GRAVEYARD
    if 'target noncreature land' in text:
        assert 'Creature' in state.cards[land].types or effective_power(state, land) == 6
        assert not state.cards[land].tapped and has_keyword(state, land, 'vigilance') and has_keyword(state, land, 'haste')
    if "owner's library" in text:
        assert state.cards[binding].zone == Zone.LIBRARY
        assert state.players[3-seat].library[-3] == binding
    if "owner's hand" in text:
        assert state.cards[binding].zone == Zone.HAND
        assert len(state.players[seat].hand) == hand_before + 1
    if 'one or more colors' in text:
        assert state.cards[other].zone == Zone.EXILE
        assert state.cards[land].zone == Zone.BATTLEFIELD
    if 'you gain 7 life, draw' in text:
        assert state.players[seat].life == life_before + 7
        assert len(state.players[seat].hand) >= hand_before
        assert len(state.players[seat].battlefield) >= 10
    if 'emblem' in text:
        assert len(state.emblems) == emblem_before + 1
        assert state.cards[state.emblems[-1]].zone == Zone.COMMAND
        assert all(cid not in p.battlefield for cid in state.emblems for p in state.players.values())
        if 'creatures you control get' in text:
            assert effective_power(state, creature) == 3 and has_keyword(state, creature, 'flying')
        if 'lands you control have' in text:
            assert has_keyword(state, land, 'indestructible')
    if 'for each forest' in text:
        assert effective_power(state, creature) > 1 and has_keyword(state, creature, 'trample')
    if 'as though they had flash' in text:
        assert state.loyalty_permissions
    if 'next end step' in text:
        assert state.delayed_triggers
        for _ in range(64):
            if state.step == Step.END_STEP:
                break
            state = c.act(state, state.priority_player, {'type': 'pass_priority'})
            state = settle(state)
        assert state.step == Step.END_STEP
        state = settle(state)
        assert not state.delayed_triggers and not state.cards[land].tapped
    synthetic_receipt(request, c.cold(state), rows[name], printed_canonical_paid=True,
                      declared_resident_modifier='Doubling Season', ability_index=index)
