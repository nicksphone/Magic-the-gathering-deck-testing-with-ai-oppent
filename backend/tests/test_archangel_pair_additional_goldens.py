"""Additional paid split-target/LKI goldens; detached compiler probes labeled."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from game_state.state import Zone, object_incarnation
from rules_engine.continuous import has_keyword, effective_power, effective_toughness
from rules_engine.kicker import paired_permanent_kicker
from rules_engine.targeting import stack_object_kind
from tests.test_archangel_pair_paid_desired import (
    ROWS, RULES, g, act, cold, setup, cast_pair, enter, targets, response, advance)
from tests.test_static_ability_suppression import CARDS


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('episode', ['none', 'counter-player', 'counter-creature', 'fizzle-creature'])
def test_paid_split_targets_deliberate_order_and_independent_response(seat, episode):
    state, source = setup(seat)
    victim = g.add(state, ROWS, 'Wall of Omens', 3-seat, Zone.BATTLEFIELD)
    state, spell = cast_pair(state, source, seat, 'kicker_1_2', 2, ('B', 'R'))
    state = advance(state, lambda s: all(i.id != spell for i in s.stack))
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.cards[source].kicker_count == 2 and state.cards[source].was_kicked
    assert has_keyword(state, source, 'flying') and has_keyword(state, source, 'lifelink')
    pending = state.pending_trigger_order
    assert pending and 'phase' not in pending and not state.stack
    group = pending['groups'][str(seat)]
    assert len(group) == 2 and all(t['effect_key'] == 'deal_damage' and t['payload']['amount'] == 2 for t in group)
    order = next(m for m in RULES.legal_moves(state, seat) if m['type'] == 'choose_trigger_order'
                 and m['trigger_order'] == [t['_choice_id'] for t in reversed(group)])
    expected_clauses = [t['payload']['__trigger_full_clause'] for t in reversed(group)]
    state = act(cold(state), seat, deepcopy(order))
    assert state.pending_trigger_order['phase'] == 'targets'
    assert [i.payload['__trigger_full_clause'] for i in state.stack] == expected_clauses
    for _ in range(2):
        moves = RULES.legal_moves(state, seat)
        stack_id = moves[0]['stack_id']
        item = next(i for i in state.stack if i.id == stack_id)
        target = ({'target_card_id': victim} if 'kicked twice' in item.payload['__trigger_full_clause'].lower()
                  else {'target_player': 3-seat})
        move = next(m for m in moves if m['type'] == 'choose_trigger_target' and m['stack_id'] == stack_id
                    and all(m.get(k) == v for k, v in target.items()))
        state = act(cold(state), seat, deepcopy(move))
    assert not state.pending_trigger_order and len(state.stack) == 2
    assert all(stack_object_kind(state, i) == 'triggered' and i.payload['amount'] == 2 for i in state.stack)
    player_frame = next(i.id for i in state.stack if i.payload.get('target_player') == 3-seat)
    creature_frame = next(i.id for i in state.stack if i.payload.get('target_card_id') == victim)
    assert player_frame != creature_frame
    if episode.startswith('counter-'):
        removed = player_frame if episode == 'counter-player' else creature_frame
        retained = creature_frame if removed == player_frame else player_frame
        state = response(state, 3-seat, 'Stifle', {'U': 1}, {'target_stack_id': removed})
        assert {i.id for i in state.stack} == {retained}
    elif episode == 'fizzle-creature':
        state = response(state, 3-seat, 'Unsummon', {'U': 1}, {'target_card_id': victim})
        assert state.cards[victim].zone == Zone.HAND
        assert {i.id for i in state.stack} == {player_frame, creature_frame}
    state = advance(cold(state), lambda s: not s.stack)
    player_damage = 0 if episode == 'counter-player' else 2
    creature_damage = 2 if episode in ('none', 'counter-player') else 0
    assert state.players[3-seat].life == 20 - player_damage
    assert state.players[seat].life == 20 + player_damage + creature_damage
    if episode != 'fizzle-creature':
        assert state.cards[victim].zone == Zone.BATTLEFIELD and state.cards[victim].counters.get('__damage_marked', 0) == creature_damage
    assert state.cards[source].kicker_count == 2 and state.cards[source].was_kicked


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_source_return_retains_explicit_count_and_lifelink_in_old_lki(seat):
    state, source = setup(seat)
    state, spell = cast_pair(state, source, seat, 'kicker_1_2', 2, ('B', 'R'))
    state, entries = enter(state, source, seat, 2, spell, {'target_player': 3-seat})
    old_ref = object_incarnation(state.cards[source])
    state = response(state, 3-seat, 'Unsummon', {'U': 1}, {'target_card_id': source})
    assert state.cards[source].zone == Zone.HAND and state.cards[source].kicker_count is None
    assert not state.cards[source].was_kicked
    assert {i.id for i in state.stack} == set(entries)
    for item in state.stack:
        lki = item.payload['__source_lki']
        assert lki['battlefield_incarnation'] == old_ref and lki['controller'] == seat
        assert lki['kicker_count'] == 2 and lki['was_kicked'] is True
        assert {'flying', 'lifelink'} <= set(lki['keywords'])
    state = advance(cold(state), lambda s: not s.stack)
    assert state.players[seat].life == 24 and state.players[3-seat].life == 16


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_entry_under_canonical_public_humility_has_no_abilities_or_etbs(seat):
    state, source = setup(seat)
    g.add(state, CARDS, 'Humility', 3-seat, Zone.BATTLEFIELD)
    state, spell = cast_pair(state, source, seat, 'kicker_1_2', 2, ('B', 'R'))
    state = advance(state, lambda s: all(i.id != spell for i in s.stack))
    assert state.cards[source].zone == Zone.BATTLEFIELD and state.cards[source].kicker_count == 2
    assert state.cards[source].was_kicked and not state.stack and not state.pending_trigger_order
    assert not has_keyword(state, source, 'flying') and not has_keyword(state, source, 'lifelink')
    assert effective_power(state, source) == effective_toughness(state, source) == 1
    assert state.players[seat].life == state.players[3-seat].life == 20
    assert not cold(state).stack


@pytest.mark.parametrize('mutation', ['price-only', 'unknown-tail', 'missing-second', 'wrong-condition', 'unsupported-keyword'])
def test_detached_complete_body_parser_denies_partial_or_unknown_paired_rewards(mutation):
    card = SimpleNamespace(**deepcopy(ROWS['Archangel of Wrath']), types=['Creature'])
    text = card.oracle_text
    if mutation == 'price-only':
        card.oracle_text = text.splitlines()[0]
    elif mutation == 'unknown-tail':
        card.oracle_text += '\nDraw a card.'
    elif mutation == 'missing-second':
        card.oracle_text = '\n'.join(text.splitlines()[:-1])
    elif mutation == 'wrong-condition':
        card.oracle_text = text.replace('kicked twice', 'kicked three times')
    else:
        card.oracle_text = text.replace('Flying, lifelink', 'Flying, lifelink, ward {2}')
    assert paired_permanent_kicker(card) is None
