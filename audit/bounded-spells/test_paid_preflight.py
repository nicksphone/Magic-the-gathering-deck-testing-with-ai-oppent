"""Paid canonical actions distinguish unselected diagnostics from execution gaps."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
import inventory as inv
import domain_paid_support as paid
from card_data.hydration import hydrate_deck_cards
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine

OUT = Path(os.environ['GAP6_EVIDENCE'])
ROWS = []
NAMES = ['Force of Vigor', 'March of Otherworldly Light',
         'March of the Multitudes', 'Secure the Wastes', 'Searing Blaze']


@pytest.fixture(scope='module')
def facts():
    seed, raws, provenance = inv.load_inputs()
    result = {}
    for name in [*NAMES, 'Forest', 'Llanowar Elves', "Witch's Oven", 'Intangible Virtue']:
        row = hydrate_deck_cards(None, [{'card_name': name, 'quantity': 1}])[0]
        raw = raws[seed[name]['scryfall_id']]
        assert row['oracle_text'] == raw['oracle_text']
        result[name] = {**row, 'name': name}
    return result


def setup(facts, seat, name, count=2):
    state = paid.position(facts, seat)
    source = paid.add(state, facts, name, seat, Zone.HAND)
    artifact = paid.add(state, facts, "Witch's Oven", 3-seat)
    enchantment = paid.add(state, facts, 'Intangible Virtue', 3-seat)
    creature = paid.add(state, facts, 'Llanowar Elves', 3-seat)
    land = paid.add(state, facts, 'Forest', 3-seat)
    targets = {'Force of Vigor': {'target_card_ids': [artifact, enchantment][:count]},
               'March of Otherworldly Light': {'x_value': 2, 'target_card_id': creature},
               'March of the Multitudes': {'x_value': 2},
               'Secure the Wastes': {'x_value': 2},
               'Searing Blaze': {'target_player': 3-seat, 'target_card_id': creature}}[name]
    pool = {'Force of Vigor': {'C': 2, 'G': 2},
            'March of Otherworldly Light': {'C': 2, 'W': 1},
            'March of the Multitudes': {'C': 2, 'W': 2, 'G': 1},
            'Secure the Wastes': {'C': 2, 'W': 1},
            'Searing Blaze': {'R': 2}}[name]
    state.players[seat].mana_pool = deepcopy(pool)
    if name == 'March of Otherworldly Light':
        offered = next(m for m in RulesEngine().legal_moves(state, seat)
                       if m['type'] == 'cast_spell' and m['card_id'] == source)
        assert any(o['id'] == 'base' for o in offered['cost_options'])
    return state, source, targets, pool, (artifact, enchantment, creature, land)


def record(label, facts, name, seat, before, state, **details):
    row = {'case': label, 'name': name, 'seat': seat,
           'body_sha256': inv.canonical_hash(facts[name]),
           'before': inv.canonical_hash(before),
           'after': inv.canonical_hash(serialize_match_snapshot(state)), **details}
    ROWS.append(row)


def cast(state, seat, source, targets):
    fields = {}
    if state.cards[source].name == 'March of Otherworldly Light':
        fields['cost_choice'] = {'id': 'base', 'exile_card_ids': []}
    return paid.act(state, seat, 'cast_spell', card_id=source, targets=targets, **fields)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,count', [(NAMES[0], 0), (NAMES[0], 1), (NAMES[0], 2),
                                     *[(name, 2) for name in NAMES[1:]]])
def test_paid_selected_complete_stack_body(facts, seat, name, count):
    state, source, targets, pool, ids = setup(facts, seat, name, count)
    before = serialize_match_snapshot(state)
    opponent_hand = list(state.players[3-seat].hand)
    state = cast(state, seat, source, targets)
    record('paid', facts, name, seat, before, state, count=count, targets=targets,
           pool_before=pool, pool_after=state.players[seat].mana_pool,
           effect=state.stack[-1].effect_key, payload=state.stack[-1].payload)
    assert len(state.stack) == 1 and state.cards[source].zone == Zone.STACK
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.players[3-seat].hand == opponent_hand
    state = paid.restore(state)
    state = paid.resolve(state)
    record('resolved', facts, name, seat, before, state, count=count,
           zones={cid: state.cards[cid].zone.value for cid in ids},
           life=state.players[3-seat].life)
    assert not state.stack and state.cards[source].zone == Zone.GRAVEYARD
    assert state.players[3-seat].hand == opponent_hand
    if name == 'Force of Vigor':
        for index, cid in enumerate(ids[:2]):
            assert state.cards[cid].zone == (Zone.GRAVEYARD if index < count else Zone.BATTLEFIELD)
    elif name == 'March of Otherworldly Light':
        assert state.cards[ids[2]].zone == Zone.EXILE
    elif name == 'Searing Blaze':
        assert state.players[3-seat].life == 19
        assert state.cards[ids[2]].zone == Zone.GRAVEYARD
    else:
        tokens = [state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token]
        assert len(tokens) == 2
        assert all((c.power, c.toughness, c.colors) == (1, 1, ['W']) for c in tokens)
        assert all(c.name == ('Soldier' if name == 'March of the Multitudes' else 'Warrior') for c in tokens)
        assert all(('lifelink' in [k.lower() for k in c.keywords]) ==
                   (name == 'March of the Multitudes') for c in tokens)
    paid.restore(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', NAMES)
def test_unknown_suffix_rejected_before_payment(facts, seat, name):
    state, source, targets, _, _ = setup(facts, seat, name)
    state.cards[source].oracle_text += '\nUnknown audit instruction.'
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, source, targets)
    assert serialize_match_snapshot(state) == before
    record('unknown-suffix-rejected', facts, name, seat, before, state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Force of Vigor', 'March of Otherworldly Light', 'Searing Blaze'])
def test_invalid_public_target_is_atomic(facts, seat, name):
    state, source, targets, _, ids = setup(facts, seat, name)
    if name == 'Force of Vigor':
        targets['target_card_ids'] = [ids[2]]
    elif name == 'March of Otherworldly Light':
        targets['target_card_id'] = ids[3]
    else:
        own = paid.add(state, facts, 'Llanowar Elves', seat)
        targets['target_card_id'] = own
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, source, targets)
    assert serialize_match_snapshot(state) == before
    record('invalid-target-rejected', facts, name, seat, before, state)


def test_publish_receipts():
    (OUT/'paid-receipts.json').write_text(json.dumps(ROWS, indent=2, sort_keys=True)+'\n')
