"""Complete canonical Domain spell and Flash episodes; public retained positions."""
import json
import os

import pytest

import inventory as inv
import domain_paid_support as g
from test_domain_paid_continuations import cold, privacy_probe, remove_binding
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.domain import basic_land_type_count
from rules_engine.engine import RulesEngine
from rules_engine.mana import mana_value

BASICS = ['Forest', 'Plains', 'Island', 'Swamp', 'Mountain']
RUN = os.environ.get('GATE2_DOMAIN_SPELL_RUN', 'domain-spell-flash')


@pytest.fixture(scope='module')
def facts():
    seed, selected, proof = inv.load_inputs()
    raw = {name: selected[row['scryfall_id']] for name, row in seed.items()}
    names = BASICS + ['Herd Migration', 'Leyline Binding', 'Boseiju, Who Endures', 'Torrential Gearhulk']
    for name in names:
        assert raw[name]['object'] == 'card' and raw[name]['name'] == name
        assert raw[name]['oracle_text'] == seed[name]['oracle_text']
    with (inv.ROOT.parent / 'evidence' / (RUN + '-facts.json')).open('x') as stream:
        json.dump({'source': proof, 'cards': {name: raw[name] for name in names}}, stream, indent=2)
    return raw


def replay_cast(state, seat, source):
    before = serialize_match_snapshot(state)
    action = {'type': 'cast_spell', 'card_id': source}
    paid = checked_action(state, RulesEngine(), seat, action)
    replay = checked_action(deserialize_match_snapshot(before), RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    assert serialize_match_snapshot(paid) == serialize_match_snapshot(replay)
    return paid, replay


def receipt(case, state, **facts):
    with (inv.ROOT.parent / 'evidence' / (RUN + '-' + case + '.json')).open('x') as stream:
        json.dump({'case': case, 'observed': facts,
                   'snapshot': serialize_match_snapshot(state)}, stream, indent=2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('types', [0, 1, 5])
def test_full_raw_herd_spell_paid_domain_count_color_owner_and_replay(facts, seat, types, tmp_path):
    state = g.position(facts, seat)
    source = g.add(state, facts, 'Herd Migration', seat, Zone.HAND)
    for name in BASICS[:types]:
        g.add(state, facts, name, seat)
    for name in BASICS:
        g.add(state, facts, name, 3-seat)
    assert basic_land_type_count(state, seat) == types
    assert basic_land_type_count(state, 3-seat) == 5
    assert state.cards[source].oracle_text == facts['Herd Migration']['oracle_text']
    assert state.cards[source].mana_cost == '{6}{G}'
    state.players[seat].mana_pool = {'C': 6, 'G': 1}
    paid, replay = replay_cast(state, seat, source)
    assert sum(paid.players[seat].mana_pool.values()) == 0
    assert len(paid.stack) == 1 and paid.stack[-1].effect_key == 'create_token'
    paid = cold(paid, tmp_path, 'paid-herd-spell')
    replay = cold(replay, tmp_path, 'replayed-herd-spell')
    g.resolve(paid)
    g.resolve(replay)
    assert serialize_match_snapshot(paid) == serialize_match_snapshot(replay)
    tokens = [c for c in paid.cards.values() if c.is_token]
    assert len(tokens) == types
    for token in tokens:
        assert token.name == 'Beast' and token.colors == ['G']
        assert token.owner == token.controller == seat and token.zone == Zone.BATTLEFIELD
        assert token.id in paid.players[seat].battlefield
        assert (effective_power(paid, token.id), effective_toughness(paid, token.id)) == (3, 3)
    assert paid.cards[source].zone == Zone.GRAVEYARD and not paid.stack
    paid = cold(paid, tmp_path, 'complete-herd-spell')
    receipt(f'herd-{seat}-{types}', paid, paid_C=6, paid_G=1, domain=types,
            opponent_domain=5, tokens=types, exact_replay=True, complete_printed_body=True)


@pytest.mark.parametrize('seat', [1, 2])
def test_full_raw_binding_flash_offturn_paid_discount_linked_return(facts, seat, tmp_path):
    state = g.position(facts, seat)
    other = 3-seat
    source = g.add(state, facts, 'Leyline Binding', seat, Zone.HAND)
    no_flash = g.add(state, facts, 'Herd Migration', seat, Zone.HAND)
    target = g.add(state, facts, 'Torrential Gearhulk', other)
    for name in BASICS:
        g.add(state, facts, name, seat)
    # Lawful public retained end-step position, not a claim of playing five lands now.
    state.active_player = state.priority_player = other
    state.step = Step.END_STEP
    state = g.act(state, other, 'pass_priority')
    assert state.priority_player == seat and state.active_player == other
    assert state.step == Step.END_STEP and basic_land_type_count(state, seat) == 5
    state.players[seat].mana_pool = {'C': 6, 'G': 1}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        g.cast(state, seat, no_flash)
    assert serialize_match_snapshot(state) == before
    assert state.cards[source].oracle_text == facts['Leyline Binding']['oracle_text']
    assert state.cards[source].mana_cost == '{5}{W}'
    state.players[seat].mana_pool = {'W': 1}
    paid, replay = replay_cast(state, seat, source)
    assert sum(paid.players[seat].mana_pool.values()) == 0
    assert paid.active_player == other and paid.step == Step.END_STEP
    assert mana_value(paid.cards[source].mana_cost) == 6
    paid = cold(paid, tmp_path, 'offturn-flash-paid-stack')
    g.resolve(paid)
    g.resolve(replay)
    assert serialize_match_snapshot(paid) == serialize_match_snapshot(replay)
    assert paid.pending_trigger_order['phase'] == 'targets'
    privacy_probe(paid, seat)
    sid = paid.pending_trigger_order['current_stack_id']
    paid = g.act(paid, seat, 'choose_trigger_target', stack_id=sid, target_card_id=target)
    assert paid.stack[-1].effect_key == 'exile_until_source_leaves'
    paid = cold(paid, tmp_path, 'offturn-public-target')
    g.resolve(paid)
    assert paid.cards[target].zone == Zone.EXILE and paid.linked_exiles
    assert paid.cards[source].zone == Zone.BATTLEFIELD
    paid = remove_binding(paid, facts, seat, source)
    assert paid.cards[target].zone == Zone.BATTLEFIELD and not paid.linked_exiles
    paid = cold(paid, tmp_path, 'offturn-flash-returned')
    receipt(f'flash-{seat}', paid, active_player=other, step='end_step', paid_W=1,
            generic_discount=5, printed_mana_value=6, actual_nonflash_rejected=True,
            target_exiled_then_returned=True, paid_boseiju_C=1, paid_boseiju_G=1,
            exact_cast_replay=True, complete_printed_body=True)
