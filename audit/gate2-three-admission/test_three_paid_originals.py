"""Independent complete canonical paid episodes; parser mutations are negatives only."""
from copy import deepcopy
import json
import os

import pytest

import inventory as inv
from card_data.hydration import hydrate_deck_cards
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.domain import basic_land_type_count
from rules_engine.mana import mana_value
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.engine import RulesEngine

FAMILIES = ['Searing Blaze', 'Sunfall', 'Chrome Host Seedshark']
PHASE = os.environ.get('ADMISSION_PHASE', 'before')
OUT = inv.ROOT.parent / 'evidence'

@pytest.fixture(scope='module')
def facts():
    seed, selected, proof = inv.load_inputs()
    raws = {name: selected[card['scryfall_id']] for name, card in seed.items()}
    for name in FAMILIES:
        assert raws[name]['oracle_text'] == seed[name]['oracle_text']
    with (OUT / ('facts-' + PHASE + '.json')).open('x') as stream:
        json.dump({'source': proof, 'cards': {name: raws[name] for name in FAMILIES}}, stream, indent=2)
    return raws


def position(facts, seat):
    land = facts['Forest']
    deck = [{**land, 'card_name': land['name'], 'quantity': 30}]
    state = MatchFactory.from_decks(deck, deck, seed=2331)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    for player in state.players.values():
        for cid in list(player.hand):
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()
    return state


def add(state, facts, name, seat, zone=Zone.BATTLEFIELD):
    raw = facts[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 1}], [], seed=2331)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def act(state, seat, kind, **fields):
    return checked_action(state, RulesEngine(), seat, {'type': kind, **fields})


def cast(state, seat, source, **targets):
    return act(state, seat, 'cast_spell', card_id=source, targets=targets)


def restore(state):
    packet = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(packet)
    assert serialize_match_snapshot(result) == packet
    return result


def resolve(state):
    assert resolve_top_of_stack(state)
    return state


def respond(state, seat):
    if state.priority_player != seat:
        state = act(state, state.priority_player, 'pass_priority')
    assert state.priority_player == seat
    return state


def receipt(label, facts, names, state, **observed):
    packet = {'case': label, 'phase': PHASE,
        'raw_sha256': {name: inv.canonical_hash(facts[name]) for name in names},
        'coverage_sha256': inv.sha(inv.ROOT / 'backend/rules_engine/coverage.py'),
        'state_sha256': inv.canonical_hash(serialize_match_snapshot(state)), 'observed': observed}
    with (OUT / (PHASE + '-' + label + '.json')).open('x') as stream:
        json.dump(packet, stream, indent=2, sort_keys=True)


@pytest.mark.parametrize('name', ['Searing Blaze', 'Sunfall', 'Chrome Host Seedshark'])
@pytest.mark.parametrize('seat', [1, 2])
def test_insufficient_real_payment_rejected_atomically(name, seat, facts):
    state = position(facts, seat)
    source = add(state, facts, name, seat, Zone.HAND)
    target = add(state, facts, 'Torrential Gearhulk', 3-seat)
    state.players[seat].mana_pool = {}
    before = serialize_match_snapshot(state)
    targets = {'target_player': 3-seat, 'target_card_id': target} if name == 'Searing Blaze' else {}
    with pytest.raises(ActionRejected):
        cast(state, seat, source, **targets)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('primary', ['player', 'planeswalker'])
@pytest.mark.parametrize('entry', ['none', 'before', 'caster-response', 'opponent-response'])
def test_paid_blaze_complete_targets_and_actual_land_history(facts, seat, primary, entry):
    state = position(facts, seat)
    source = add(state, facts, 'Searing Blaze', seat, Zone.HAND)
    target = add(state, facts, 'Torrential Gearhulk', 3-seat)
    walker = add(state, facts, 'Ugin, the Spirit Dragon', 3-seat) if primary == 'planeswalker' else None
    state.players[seat].mana_pool = {'R': 2}
    if entry == 'before':
        land = add(state, facts, 'Forest', seat, Zone.HAND)
        state = act(state, seat, 'play_land', card_id=land)
        assert state.land_entries_this_turn.get(seat) == 1
    selected = {'target_card_ids': [walker, target]} if walker else {'target_player': 3-seat, 'target_card_id': target}
    state = cast(state, seat, source, **selected)
    assert state.players[seat].mana_pool.get('R', 0) == 0
    assert state.stack[-1].effect_key == 'linked_landfall_damage'
    if entry.endswith('response'):
        actor = seat if entry == 'caster-response' else 3-seat
        spiral = add(state, facts, 'Growth Spiral', actor, Zone.HAND)
        land = add(state, facts, 'Forest', actor, Zone.HAND)
        state.players[actor].mana_pool.update(G=1, U=1)
        state = cast(respond(state, actor), actor, spiral)
        assert state.players[actor].mana_pool.get('G', 0) == state.players[actor].mana_pool.get('U', 0) == 0
        assert not resolve_top_of_stack(state)
        assert state.pending_mechanic_choice['kind'] == 'land_from_hand'
        state = act(restore(state), actor, 'choose_mechanic', card_ids=[land])
        assert state.cards[land].zone == Zone.BATTLEFIELD
        assert state.land_entries_this_turn.get(actor) == 1
    state = restore(state)
    amount = 3 if entry in {'before', 'caster-response'} else 1
    old = state.cards[walker].loyalty if walker else state.players[3-seat].life
    resolve(state)
    assert (state.cards[walker].loyalty if walker else state.players[3-seat].life) == old - amount
    assert state.cards[target].counters.get('__damage_marked', 0) == amount
    assert state.cards[source].zone == Zone.GRAVEYARD
    receipt(f'blaze-{seat}-{primary}-{entry}', facts, ['Searing Blaze'], state, damage=amount, paid_R=2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['wrong-controller', 'noncreature', 'missing-secondary'])
def test_blaze_target_rejection_preserves_root_and_cost(facts, seat, fault):
    state = position(facts, seat)
    source = add(state, facts, 'Searing Blaze', seat, Zone.HAND)
    target = add(state, facts, 'Torrential Gearhulk', 3-seat)
    land = add(state, facts, 'Forest', 3-seat)
    state.players[seat].mana_pool = {'R': 2}
    selected = {'target_player': seat if fault == 'wrong-controller' else 3-seat,
                'target_card_id': land if fault == 'noncreature' else target}
    if fault == 'missing-secondary':
        selected.pop('target_card_id')
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, source, **selected)
    assert serialize_match_snapshot(state) == before


def transform_token(state, seat, token, expected):
    state = respond(state, seat)
    state.players[seat].mana_pool = {'C': 2}
    state = act(state, seat, 'activate_ability', card_id=token, ability_index=0)
    assert state.players[seat].mana_pool.get('C', 0) == 0
    resolve(state)
    if expected:
        assert 'Creature' in state.cards[token].types
        assert (effective_power(state, token), effective_toughness(state, token)) == (expected, expected)
    else:
        assert state.cards[token].zone == Zone.CEASED
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 3])
def test_paid_sunfall_counts_committed_exiles_and_paid_token_transform(facts, seat, count):
    state = position(facts, seat)
    source = add(state, facts, 'Sunfall', seat, Zone.HAND)
    creatures = [add(state, facts, 'Torrential Gearhulk', seat if i == 0 else 3-seat) for i in range(count)]
    state.players[seat].mana_pool = {'C': 3, 'W': 2}
    state = cast(state, seat, source)
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = restore(state)
    resolve(state)
    assert all(state.cards[cid].zone == Zone.EXILE for cid in creatures)
    token = next(c for c in state.cards.values() if c.zone == Zone.BATTLEFIELD and c.is_token)
    assert token.controller == seat and 'Creature' not in token.types
    assert token.counters.get('+1/+1', 0) == count and len(token.card_faces) == 2
    state = transform_token(restore(state), seat, token.id, count)
    receipt(f'sunfall-{seat}-{count}', facts, ['Sunfall'], state, exiled=count, token_counters=count, transform_paid_C=2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('leave_source', [False, True])
def test_paid_seedshark_uses_actual_noncreature_cast_cause_not_discounted_cost(facts, seat, leave_source):
    state = position(facts, seat)
    shark = add(state, facts, 'Chrome Host Seedshark', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 2, 'U': 1}
    state = cast(state, seat, shark)
    assert sum(state.players[seat].mana_pool.values()) == 0
    resolve(state)
    assert state.cards[shark].zone == Zone.BATTLEFIELD
    creature = add(state, facts, 'Monastery Swiftspear', seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1}
    state = cast(respond(state, seat), seat, creature)
    assert all(item.effect_key != 'incubate' for item in state.stack)
    resolve(state)
    source = add(state, facts, 'Leyline Binding', seat, Zone.HAND)
    add(state, facts, 'Hallowed Fountain', seat)
    add(state, facts, 'Mountain', seat)
    yavi = add(state, facts, 'Yavimaya, Cradle of Growth', seat, Zone.HAND)
    state = act(respond(state, seat), seat, 'play_land', card_id=yavi)
    assert basic_land_type_count(state, seat) == 4
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = cast(state, seat, source)
    assert sum(state.players[seat].mana_pool.values()) == 0
    if state.pending_trigger_order:
        pending = state.pending_trigger_order
        assert pending.get('phase') != 'targets'
        group = pending['groups'][str(seat)]
        # Choose the legal public ordering with incubate last (top of stack).
        order = sorted(group, key=lambda item: item['effect_key'] == 'incubate')
        state = act(restore(state), seat, 'choose_trigger_order',
                    trigger_order=[item['_choice_id'] for item in order])
    trigger = state.stack[-1]
    assert trigger.effect_key == 'incubate' and trigger.source_card_id == shark
    assert trigger.controller == seat and trigger.payload['counters'] == 6
    if leave_source:
        channel = add(state, facts, 'Otawara, Soaring City', 3-seat, Zone.HAND)
        state.players[3-seat].mana_pool = {'C': 3, 'U': 1}
        state = act(respond(state, 3-seat), 3-seat, 'activate_ability', card_id=channel,
                    ability_index=1, targets={'target_card_id': shark})
        assert sum(state.players[3-seat].mana_pool.values()) == 0
        resolve(state)
        assert state.cards[shark].zone == Zone.HAND
    state = restore(state)
    resolve(state)
    token = next(c for c in state.cards.values() if c.is_token and c.zone == Zone.BATTLEFIELD)
    assert token.controller == seat and token.counters == {'+1/+1': 6}
    # Retain the unresolved original spell while paying the token's native ability.
    state = transform_token(restore(state), seat, token.id, 6)
    receipt(f'seedshark-{seat}-{leave_source}', facts, ['Chrome Host Seedshark', 'Leyline Binding'], state,
            triggering_mana_value=6, paid_cast_mana=2, source_departed=leave_source, transform_paid_C=2)

