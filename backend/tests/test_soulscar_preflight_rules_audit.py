"""Canonical rules fixtures, not natural games; no SQL or sockets required."""
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from effects import handlers
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.combat import _mark_creature_damage
from rules_engine.counter_replacements import counter_modifier
from rules_engine.coverage import deck_pair_coverage, known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.replacement import replacement_options


DIRECTORY = Path(__file__).parent / 'fixtures/soulscar_consumer_audit'
CARDS = {row['name']: row for row in json.loads((DIRECTORY / 'cards.json').read_text())}
for filename in ['boon-of-safety.json', 'vampire-nighthawk.json', 'stigma-lasher.json']:
    row = json.loads((DIRECTORY / filename).read_text())
    CARDS[row['name']] = row


def position(seat):
    deck = [{**CARDS['Island'], 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=7107)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {'R': 5, 'U': 5, 'W': 5, 'C': 5}
    return state


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    raw = CARDS[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=7107)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    card.summoning_sick = False
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def restore(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def cast(state, name, seat, target):
    cid = add(state, name, seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': cid, 'targets': {'target_card_id': target}})
    assert serialize_match_snapshot(state) == before
    assert result.cards[cid].zone == Zone.STACK
    assert result.players[seat].mana_pool != state.players[seat].mana_pool
    return result, cid


def finish(state):
    for _ in range(32):
        if state.pending_mechanic_choice:
            pending = state.pending_mechanic_choice
            assert pending['kind'] == 'scry'
            state = checked_action(state, RulesEngine(), pending['player_id'], {
                'type': 'choose_mechanic', 'kind': 'scry', 'card_ids': []})
        elif state.pending_replacement_choice:
            return state
        elif state.stack:
            state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
        else:
            return state
    raise AssertionError('Bounded fixture continuation did not finish')


def receipt(label, state, target, **data):
    path = os.environ.get('MTG_SOULSCAR_RECEIPTS')
    if path:
        row = {'case': label, 'target': target, 'zone': state.cards[target].zone.value,
               'counters': state.cards[target].counters,
               'life': {pid: p.life for pid, p in state.players.items()},
               'pending_replacement': state.pending_replacement_choice, **data}
        with open(path, 'a') as stream:
            stream.write(json.dumps(row, sort_keys=True) + '\n')


def test_preflight_is_generic_counter_parser_classification_not_missing_damage_route():
    row = CARDS['Soul-Scar Mage']
    line = row['oracle_text'].splitlines()[1]
    assert counter_modifier(line) is None
    assert known_unsupported_mechanics(row['oracle_text'], card_name=row['name']) == [
        'counter replacement route fidelity', 'unsupported counter replacement clause']
    report = deck_pair_coverage([{**row, 'card_name': row['name']}], [])
    assert report == {'status': 'exploratory', 'known_unsupported_cards': [
        {'deck': 'A', 'card_name': row['name'], 'mechanics': [
            'counter replacement route fidelity', 'unsupported counter replacement clause']}]}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,amount', [('Lightning Bolt', 3), ('Unholy Heat', 2)])
@pytest.mark.parametrize('reload', [False, True])
@pytest.mark.parametrize('friendly', [False, True])
def test_paid_actual_spells_replace_only_opposing_creature_damage(seat, name, amount, reload, friendly):
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Torrential Gearhulk', seat if friendly else 3-seat)
    state, spell = cast(state, name, seat, target)
    if reload:
        state = restore(state)
    state = finish(state)
    receipt(name, state, target, seat=seat, friendly=friendly, restored=reload)
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.cards[target].counters.get('-1/-1', 0) == (0 if friendly else amount)
    assert state.cards[target].counters.get('__damage_marked', 0) == (amount if friendly else 0)
    assert state.cards[target].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Lightning Bolt', 'Unholy Heat'])
def test_replaced_actual_paid_damage_causes_zero_toughness_sba(seat, name):
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Grizzly Bears', 3-seat)
    state, _ = cast(state, name, seat, target)
    state = finish(restore(state))
    receipt('sba-death', state, target, seat=seat, spell=name)
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert target in state.players[3-seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reload', [False, True])
def test_printed_tap_damage_ability_uses_its_actual_source_controller(seat, reload):
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    pyro = add(state, 'Prodigal Pyromancer', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': pyro, 'ability_index': 0, 'targets': {'target_card_id': target}})
    assert serialize_match_snapshot(state) == before
    assert result.cards[pyro].tapped
    state = finish(restore(result) if reload else result)
    receipt('printed-activated-damage', state, target, seat=seat)
    assert state.cards[target].counters.get('-1/-1') == 1
    assert not state.cards[target].counters.get('__damage_marked')


@pytest.mark.parametrize('seat', [1, 2])
def test_opposing_replacement_source_does_not_rewrite_casters_damage(seat):
    state = position(seat)
    add(state, 'Soul-Scar Mage', 3-seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    state, _ = cast(state, 'Lightning Bolt', seat, target)
    state = finish(state)
    assert state.cards[target].counters.get('-1/-1', 0) == 0
    assert state.cards[target].counters.get('__damage_marked') == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_humility_suppresses_replacement_without_changing_oracle(seat):
    state = position(seat)
    mage = add(state, 'Soul-Scar Mage', seat)
    add(state, 'Humility', 3-seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    state, _ = cast(state, 'Lightning Bolt', seat, target)
    state = finish(restore(state))
    assert state.cards[mage].oracle_text == CARDS['Soul-Scar Mage']['oracle_text']
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert not any('replaces 3 noncombat damage' in line for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mage_present', [False, True])
def test_noncombat_replacement_is_not_wither_damage_or_lifelink(seat, mage_present, monkeypatch):
    state = position(seat)
    if mage_present:
        add(state, 'Soul-Scar Mage', seat)
    nighthawk = add(state, 'Vampire Nighthawk', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    events = []
    original = handlers.emit_event
    def capture(state, event, payload):
        events.append(event)
        return original(state, event, payload)
    monkeypatch.setattr(handlers, 'emit_event', capture)
    # Explicit core noncombat packet from a genuine canonical source, not a
    # claimed printed Nighthawk activation or injected StackItem.
    dealt = handlers.deal_damage(state, 3-seat, {
        '__source_card_id': nighthawk, 'target_card_id': target, 'amount': 2})
    receipt('noncombat-lifelink-core', state, target, events=events, dealt=dealt)
    assert state.players[seat].life == (20 if mage_present else 22)
    assert ('damage_dealt' in events) == (not mage_present)
    assert dealt == (0 if mage_present else 2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source,minus', [('Prodigal Pyromancer', 0), ('Stigma Lasher', 1), ('Glistener Elf', 1)])
def test_combat_core_is_not_replaced_and_wither_infect_still_count_as_damage(seat, source, minus):
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    attacker = add(state, source, seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    dealt = _mark_creature_damage(state, target, 1, source_id=attacker)
    assert dealt == 1
    assert state.cards[target].counters.get('-1/-1', 0) == minus
    assert state.cards[target].counters.get('__damage_marked', 0) == 1-minus


@pytest.mark.parametrize('seat', [1, 2])
def test_damage_doubling_and_soulscar_are_both_offered_to_affected_player(seat):
    state = position(seat)
    mage = add(state, 'Soul-Scar Mage', seat)
    furnace = add(state, 'Furnace of Rath', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    bolt = add(state, 'Lightning Bolt', seat, Zone.HAND)
    options = replacement_options(state, 'damage_to_permanent', target_card_id=target, source_card_id=bolt)
    receipt('replacement-options', state, target, options=options)
    assert {mage, furnace} <= {option['source_id'] for option in options}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reload', [False, True])
def test_genuine_paid_shield_spell_then_bolt_requires_affected_human_order(seat, reload):
    state = position(3-seat)
    mage = add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    state, _ = cast(state, 'Boon of Safety', 3-seat, target)
    state = finish(state)
    assert state.cards[target].counters.get('shield') == 1
    state.active_player = state.priority_player = seat
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    state, _ = cast(state, 'Lightning Bolt', seat, target)
    if reload:
        state = restore(state)
    state = finish(state)
    receipt('paid-shield-order', state, target, seat=seat, restored=reload)
    assert state.pending_replacement_choice is not None, 'Affected human must choose shield versus replacing damage with counters'
    assert state.pending_replacement_choice['player_id'] == 3-seat
    ids = {option['source_id'] for option in state.pending_replacement_choice['options']}
    assert mage in ids and f'shield-counter:{target}' in ids
