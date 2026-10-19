"""Paid cost-increase, reservation and stale-object boundaries on full facts."""
import json
from hashlib import sha256

import pytest

import inventory as inv
import domain_paid_support as g
from test_march_pitch_paid import setup
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import collect_cost_options, check_cost_option_available
from rules_engine.engine import RulesEngine
from training.environment import TrainingEnvironment


@pytest.fixture(scope='module')
def facts():
    seed, selected, _ = inv.load_inputs()
    raws = {name: selected[row['scryfall_id']] for name, row in seed.items()}
    directory = inv.ROOT / 'backend/tests/fixtures/cost_reservation_overlap'
    proof = json.loads((directory / 'provenance.json').read_bytes())
    assert inv.sha(directory / 'canonical.json') == proof['canonical_json_sha256']
    supplemental = json.loads((directory / 'canonical.json').read_bytes())
    raw = supplemental['Skirge Familiar']
    canonical = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert sha256(canonical).hexdigest() == proof['rows']['Skirge Familiar']['raw_canonical_sha256']
    raws[raw['name']] = raw
    return raws


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x,n,expected_generic', [(4, 1, 3), (4, 2, 1), (2, 3, 0)])
def test_actual_paid_thalia_increase_then_discount_and_floor(facts, seat, x, n, expected_generic):
    state, action, *_ = setup(facts, seat, x, n)
    thalia = g.add(state, facts, 'Thalia, Guardian of Thraben', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = g.cast(state, seat, thalia)
    assert state.cards[thalia].zone == Zone.STACK
    assert state.stack[-1].payload['mana_spent'] == 2
    g.resolve(state)
    assert state.cards[thalia].zone == Zone.BATTLEFIELD
    state = g.respond(state, seat)
    state.players[seat].mana_pool = {'C': expected_generic, 'W': 1}
    if expected_generic:
        before = serialize_match_snapshot(state)
        insufficient = g.restore(state)
        insufficient.players[seat].mana_pool = {'C': expected_generic-1, 'W': 1}
        with pytest.raises(ActionRejected):
            checked_action(insufficient, RulesEngine(), seat, action)
        assert serialize_match_snapshot(state) == before
    paid = checked_action(state, RulesEngine(), seat, action)
    assert paid.stack[-1].payload['mana_spent'] == expected_generic+1
    assert sum(paid.players[seat].mana_pool.values()) == 0
    g.resolve(paid)
    assert paid.cards[action['targets']['target_card_id']].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('has_fuel', [False, True])
def test_pitch_cards_cannot_also_pay_real_discard_mana_ability(facts, seat, has_fuel):
    state, action, whites, red, _ = setup(facts, seat, x=4, n=1)
    # Fixture-zone setup leaves precisely one selected white card and the spell
    # in hand; any optional extra mana fuel is an independently declared card.
    for cid in whites[1:]+[red]:
        state.players[seat].hand.remove(cid)
        state.cards[cid].move_to_zone(Zone.LIBRARY)
        state.players[seat].library.append(cid)
    familiar = g.add(state, facts, 'Skirge Familiar', seat)
    fuel = g.add(state, facts, 'Searing Blaze', seat, Zone.HAND) if has_fuel else None
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    card = state.cards[action['card_id']]
    option = next(o for o in collect_cost_options(state, seat, card) if o.id == 'base')
    before = serialize_match_snapshot(state)
    assert check_cost_option_available(state, seat, card, option, x_value=4,
                                       cost_choice=action['cost_choice']) == has_fuel
    assert serialize_match_snapshot(state) == before
    if not has_fuel:
        for route in ('checked', 'direct'):
            with pytest.raises(ActionRejected):
                if route == 'checked':
                    checked_action(state, RulesEngine(), seat, action)
                else:
                    RulesEngine().take_action(state, seat, action, reject_invalid=True)
            assert serialize_match_snapshot(state) == before
        return
    paid = checked_action(g.restore(state), RulesEngine(), seat, action)
    assert paid.stack[-1].payload['mana_spent'] == 3
    assert paid.cards[whites[0]].zone == Zone.EXILE
    assert paid.cards[fuel].zone == Zone.GRAVEYARD
    assert paid.cards[familiar].zone == Zone.BATTLEFIELD
    assert sum(paid.players[seat].mana_pool.values()) == 0
    g.resolve(paid)
    assert paid.cards[action['targets']['target_card_id']].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['checked', 'direct'])
def test_selected_white_stale_after_actual_paid_cast_rejected(facts, seat, route):
    state, action, whites, *_ = setup(facts, seat)
    selected = whites[2]
    action['cost_choice']['exile_card_ids'] = [selected]
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = g.cast(state, seat, selected)
    assert state.cards[selected].zone == Zone.STACK
    g.resolve(state)
    assert state.cards[selected].zone == Zone.BATTLEFIELD
    state = g.respond(state, seat)
    state.players[seat].mana_pool = {'C': 20, 'W': 1}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        if route == 'checked':
            checked_action(state, RulesEngine(), seat, action)
        else:
            RulesEngine().take_action(state, seat, action, reject_invalid=True)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_training_requirement_public_option_contract(facts, seat):
    state, action, *_ = setup(facts, seat)
    consumer = TrainingEnvironment()
    consumer._state = g.restore(state)
    consumer._rules = RulesEngine()
    before = serialize_match_snapshot(consumer._state)
    consumer._require_choices(action, seat)
    assert serialize_match_snapshot(consumer._state) == before
