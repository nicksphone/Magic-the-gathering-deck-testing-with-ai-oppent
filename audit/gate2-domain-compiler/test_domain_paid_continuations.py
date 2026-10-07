"""Paid canonical continuations; mutated strings occur only in compiler negatives."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

import inventory as inv
import domain_paid_support as g
from ai.information import decision_view, is_unknown
from game_state.state import Zone, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.events import _trigger_from_oracle
from rules_engine.oracle_effects import compile_search_life_instruction
from rules_engine.stack_engine import resolve_top_of_stack

RUN = os.environ.get('GATE2_DOMAIN_RUN', 'domain-paid')

@pytest.fixture(scope='module')
def facts():
    seed, selected, proof = inv.load_inputs()
    raw = {name: selected[row['scryfall_id']] for name, row in seed.items()}
    fixture = inv.ROOT / 'backend/tests/fixtures/cloudshift_compound_audit'
    for line in (fixture / 'SHA256SUMS').read_text().splitlines():
        digest, filename = line.split()
        assert inv.sha(fixture / Path(filename).name) == digest
    extra = json.loads((fixture / 'flicker-of-fate.json').read_bytes())
    assert extra['object'] == 'card' and extra['name'] == 'Flicker of Fate' and extra['oracle_id']
    raw[extra['name']] = extra
    with (inv.ROOT.parent / 'evidence' / (RUN + '-facts.json')).open('x') as stream:
        json.dump({'source': proof, 'auxiliary_fixture': str(fixture),
                   'auxiliary_sha256': inv.sha(fixture / 'flicker-of-fate.json'),
                   'canonical_cards': {name: raw[name] for name in
                       ['Herd Migration', 'Leyline Binding', 'Boseiju, Who Endures', 'Flicker of Fate']}}, stream, indent=2)
    return raw


def cold(state, tmp_path, name):
    packet = serialize_match_snapshot(state)
    path = tmp_path / (name + '.json')
    path.write_text(json.dumps(packet))
    result = deserialize_match_snapshot(json.loads(path.read_bytes()))
    assert serialize_match_snapshot(result) == packet
    return result


def hidden(state, viewer):
    other = state.players[3-viewer]
    ids = other.hand + other.library
    return {'hand': list(other.hand), 'library': list(other.library),
            'cards': {cid: deepcopy(vars(state.cards[cid])) for cid in ids}}


def privacy_probe(state, viewer):
    before = serialize_match_snapshot(state)
    private = hidden(state, viewer)
    view, _ = decision_view(state, viewer, [])
    assert all(is_unknown(view.cards[cid]) for cid in private['hand'] + private['library'])
    assert serialize_match_snapshot(state) == before
    assert hidden(state, viewer) == private


def observed(case, state, **outcome):
    with (inv.ROOT.parent / 'evidence' / (RUN + '-' + case + '.json')).open('x') as stream:
        json.dump({'case': case, 'outcome': outcome, 'snapshot': serialize_match_snapshot(state)}, stream, indent=2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('find', [False, True])
def test_paid_search_private_choice_cold_restart_and_exactly_once_life(facts, seat, find, tmp_path):
    state = g.position(facts, seat)
    source = g.add(state, facts, 'Herd Migration', seat, Zone.HAND)
    basic = g.add(state, facts, 'Forest', seat, Zone.LIBRARY)
    nonbasic = g.add(state, facts, 'Hallowed Fountain', seat, Zone.LIBRARY)
    g.add(state, facts, 'Lightning Bolt', 3-seat, Zone.HAND)
    g.add(state, facts, 'Sunfall', 3-seat, Zone.LIBRARY)
    private = hidden(state, seat)
    state.players[seat].mana_pool = {'C': 1, 'G': 1}
    state = g.act(state, seat, 'activate_ability', card_id=source, ability_index=0)
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = cold(state, tmp_path, 'paid-stack')
    assert not resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'search_library' and nonbasic not in pending['options']
    assert pending['continuation_effects'] == [{'effect_key': 'gain_life', 'payload': {
        'amount': 3, '__source_card_id': source, '__resolving_item': pending['resolving_item']}}]
    assert state.players[seat].life == 20
    state = cold(state, tmp_path, 'pending-search')
    privacy_probe(state, seat)
    privacy_probe(state, 3-seat)
    before = serialize_match_snapshot(state)
    for actor, cards in [(3-seat, [basic]), (seat, [nonbasic])]:
        with pytest.raises(ActionRejected):
            g.act(state, actor, 'choose_mechanic', card_ids=cards)
        assert serialize_match_snapshot(state) == before
    state = g.act(state, seat, 'choose_mechanic', card_ids=[basic] if find else [])
    assert state.players[seat].life == 23
    assert state.cards[basic].zone == (Zone.HAND if find else Zone.LIBRARY)
    assert not state.stack and state.pending_mechanic_choice is None
    assert hidden(state, seat) == private
    state = cold(state, tmp_path, 'completed-search')
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        g.act(state, seat, 'choose_mechanic', card_ids=[basic] if find else [])
    assert serialize_match_snapshot(state) == before and state.players[seat].life == 23
    observed(f'herd-{seat}-{find}', state, paid_C=1, paid_G=1, life_gain=3, found=find)


@pytest.mark.parametrize('tail', [' Unknown instruction.', ' Draw a card.', '\nDestroy target creature.',
                                ' If you control a creature, gain 1 life.', ' and draw a card.'])
def test_search_unknown_tail_compiles_no_partial_search_or_life(facts, tail):
    # Diagnostic-only mutation, never placed on or executed as a gameplay card.
    instruction = facts['Herd Migration']['oracle_text'].split(': ', 1)[1] + tail
    result = compile_search_life_instruction(instruction)
    assert result[0] == 'noop' and result[1]['__unsupported_instruction'] == instruction


@pytest.mark.parametrize('number,count', [('3', 3), ('three', 3), ('ten', 10), ('12', 12), ('0', 0)])
def test_closed_search_life_reuses_existing_count_parser(facts, number, count):
    # Pure instruction grammar unit, not fictional or rewritten gameplay Oracle.
    instruction = facts['Herd Migration']['oracle_text'].split(': ', 1)[1].replace('3 life', number + ' life')
    result = compile_search_life_instruction(instruction)
    assert result[0] == 'effect_sequence'
    assert [item['effect_key'] for item in result[1]['effects']] == ['search_library', 'gain_life']
    assert result[1]['effects'][1]['payload'] == {'amount': count}


def binding_targets(facts, seat, foreign=False):
    state = g.position(facts, seat)
    source = g.add(state, facts, 'Leyline Binding', seat, Zone.HAND)
    target = g.add(state, facts, 'Torrential Gearhulk', 3-seat)
    if foreign:
        # Lawful stolen-object starting board, not a claimed control-change episode.
        state.cards[target].owner = seat
    second = g.add(state, facts, 'Torrential Gearhulk', 3-seat)
    own = g.add(state, facts, 'Torrential Gearhulk', seat)
    land = g.add(state, facts, 'Mountain', 3-seat)
    g.add(state, facts, 'Hallowed Fountain', seat)
    g.add(state, facts, 'Mountain', seat)
    yavi = g.add(state, facts, 'Yavimaya, Cradle of Growth', seat, Zone.HAND)
    g.add(state, facts, 'Lightning Bolt', 3-seat, Zone.HAND)
    g.add(state, facts, 'Sunfall', 3-seat, Zone.LIBRARY)
    state = g.act(state, seat, 'play_land', card_id=yavi)
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = g.cast(state, seat, source)
    assert sum(state.players[seat].mana_pool.values()) == 0
    g.resolve(state)
    assert state.pending_trigger_order['phase'] == 'targets'
    sid = state.pending_trigger_order['current_stack_id']
    for actor, invalid in [(seat, own), (seat, land), (3-seat, target)]:
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            g.act(state, actor, 'choose_trigger_target', stack_id=sid, target_card_id=invalid)
        assert serialize_match_snapshot(state) == before
    privacy_probe(state, seat)
    state = g.act(state, seat, 'choose_trigger_target', stack_id=sid, target_card_id=target)
    assert state.stack[-1].effect_key == 'exile_until_source_leaves'
    return state, source, target, second


def remove_binding(state, facts, seat, source):
    channel = g.add(state, facts, 'Boseiju, Who Endures', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'C': 1, 'G': 1}
    state = g.act(g.respond(state, 3-seat), 3-seat, 'activate_ability', card_id=channel,
                  ability_index=1, targets={'target_card_id': source})
    assert sum(state.players[3-seat].mana_pool.values()) == 0
    resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'optional_search'
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        g.act(state, 3-seat, 'choose_mechanic', card_ids=['decline'])
    assert serialize_match_snapshot(state) == before
    state = g.act(state, seat, 'choose_mechanic', card_ids=['decline'])
    assert state.cards[source].zone == Zone.GRAVEYARD
    return state


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_source_departure_before_etb_resolution_does_not_exile(facts, seat, tmp_path):
    state, source, target, _ = binding_targets(facts, seat)
    state = remove_binding(state, facts, seat, source)
    state = cold(state, tmp_path, 'departed-source-pending-trigger')
    g.resolve(state)
    assert state.cards[target].zone == Zone.BATTLEFIELD and not state.linked_exiles
    observed(f'leyline-source-before-{seat}', state, paid_cast=2, paid_removal=2, exiled=False)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_paid_duration_return_cold_restart_and_foreign_owner(facts, seat, foreign, tmp_path):
    state, source, target, _ = binding_targets(facts, seat, foreign)
    private = hidden(state, seat)
    state = cold(state, tmp_path, 'chosen-public-trigger')
    g.resolve(state)
    assert state.cards[target].zone == Zone.EXILE
    assert state.linked_exiles[0]['source_timestamp'] == object_incarnation(state.cards[source])
    state = cold(state, tmp_path, 'linked-exile')
    state = remove_binding(state, facts, seat, source)
    assert state.cards[target].zone == Zone.BATTLEFIELD and not state.linked_exiles
    owner = seat if foreign else 3-seat
    assert state.cards[target].owner == state.cards[target].controller == owner
    assert target in state.players[owner].battlefield
    assert hidden(state, seat) == private
    observed(f'leyline-return-{seat}-{foreign}', state, paid_cast=2, paid_removal=2, returned_to_owner=owner)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_actual_blink_new_incarnation_does_not_reactivate_old_duration(facts, seat, tmp_path):
    state, source, old_target, new_target = binding_targets(facts, seat)
    old_timestamp = state.stack[-1].payload['source_timestamp']
    blink = g.add(state, facts, 'Flicker of Fate', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = g.cast(g.respond(state, seat), seat, blink, target_card_id=source)
    assert sum(state.players[seat].mana_pool.values()) == 0
    g.resolve(state)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert object_incarnation(state.cards[source]) != old_timestamp
    sid = state.pending_trigger_order['current_stack_id']
    state = g.act(state, seat, 'choose_trigger_target', stack_id=sid, target_card_id=new_target)
    state = cold(state, tmp_path, 'new-source-old-trigger-pending')
    g.resolve(state)
    assert state.cards[new_target].zone == Zone.EXILE
    g.resolve(state)
    assert state.cards[old_target].zone == Zone.BATTLEFIELD
    assert len(state.linked_exiles) == 1
    assert state.linked_exiles[0]['source_timestamp'] == object_incarnation(state.cards[source])
    state = remove_binding(state, facts, seat, source)
    assert state.cards[new_target].zone == Zone.BATTLEFIELD and not state.linked_exiles
    observed(f'leyline-blink-{seat}', state, paid_blink=2, old_trigger_exiled=False, new_link_returned=True)


@pytest.mark.parametrize('tail', [' Draw a card.', ' Unknown instruction.', '\nDraw a card.',
                                '\nWhen this enchantment enters, draw a card.'])
@pytest.mark.parametrize('seat', [1, 2])
def test_linked_entry_unknown_complete_tail_never_plain_exiles(facts, seat, tail):
    # Mutated diagnostic argument only, never modified/executed canonical card data.
    state = g.position(facts, seat)
    source = g.add(state, facts, 'Leyline Binding', seat)
    clause = facts['Leyline Binding']['oracle_text'].splitlines()[-1] + tail
    before = serialize_match_snapshot(state)
    result = _trigger_from_oracle(state, source, seat, clause, 'diagnostic', 'enters_battlefield',
                                  {'card_id': source, 'controller': seat})
    assert result['effect_key'] == 'noop' and result['payload']['__unsupported_trigger_instruction']
    assert serialize_match_snapshot(state) == before
