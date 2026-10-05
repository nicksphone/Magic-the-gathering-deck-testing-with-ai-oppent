"""Canonical graveyard watchers see actual departures, not newly entering watchers."""
import pytest

from game_state.state import Zone
from effects.handlers import exile_from_graveyard, return_creature_from_graveyard_to_battlefield
from tests.test_cast_resource_payments import ROWS, add, cost, position
from rules_engine.casting_resources import apply_resource_payment, resource_payment
from tests.test_ai_recurring_engines import resolve


@pytest.mark.parametrize('seat', [1, 2])
def test_delve_batch_triggers_once_and_creates_correct_tapped_zombie(seat):
    state, spell = position(seat, 'Dig Through Time')
    watcher = add(state, 'Tormod, the Desecrator', seat, cards=ROWS)
    cards = [add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=ROWS) for _ in range(3)]
    plan = resource_payment(state, seat, spell, cost(spell), {'delve': [c.id for c in cards]})
    assert apply_resource_payment(state, seat, spell, plan)
    assert len(state.stack) == 1
    state = resolve(state)
    tokens = [state.cards[cid] for cid in state.players[seat].battlefield if cid != watcher.id]
    assert len(tokens) == 1
    token = tokens[0]
    assert (token.name, token.power, token.toughness, token.colors, token.tapped) == ('Zombie', 2, 2, ['B'], True)


@pytest.mark.parametrize('seat', [1, 2])
def test_separate_departures_and_wrong_owner_are_distinct(seat):
    state, _ = position(seat, 'Dig Through Time')
    add(state, 'Tormod, the Desecrator', seat, cards=ROWS)
    foreign = add(state, 'Ornithopter', 3-seat, Zone.GRAVEYARD, cards=ROWS)
    exile_from_graveyard(state, seat, {'target_card_id': foreign.id})
    assert not state.stack
    for _ in range(2):
        card = add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=ROWS)
        exile_from_graveyard(state, 3-seat, {'target_card_id': card.id})
        exile_from_graveyard(state, 3-seat, {'target_card_id': card.id})
    assert len(state.stack) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_real_cast_stages_departure_above_spell_and_snapshot_retains_it(seat):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
    state, spell = position(seat, 'Dig Through Time')
    watcher = add(state, 'Tormod, the Desecrator', seat, cards=ROWS)
    for _ in range(6):
        add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=ROWS)
    state.players[seat].mana_pool = {c: 2 if c == 'U' else 0 for c in 'WUBRGC'}
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id})
    assert [item.source_card_id for item in state.stack] == [spell.id, watcher.id]
    snapshot = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot


@pytest.mark.parametrize('seat', [1, 2])
def test_mass_exile_collects_both_seats_in_apnap_order(seat):
    from effects.handlers import exile_all_graveyards
    state, _ = position(seat, 'Dig Through Time')
    watchers = {}
    for pid in (1, 2):
        watchers[pid] = add(state, 'Tormod, the Desecrator', pid, cards=ROWS)
        for _ in range(2):
            add(state, 'Ornithopter', pid, Zone.GRAVEYARD, cards=ROWS)
    exile_all_graveyards(state, seat, {})
    assert [item.source_card_id for item in state.stack] == [watchers[seat].id, watchers[3-seat].id]


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_departure_looks_back_before_returned_humility(seat):
    import json
    from pathlib import Path
    from effects.handlers import return_permanent_from_graveyard_to_battlefield
    data = json.loads((Path(__file__).parent / 'fixtures/type_effect_lifecycle.json').read_text())
    cards = {row['name']: row for row in data}
    state, _ = position(seat, 'Dig Through Time')
    watcher = add(state, 'Tormod, the Desecrator', seat, cards=ROWS)
    humility = add(state, 'Humility', seat, Zone.GRAVEYARD, cards=cards)
    return_permanent_from_graveyard_to_battlefield(state, seat, {'target_card_id': humility.id})
    assert len(state.stack) == 1 and state.stack[-1].source_card_id == watcher.id


@pytest.mark.parametrize('seat', [1, 2])
def test_returned_watcher_does_not_see_own_departure(seat):
    state, _ = position(seat, 'Dig Through Time')
    watcher = add(state, 'Tormod, the Desecrator', seat, Zone.GRAVEYARD, cards=ROWS)
    return_creature_from_graveyard_to_battlefield(state, seat, {'target_card_id': watcher.id})
    assert watcher.zone == Zone.BATTLEFIELD
    assert not state.stack
