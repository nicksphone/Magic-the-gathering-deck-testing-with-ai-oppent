"""Unmarked canonical escape desired scenarios; original strict xfails untouched."""
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana_abilities import mana_ability_specs
from tests.test_fixed_spell_cost_witness import add
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_spell_cost_overlap_investigation import escape_position, cast, unchanged_root


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('funding', ['tower', 'already-funded', 'free-alternative'])
@pytest.mark.parametrize('explicit', [False, True])
def test_real_mana_creates_escape_card_without_preparation(seat, funding, explicit):
    state, tower, creature, spell, grave = escape_position(seat)
    if funding == 'already-funded':
        state.players[seat].mana_pool['B'] = 2
    if funding == 'free-alternative':
        add(state, 'Swamp', seat)
        add(state, 'Swamp', seat)
    action = cast(spell, from_graveyard=True, cost_choice={'id': 'escape'})
    if explicit:
        action['escape_exile_ids'] = [*grave, creature.id]
    with unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    assert paid.cards[tower.id].tapped
    assert paid.cards[spell.id].zone == Zone.STACK
    assert all(paid.cards[cid].zone == Zone.EXILE for cid in [*grave, creature.id])
    item = next(item for item in paid.stack if item.source_card_id == spell.id)
    assert item.controller == seat and item.payload['mana_spent'] == 5
    assert item.payload['__escaped']
    restored = deserialize_match_snapshot(serialize_match_snapshot(paid))
    for _ in range(12):
        if not restored.stack:
            break
        restored = checked_action(restored, RulesEngine(), restored.priority_player,
                                  {'type': 'pass_priority'})
    assert not restored.stack
    assert restored.cards[spell.id].zone == Zone.BATTLEFIELD
    assert restored.cards[spell.id].counters.get('+1/+1') == 2
    goats = [card for card in restored.cards.values()
             if card.is_token and card.zone == Zone.BATTLEFIELD and card.owner == seat
             and card.name == 'Goat']
    assert len(goats) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['insufficient-mana', 'one-fewer-grave', 'duplicate',
                                'source', 'foreign', 'unknown', 'wrong-actor'])
def test_invalid_ordered_escape_is_atomic(seat, bad):
    state, _, creature, spell, grave = escape_position(seat, initial=2 if bad == 'one-fewer-grave' else 3)
    if bad == 'insufficient-mana':
        state.players[seat].mana_pool = {}
    action = cast(spell, from_graveyard=True, cost_choice={'id': 'escape'})
    actor = seat
    if bad in {'duplicate','source','foreign','unknown'}:
        extra = {'duplicate': grave[0], 'source': spell.id, 'unknown': 'missing-card'}
        if bad == 'foreign':
            extra['foreign'] = add(state, 'Island', 3-seat, Zone.GRAVEYARD).id
        action['escape_exile_ids'] = [*grave, extra[bad]]
    if bad == 'wrong-actor':
        actor = 3-seat
    with unchanged_root(state), pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), actor, action)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_graveyard_replacement_cannot_manufacture_escape_card(seat):
    state, tower, creature, spell, grave = escape_position(seat)
    path = Path(__file__).parents[2] / 'backend/tests/fixtures/death_cycle_ordering/canonical.json'
    rows = json.loads(path.read_text())
    row = rows['Leyline of the Void']
    raw_add(state, 'Leyline of the Void', 3-seat, cards={row['name']: {
        **row, 'power': row.get('power'), 'toughness': row.get('toughness')}})
    spec = next(spec for spec in mana_ability_specs(tower, state) if 'Sacrifice' in spec[1])
    with unchanged_root(state):
        prepared = checked_action(state, RulesEngine(), seat, {
            'type': 'activate_mana_ability', 'card_id': tower.id,
            'ability_index': spec[0], 'color': 'B',
            'payment_choices': {'sacrifice_card_ids': [creature.id]}})
    assert prepared.cards[creature.id].zone == Zone.EXILE
    assert creature.id not in prepared.players[seat].graveyard
    action = cast(spell, from_graveyard=True, cost_choice={'id': 'escape'})
    with unchanged_root(state), pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
