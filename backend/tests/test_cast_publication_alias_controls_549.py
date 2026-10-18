"""Desired real AUTO/HUMAN publication parity; PREP, not executed evidence."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
from weakref import ref

import pytest

from game_state.serializers import (
    _card_snapshot, deserialize_match_snapshot, serialize_match_snapshot,
)
from game_state.state import MatchFactory, Step, Zone, object_incarnation
from rules_engine import mana, prevention
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.mana_abilities import PaidManaStep
from rules_engine.mana_continuation import reference
from tests.library_canonical_fixtures import raw_card
from tests.test_forge_human_replacement_order import (
    act, balances, card_entry, entry, fingerprint, finish_stack, salve_entry, setup,
)


DIRECTORY = Path(__file__).parent / 'fixtures/cast_alias_publication_549'
STEEL_BYTES = (DIRECTORY / 'steel-seraph.raw.json').read_bytes()
assert hashlib.sha256(STEEL_BYTES).hexdigest() == (
    '72eab5073b2ae6ae683cfd7c6d3cb8d052b69577184ec5086518f58acc8047f7')
STEEL = json.loads(STEEL_BYTES)


def _roundtrip(state):
    before = fingerprint(state)
    payload = json.loads(json.dumps(serialize_match_snapshot(state)))
    encoded = deepcopy(payload)
    restored = deserialize_match_snapshot(payload)
    assert payload == encoded
    assert fingerprint(restored) == before == fingerprint(state)
    return restored


def _prototype_start(seat):
    # All floating resources precede both genuine paid Salves. One BF Forge
    # supplies the final W of the actual RAW Prototype cost; no paid-step reset.
    deck = [entry('Battlefield Forge', 8), salve_entry(), card_entry(STEEL, 1),
            card_entry(raw_card('Lightning Bolt'), 1)]
    state = MatchFactory.from_decks(deck, deck, seed=618)
    stock = deepcopy(state.sideboard_facts)
    starting_stock = deepcopy(state.starting_decks)
    physical = {cid: (card.owner, deepcopy(card.characteristic_record['physical']))
                for cid, card in state.cards.items()}

    def place(card, zone):
        owner = state.players[card.owner]
        getattr(owner, card.zone.value).remove(card.id)
        card.move_to_zone(zone)
        getattr(owner, zone.value).append(card.id)

    forge = next(c for c in state.cards.values()
                 if c.owner == seat and c.name == 'Battlefield Forge')
    steel = next(c for c in state.cards.values() if c.owner == seat and c.name == STEEL['name'])
    salves = [c for c in state.cards.values() if c.owner == seat and c.name == 'Healing Salve']
    bolt = next(c for c in state.cards.values() if c.owner == 3-seat and c.name == 'Lightning Bolt')
    place(forge, Zone.BATTLEFIELD)
    for card in [steel, bolt, *salves]:
        place(card, Zone.HAND)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state.players[seat].mana_pool = {'W': 3, 'C': 1}
    state.players[3-seat].mana_pool = {'R': 1}
    assert state.sideboard_facts == stock and state.starting_decks == starting_stock
    assert {cid: (card.owner, card.characteristic_record['physical'])
            for cid, card in state.cards.items()} == physical
    expected_facts = deepcopy(stock)
    for source in salves:
        binding = stock['inventory'][source.id]
        assert binding == {'owner': seat, 'stock_key': 'Healing Salve'}
        protected = expected_facts['seats'][str(binding['owner'])]['protected']
        if source.id not in protected:
            protected.append(source.id)
    frames = []
    from rules_engine.oracle_effects import inspect_target_hints
    for source in salves:
        modes = inspect_target_hints(state, state.cards[source.id], seat)['modes']
        mode = next(value for value in modes if value.startswith('Prevent'))
        state = act(state, seat, {'type': 'cast_spell', 'card_id': source.id,
                    'cost_choice': {'id': 'base'},
                    'targets': {'mode_text': mode, 'target_player': seat}})
        frames.append(state.stack[-1].id)
        state = finish_stack(state)
        assert not state.stack and not state.pending_replacement_choice
    assert state.sideboard_facts['inventory'] == stock['inventory']
    assert state.starting_decks == starting_stock
    assert {cid: (card.owner, card.characteristic_record['physical'])
            for cid, card in state.cards.items()} == physical
    postpaid_stock = deepcopy(state.sideboard_facts)
    assert postpaid_stock == expected_facts
    receipts = state.numeric_prevention_shields
    assert len(receipts) == 2 and {r.resolving_stack_id for r in receipts} == set(frames)
    assert {r.source_card_id for r in receipts} == {c.id for c in salves}
    assert all(r.remaining == 3 and r.target_player == seat and r.source_controller == seat
               and state.cards[r.source_card_id].zone == Zone.GRAVEYARD for r in receipts)
    assert {color: amount for color, amount in state.players[seat].mana_pool.items() if amount} == {
        'W': 1, 'C': 1}
    assert {color: amount for color, amount in state.players[3-seat].mana_pool.items() if amount} == {
        'R': 1}
    assert not state.cards[forge.id].tapped
    assert state.players[seat].battlefield == [forge.id]
    assert state.cards[steel.id].printed_characteristics == {}
    assert not state.cards[steel.id].card_faces
    return state, steel.id, bolt.id


def _consumption_observer(monkeypatch):
    original = prevention.consume_numeric_prevention_shield
    observed = []

    def observe(state, source_id, amount, *, target_card_id=None, target_player=None):
        result = original(state, source_id, amount,
                          target_card_id=target_card_id, target_player=target_player)
        observed.append((ref(state), (source_id, amount, result, target_card_id, target_player)))
        return result

    monkeypatch.setattr(prevention, 'consume_numeric_prevention_shield', observe)
    # checked_action returns its actual working copy. Identity filtering excludes
    # planner trials, without retaining their states or relying on reusable IDs.
    return lambda actual: [row for owner, row in observed if owner() is actual]


def _payment_observer(monkeypatch):
    original = mana._start_cast_payment
    observed = []

    def observe(state, player_id, owner, req, resources, plan, snow_spent, context,
                reserved, protected_life, details, hybrids, condition):
        steps = []
        held = set(reserved)
        if resources is not None:
            held.update((*resources.delve, *resources.improvise,
                         *(cid for cid, _ in resources.convoke)))
        for step in plan:
            if isinstance(step, PaidManaStep):
                cid, selector, amount, index, excluded, kind = (
                    step.source_id, step.color, 0, step.ability_index,
                    sorted(step.excluded_sources), 'paid')
            else:
                cid, selector, amount, _ = step
                index, excluded, kind = None, [], 'free'
            steps.append({'kind': kind, 'source': reference(state.cards[cid]),
                          'selector': selector, 'ability_index': index,
                          'excluded_sources': excluded, 'amount': amount, 'spec': None})
        captured = {'payer': player_id, 'source': deepcopy(owner['data']['source']),
                    'req': dict(req), 'steps': steps, 'context': [context[0], sorted(context[1])],
                    'reserved_card_ids': sorted(held), 'protected_life': protected_life,
                    'resource_plan': (json.loads(json.dumps(asdict(resources)))
                                      if resources is not None else None),
                    'snow_spent': dict(snow_spent)}
        observed.append((ref(state), deepcopy(captured)))
        return original(state, player_id, owner, req, resources, plan, snow_spent,
                        context, reserved, protected_life, details, hybrids, condition)

    monkeypatch.setattr(mana, '_start_cast_payment', observe)
    return lambda actual: [deepcopy(row) for owner, row in observed if owner() is actual]


def _human_payment_progress(state, initial):
    frames = state.mana_continuation['frames']
    owner, payment = frames[:2]
    assert owner['tag'] == 'owner' and owner['op'] == 'cast'
    assert payment['tag'] == 'payment'
    assert owner['payer'] == payment['payer'] == initial['payer']
    assert owner['data']['source'] == initial['source']
    contract, data = owner['data']['payment_contract'], payment['data']
    for key in ('req', 'context', 'reserved_card_ids', 'protected_life',
                'resource_plan', 'snow_spent'):
        assert contract[key] == data[key] == initial[key]
    assert contract['steps'] == data['steps']
    assert len(data['steps']) == len(initial['steps'])
    assert type(data['cursor']) is int and 0 <= data['cursor'] < len(data['steps'])
    assert data['in_flight'] is True
    assert len(data['paid_prefix']) == data['cursor']
    for index, (step, captured) in enumerate(zip(data['steps'], initial['steps'])):
        for key in ('kind', 'source', 'selector', 'excluded_sources', 'amount'):
            assert step[key] == captured[key]
        if step['kind'] == 'paid':
            assert step['ability_index'] == captured['ability_index'] and step['spec'] is None
        elif index <= data['cursor']:
            # Free steps bind their native index/spec only when execution reaches them.
            assert captured['ability_index'] is None and captured['spec'] is None
            assert type(step['ability_index']) is int
            assert type(step['spec']) is list and len(step['spec']) == 3
            assert step['spec'][0] == step['ability_index']
        else:
            assert step['ability_index'] is None and step['spec'] is None
    for index, row in enumerate(data['paid_prefix']):
        assert set(row) == {'source', 'pool_after', 'snow_after'}
        assert row['source'] == initial['steps'][index]['source']
        for key in ('pool_after', 'snow_after'):
            assert type(row[key]) is dict
            assert all(type(amount) is int and amount >= 0 for amount in row[key].values())
    return deepcopy(data)


def _paid_pair(root, seat, source, action, roundtrip, monkeypatch):
    before = fingerprint(root)
    events_for = _consumption_observer(monkeypatch)
    starts_for = _payment_observer(monkeypatch)
    automatic, human = _roundtrip(root), _roundtrip(root)
    automatic.replacement_choice_players = {3-seat}
    automatic = act(automatic, seat, action)
    assert not automatic.pending_replacement_choice and automatic.mana_continuation is None
    automatic_starts = starts_for(automatic)
    assert len(automatic_starts) == 1, 'One actual cast owner must start one native payment'
    initial = automatic_starts[0]
    assert initial['payer'] == seat and initial['source']['card_id'] == source
    automatic_events = events_for(automatic)
    assert automatic_events, 'The real automatic payment must consume genuine Salve receipts'
    assert all(row[0] in {'numeric-prevention:' + key for key in balances(root)}
               and row[2][1] > 0 and row[4] == seat for row in automatic_events)

    human = act(human, seat, action)
    assert starts_for(human) == automatic_starts
    human_events = events_for(human)
    captures = []
    assert human.pending_replacement_choice and human.mana_continuation
    while human.pending_replacement_choice:
        progress_before = _human_payment_progress(human, initial)
        assert human_events == automatic_events[:len(human_events)]
        assert len(human_events) < len(automatic_events)
        pending = human.pending_replacement_choice
        assert pending['player_id'] == seat
        selected = automatic_events[len(human_events)][0]
        assert selected in {item['source_id'] for item in pending['options']}
        assert human.cards[source].zone == Zone.HAND and not human.stack
        assert human.cards[source].characteristic_record['physical'] == (
            root.cards[source].characteristic_record['physical'])
        owner = human.mana_continuation['frames'][0]
        assert owner['tag'] == 'owner' and owner['op'] == 'cast'
        assert owner['data']['source']['card_id'] == source
        captures.append(deepcopy(owner['data']))
        if roundtrip:
            human = _roundtrip(human)
        consumed_before = len(human_events)
        human = act(human, seat, {'type': 'choose_replacement',
                                 'replacement_source_id': selected})
        human_events.extend(events_for(human))
        assert len(human_events) > consumed_before
        if human.pending_replacement_choice:
            progress_after = _human_payment_progress(human, initial)
            assert progress_after['cursor'] > progress_before['cursor']
            assert progress_after['paid_prefix'][:progress_before['cursor']] == (
                progress_before['paid_prefix'])
            assert progress_after['paid_prefix'][progress_before['cursor']]['source'] == (
                progress_before['steps'][progress_before['cursor']]['source'])
        else:
            # The real terminal frame is consumed, not replaced with an invented cursor.
            assert human.mana_continuation is None
            assert human.cards[source].zone == Zone.STACK and len(human.stack) == 1
    assert human_events == automatic_events
    assert human.mana_continuation is None
    assert fingerprint(root) == before
    return automatic, human, automatic_events, captures


def _assert_native_publication(root, result, seat, source, cost):
    original, card = root.cards[source], result.cards[source]
    assert len(result.stack) == 1 and result.stack[0].source_card_id == source
    assert result.stack[0].controller == seat and result.stack[0].payload['mana_spent'] == cost
    assert not result.pending_replacement_choice and not result.pending_mechanic_choice
    assert not result.pending_trigger_order and result.mana_continuation is None
    assert card.owner == original.owner == seat and card.controller == seat
    assert card.zone == Zone.STACK and source not in result.players[seat].hand
    assert card.zone_change_sequence == original.zone_change_sequence + 1
    assert object_incarnation(card) == object_incarnation(original)
    assert card.characteristic_record['physical'] == original.characteristic_record['physical']
    assert result.spells_cast_this_turn == {
        **root.spells_cast_this_turn, seat: root.spells_cast_this_turn.get(seat, 0) + 1}
    assert result.sideboard_facts == root.sideboard_facts and set(result.cards) == set(root.cards)


def _assert_same_publication(automatic, human):
    assert {cid: _card_snapshot(card) for cid, card in human.cards.items()} == {
        cid: _card_snapshot(card) for cid, card in automatic.cards.items()}
    assert serialize_match_snapshot(human)['stack'] == serialize_match_snapshot(automatic)['stack']
    assert balances(human) == balances(automatic)
    for seat in (1, 2):
        for field in ('mana_pool', 'life', 'prevent_damage_shield'):
            assert getattr(human.players[seat], field) == getattr(automatic.players[seat], field)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_real_bolt_automatic_and_human_keep_native_publication_and_once_damage(
        seat, roundtrip, monkeypatch):
    root, _, _, _ = setup(seat)
    source = next(c.id for c in root.cards.values() if c.owner == seat and c.name == 'Lightning Bolt')
    assert root.cards[source].zone == Zone.HAND
    original_cache = deepcopy(root.cards[source].printed_characteristics)
    original_values = deepcopy(root.cards[source].characteristic_record['values'])
    action = {'type': 'cast_spell', 'card_id': source, 'cost_choice': {'id': 'base'},
              'targets': {'target_player': 3-seat}}
    automatic, human, events, _ = _paid_pair(root, seat, source, action, roundtrip, monkeypatch)
    for result in (automatic, human):
        _assert_native_publication(root, result, seat, source, 1)
        assert result.cards[source].printed_characteristics == original_cache
        assert result.cards[source].characteristic_record['values'] == original_values
        assert result.stack[0].payload['amount'] == 3
    _assert_same_publication(automatic, human)
    for result in (automatic, human):
        if roundtrip:
            result = _roundtrip(result)
        before = fingerprint(result)
        with pytest.raises(ActionRejected):
            act(result, seat, {'type': 'choose_replacement', 'replacement_source_id': events[-1][0]})
        assert fingerprint(result) == before
        final = finish_stack(result)
        assert not final.stack and final.cards[source].zone == Zone.GRAVEYARD
        assert final.players[3-seat].life == root.players[3-seat].life - 3
        assert final.players[seat].life == root.players[seat].life
        assert balances(final) == balances(result)
        assert final.spells_cast_this_turn == result.spells_cast_this_turn
        assert final.cards[source].characteristic_record['physical'] == (
            root.cards[source].characteristic_record['physical'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_real_prototype_automatic_and_human_keep_reduced_values_then_restore(
        seat, roundtrip, monkeypatch):
    root, source, response = _prototype_start(seat)
    raw = STEEL
    match = re.search(r'Prototype ((?:\{[^}]+\})+) [\u2014-] (\d+)/(\d+)', raw['oracle_text'])
    assert match and match[1] == '{1}{W}{W}'
    expected = deepcopy(root.cards[source].characteristic_record['values'])
    expected.update(mana_cost=match[1], colors=['W'], power=int(match[2]), toughness=int(match[3]),
                    printed_power=match[2], printed_toughness=match[3])
    assert (root.cards[source].mana_cost, root.cards[source].power, root.cards[source].toughness) == (
        raw['mana_cost'], int(raw['power']), int(raw['toughness']))
    assert root.cards[source].oracle_text == raw['oracle_text']
    assert root.cards[source].type_line == raw['type_line']
    assert root.cards[source].types == ['Artifact', 'Creature']
    assert root.cards[source].colors == raw['colors'] == []
    assert 'Flying' in raw['keywords'] and 'flying' in root.cards[source].keywords
    move = next(m for m in RulesEngine().legal_moves(root, seat)
                if m['type'] == 'cast_spell' and m.get('card_id') == source)
    option = next(o for o in move['cost_options'] if o['id'] == 'prototype')
    assert option['mana_cost'] == match[1]
    action = {'type': 'cast_spell', 'card_id': source, 'cost_choice': {'id': option['id']}}
    automatic, human, _, captures = _paid_pair(root, seat, source, action, roundtrip, monkeypatch)
    for capture in captures:
        printed, reduced = capture['printed_face_card'], capture['face_card']
        assert (printed['mana_cost'], printed['power'], printed['toughness'], printed['colors']) == (
            raw['mana_cost'], int(raw['power']), int(raw['toughness']), raw['colors'])
        assert printed['oracle_text'] == reduced['oracle_text'] == raw['oracle_text']
        assert (reduced['mana_cost'], reduced['power'], reduced['toughness'], reduced['colors']) == (
            match[1], int(match[2]), int(match[3]), ['W'])
    for result in (automatic, human):
        _assert_native_publication(root, result, seat, source, 3)
        assert result.cards[source].characteristic_record['values'] == expected
        assert (result.cards[source].mana_cost, result.cards[source].power,
                result.cards[source].toughness, result.cards[source].colors) == (
                    match[1], int(match[2]), int(match[3]), ['W'])
    _assert_same_publication(automatic, human)
    expected_facts = deepcopy(root.sideboard_facts)
    for cid in (source, response):
        binding = expected_facts['inventory'][cid]
        protected = expected_facts['seats'][str(binding['owner'])]['protected']
        if cid not in protected:
            protected.append(cid)
    observer = expected_facts['seats'][str(3-seat)]
    assert source not in observer['observed_creatures']
    observer['observed_creatures'].append(source)
    observer['observed_creature_sources'][source] = {
        'cid': source, 'owner': seat, 'controller': seat,
        'zone_change_sequence': root.cards[source].zone_change_sequence + 2,
        'effective_types': raw['type_line'].split('\u2014', 1)[0].split(),
    }
    for result in (automatic, human):
        if roundtrip:
            result = _roundtrip(result)
        entered = finish_stack(result)
        assert not entered.stack and entered.cards[source].zone == Zone.BATTLEFIELD
        assert entered.cards[source].characteristic_record['values'] == expected
        assert entered.cards[source].zone_change_sequence == root.cards[source].zone_change_sequence + 2
        # A genuine opponent-paid Bolt kills the genuine reduced 3/3. Its R
        # was present before the first Salve, not credited after this entry.
        if entered.priority_player != 3-seat:
            entered = act(entered, entered.priority_player, {'type': 'pass_priority'})
        assert entered.priority_player == 3-seat
        dying = act(entered, 3-seat, {'type': 'cast_spell', 'card_id': response,
                    'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': source}})
        assert dying.stack[-1].payload['mana_spent'] == 1
        final = finish_stack(dying)
        card = final.cards[source]
        assert not final.stack and card.zone == Zone.GRAVEYARD
        assert card.zone_change_sequence == root.cards[source].zone_change_sequence + 3
        assert card.printed_characteristics == {}
        assert card.characteristic_record == root.cards[source].characteristic_record
        assert (card.mana_cost, card.power, card.toughness, card.colors) == (
            raw['mana_cost'], int(raw['power']), int(raw['toughness']), raw['colors'])
        assert final.sideboard_facts == expected_facts
        assert final.sideboard_facts['inventory'] == root.sideboard_facts['inventory']
        assert final.starting_decks == root.starting_decks
