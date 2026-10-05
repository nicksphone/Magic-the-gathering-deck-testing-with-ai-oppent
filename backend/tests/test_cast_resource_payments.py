"""Canonical payment positions; no Oracle or deck data is altered."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.casting_resources import resource_candidates, resource_payment, apply_resource_payment
from rules_engine.mana import _payment_requirements, can_pay_with_pool_and_lands, auto_pay_cost
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add
from tests.test_ai_search_prefix import bare_state


DIRECTORY = Path(__file__).parent / 'fixtures' / 'cast_resources'
RAW = json.loads((DIRECTORY / 'canonical.json').read_text())
ROWS = {row['name']: {**row, 'power': row.get('power'), 'toughness': row.get('toughness')}
        for row in RAW['data']}


def position(seat, name):
    state = bare_state(seat)
    card = add(state, name, seat, Zone.HAND, cards=ROWS)
    return state, card


def cost(card, x=0):
    return _payment_requirements(card.mana_cost, False, x, 0, 0)[0]


def test_canonical_fixture_is_complete_and_unmodified():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert len(RAW['data']) == 19 and not RAW.get('not_found')
    assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == provenance['sha256']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Dig Through Time', 'Treasure Cruise', 'Hooting Mandrills'])
def test_delve_pays_only_generic_and_does_not_generate_mana(seat, name):
    state, card = position(seat, name)
    exiles = [add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=ROWS).id for _ in range(2)]
    before = serialize_match_snapshot(state)
    req = cost(card)
    plan = resource_payment(state, seat, card, req, {'delve': exiles})
    assert plan.remaining['generic'] == req['generic'] - 2
    assert all(plan.remaining[color] == req[color] for color in 'WUBRGCS')
    assert serialize_match_snapshot(state) == before
    pools = deepcopy(state.players[seat].mana_pool)
    assert apply_resource_payment(state, seat, card, plan)
    assert state.players[seat].mana_pool == pools
    assert all(cid in state.players[seat].exile and state.cards[cid].zone == Zone.EXILE for cid in exiles)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Siege Wurm', 'Chord of Calling', 'March of the Multitudes'])
def test_convoke_colored_and_generic_even_with_summoning_sickness(seat, name):
    state, card = position(seat, name)
    green = add(state, 'Llanowar Elves', seat, cards=ROWS)
    generic = add(state, 'Ornithopter', seat, cards=ROWS)
    green.summoning_sick = generic.summoning_sick = True
    req = cost(card, 3)
    plan = resource_payment(state, seat, card, req, {'convoke': [
        {'card_id': green.id, 'pay_as': 'G'}, {'card_id': generic.id, 'pay_as': 'generic'}]})
    assert plan.remaining['G'] == req['G'] - 1
    assert plan.remaining['generic'] == req['generic'] - 1
    assert apply_resource_payment(state, seat, card, plan)
    assert green.tapped and generic.tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Metallic Rebuke', 'Reverse Engineer', 'Herald of Anguish'])
def test_improvise_pays_generic_not_colored(seat, name):
    state, card = position(seat, name)
    artifact = add(state, 'Sol Ring', seat, cards=ROWS)
    req = cost(card)
    plan = resource_payment(state, seat, card, req, {'improvise': [artifact.id]})
    assert plan.remaining['generic'] == req['generic'] - 1
    assert all(plan.remaining[color] == req[color] for color in 'WUBRGCS')
    assert apply_resource_payment(state, seat, card, plan)
    assert artifact.tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['foreign', 'tapped', 'duplicate', 'wrong_type', 'wrong_color', 'colorless', 'snow', 'overpay', 'reserved'])
def test_convoke_rejections_are_pure(seat, invalid):
    state, card = position(seat, 'Siege Wurm')
    green = add(state, 'Llanowar Elves', 3-seat if invalid == 'foreign' else seat, cards=ROWS)
    choices = [{'card_id': green.id, 'pay_as': 'G'}]
    unavailable = set()
    if invalid == 'tapped': green.tapped = True
    if invalid == 'duplicate': choices *= 2
    if invalid == 'wrong_type': choices[0]['card_id'] = add(state, 'Sol Ring', seat, cards=ROWS).id
    if invalid in {'wrong_color', 'colorless', 'snow'}: choices[0]['pay_as'] = {'wrong_color': 'U', 'colorless': 'C', 'snow': 'S'}[invalid]
    req = cost(card)
    if invalid == 'overpay': req['G'] = 0
    if invalid == 'reserved': unavailable.add(green.id)
    before = serialize_match_snapshot(state)
    assert resource_payment(state, seat, card, req, {'convoke': choices}, unavailable_tap_ids=unavailable) is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_delve_wrong_zone_owner_duplicates_and_excess(seat):
    state, card = position(seat, 'Dig Through Time')
    own = add(state, 'Sol Ring', seat, Zone.GRAVEYARD, cards=ROWS)
    foreign = add(state, 'Sol Ring', 3-seat, Zone.GRAVEYARD, cards=ROWS)
    for ids in ([foreign.id], [own.id, own.id], [card.id]):
        assert resource_payment(state, seat, card, cost(card), {'delve': ids}) is None
    req = cost(card)
    req['generic'] = 0
    assert resource_payment(state, seat, card, req, {'delve': [own.id]}) is None
    assert resource_payment(state, seat, card, cost(card), {'delve': [own.id]}, reserved_card_ids={own.id}) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_snapshot_and_stale_selection_are_checked_before_any_resource_mutation(seat):
    state, card = position(seat, 'Chord of Calling')
    cards = [add(state, 'Llanowar Elves', seat, cards=ROWS) for _ in range(2)]
    plan = resource_payment(state, seat, card, cost(card, 2), {'convoke': [
        {'card_id': c.id, 'pay_as': 'G'} for c in cards]})
    cards[1].tapped = True
    before = serialize_match_snapshot(state)
    assert not apply_resource_payment(state, seat, card, plan)
    assert serialize_match_snapshot(state) == before and not cards[0].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_resource_candidates_have_no_mana_ability_or_sickness_requirement(seat):
    state, card = position(seat, 'Siege Wurm')
    green = add(state, 'Dryad Arbor', seat, cards=ROWS)
    blank = add(state, 'Ornithopter', seat, cards=ROWS)
    green.summoning_sick = blank.summoning_sick = True
    view = resource_candidates(state, seat, card)
    options = {row['card_id']: row['pay_as'] for row in view['convoke']}
    assert options[green.id] == ['generic', 'G']
    assert options[blank.id] == ['generic']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,keyword,color,count', [
    ('Dig Through Time', 'delve', 'U', 6),
    ('Reverse Engineer', 'improvise', 'U', 3),
    ('Hooting Mandrills', 'delve', 'G', 5),
])
def test_actual_cast_uses_shared_legal_witness_and_full_transaction(seat, name, keyword, color, count):
    state, card = position(seat, name)
    state.players[seat].mana_pool = {c: 2 if c == color else 0 for c in 'WUBRGC'}
    resource_name = 'Ornithopter' if keyword == 'delve' else 'Sol Ring'
    zone = Zone.GRAVEYARD if keyword == 'delve' else Zone.BATTLEFIELD
    resources = [add(state, resource_name, seat, zone, cards=ROWS).id for _ in range(count)]
    action = {'type': 'cast_spell', 'card_id': card.id, 'resource_payment': {keyword: resources}}
    before = serialize_match_snapshot(state)
    legal = RulesEngine().legal_moves(state, seat)
    assert any(move['type'] == 'cast_spell' and move['card_id'] == card.id for move in legal)
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    assert len(result.stack) == 1 and result.cards[card.id].zone == Zone.STACK
    if keyword == 'delve':
        assert all(cid in result.players[seat].exile for cid in resources)
    else:
        assert all(result.cards[cid].tapped for cid in resources)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_convoke_cast_requires_no_mana_and_keeps_printed_cost(seat):
    state, card = position(seat, 'Siege Wurm')
    for color in state.players[seat].mana_pool:
        state.players[seat].mana_pool[color] = 0
    green = [add(state, 'Llanowar Elves', seat, cards=ROWS).id for _ in range(2)]
    generic = [add(state, 'Ornithopter', seat, cards=ROWS).id for _ in range(5)]
    action = {'type': 'cast_spell', 'card_id': card.id, 'resource_payment': {'convoke': [
        *[{'card_id': cid, 'pay_as': 'G'} for cid in green],
        *[{'card_id': cid, 'pay_as': 'generic'} for cid in generic]]}}
    result = checked_action(state, RulesEngine(), seat, action)
    assert all(result.cards[cid].tapped for cid in green + generic)
    assert result.cards[card.id].mana_cost == ROWS['Siege Wurm']['mana_cost']


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_delve_cast_records_mana_spent_not_generic_substitutions(seat):
    state, card = position(seat, 'Dig Through Time')
    state.players[seat].mana_pool = {c: 2 if c == 'U' else 0 for c in 'WUBRGC'}
    for _ in range(6):
        add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=ROWS)
    result = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': card.id})
    assert result.stack[-1].payload['mana_spent'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_improvise_mana_source_cannot_both_tap_for_mana_and_substitute(seat):
    state, card = position(seat, 'Reverse Engineer')
    state.players[seat].mana_pool = {c: 2 if c == 'U' else 0 for c in 'WUBRGC'}
    ring = add(state, 'Sol Ring', seat, cards=ROWS)
    ring.summoning_sick = False
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': card.id,
                       'resource_payment': {'improvise': [ring.id]}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_deliberate_empty_choice_preserves_resources_and_rejects_insufficient_mana(seat):
    state, card = position(seat, 'Dig Through Time')
    state.players[seat].mana_pool = {c: 2 if c == 'U' else 0 for c in 'WUBRGC'}
    for _ in range(6):
        add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=ROWS)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': card.id,
                                                 'resource_payment': {}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_payment_callbacks_are_pure_and_report_only_actual_mana(seat):
    state, card = position(seat, 'Metallic Rebuke')
    state.players[seat].mana_pool = {c: 1 if c == 'U' else 0 for c in 'WUBRGC'}
    ids = [add(state, 'Ornithopter', seat, cards=ROWS).id for _ in range(2)]
    before = serialize_match_snapshot(state)
    context = {'card_name': card.name, 'oracle_text': card.oracle_text,
               'source_card_id': card.id, 'cast_resource_card': card}
    assert can_pay_with_pool_and_lands(state, seat, card.mana_cost, **context)
    assert serialize_match_snapshot(state) == before
    details = {}
    assert auto_pay_cost(state, seat, card.mana_cost, payment_details=details, **context)
    assert details['mana_spent'] == 1
    assert set(details['resource_payment']['improvise']) == set(ids)
    assert all(state.cards[cid].tapped for cid in ids)


@pytest.mark.parametrize('seat', [1, 2])
def test_hogaak_combines_convoke_and_delve_without_spending_mana(seat):
    state, card = position(seat, 'Hogaak, Arisen Necropolis')
    state.players[seat].mana_pool = {c: 20 for c in 'WUBRGC'}
    green = [add(state, 'Llanowar Elves', seat, cards=ROWS).id for _ in range(2)]
    generic = [add(state, 'Ornithopter', seat, cards=ROWS).id for _ in range(2)]
    exiles = [add(state, 'Ornithopter', seat, Zone.GRAVEYARD, cards=ROWS).id for _ in range(3)]
    action = {'type': 'cast_spell', 'card_id': card.id, 'hybrid_choices': ['G', 'G'], 'cost_choice': {'id': 'base'},
              'resource_payment': {'delve': exiles, 'convoke': [
                  *[{'card_id': cid, 'pay_as': 'G'} for cid in green],
                  *[{'card_id': cid, 'pay_as': 'generic'} for cid in generic]]}}
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.players[seat].mana_pool == state.players[seat].mana_pool
    assert result.stack[-1].payload['mana_spent'] == 0
    assert set(result.players[seat].exile) == set(exiles)


@pytest.mark.parametrize('seat', [1, 2])
def test_hogaak_cannot_use_mana_instead_of_required_resources(seat):
    state, card = position(seat, 'Hogaak, Arisen Necropolis')
    state.players[seat].mana_pool = {c: 20 for c in 'WUBRGC'}
    before = serialize_match_snapshot(state)
    assert not can_pay_with_pool_and_lands(state, seat, card.mana_cost,
        oracle_text=card.oracle_text, source_card_id=card.id, cast_resource_card=card)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': card.id})
    assert serialize_match_snapshot(state) == before
