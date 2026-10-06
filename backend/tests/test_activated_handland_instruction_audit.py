"""Full canonical tap abilities, deliberate identities and actual paid continuations."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone, Step
from game_state.serializers import serialize_match, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from tests.ai_knowledge_consumer_fixture import position, take
from tests.test_linked_damage_targets import raw_card
from tests.test_optional_land_from_hand_audit import action, advance, roundtrip

FIXTURE = Path(__file__).parent / 'fixtures/activated_handland'
ROWS = {}
for entry in json.loads((FIXTURE / 'provenance.json').read_text())['cards']:
    raw = (FIXTURE / entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    row = json.loads(raw)
    assert row['oracle_id'] == entry['oracle_id']
    ROWS[row['name']] = row
FAMILIES = list(ROWS)


def setup(name, seat, *, eligible=True, sick=False):
    state = position('Ramp', 'Tempo', seat)
    state.mechanic_choice_players = {1, 2}
    source = raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD)
    source.summoning_sick = sick
    source.entered_turn = state.turn if sick else state.turn - 1
    state.active_player = 3-seat
    state.priority_player = seat
    state.step = Step.END_STEP
    lands = [take(state, 'Forest', seat, Zone.HAND),
             take(state, 'Tropical Island', seat, Zone.HAND)] if eligible else []
    enemy = take(state, 'Delver of Secrets', 3-seat, Zone.HAND)
    state.players[seat].lands_played_this_turn = 1
    return state, source, lands, enemy


def activation(source):
    return {'type': 'activate_ability', 'card_id': source.id,
            'ability_index': 0, 'targets': {}}


def paid(state, source, seat):
    before = serialize_match_snapshot(state)
    offered = [m for m in RulesEngine().legal_moves(state, seat)
               if m['type'] == 'activate_ability' and m['card_id'] == source.id]
    assert len(offered) == 1 and offered[0]['ability_index'] == 0
    assert serialize_match_snapshot(state) == before
    ledger = []
    result = action(state, seat, activation(source), ledger)
    assert result.cards[source.id].tapped and not state.cards[source.id].tapped
    assert result.stack[-1].source_card_id == source.id
    assert result.stack[-1].controller == seat
    assert result.stack[-1].effect_key == 'put_land_from_hand'
    assert result.stack[-1].payload['optional'] is True
    return result, ledger


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_full_printed_extraction_real_tap_and_opponents_end_step(seat, name, tmp_path):
    state, source, _, _ = setup(name, seat)
    assert source.oracle_text == ROWS[name]['oracle_text']
    ability = extract_activated_abilities(source)
    assert len(ability) == 1 and ability[0]['mana_cost'] == '{T}'
    assert ability[0]['text'] == 'You may put a land card from your hand onto the battlefield.'
    state, ledger = paid(state, source, seat)
    roundtrip(state, tmp_path / 'paid.sqlite')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('select', [False, True])
def test_deliberate_second_land_or_empty_decline_private_pending_restart(seat, name, select, tmp_path):
    state, source, lands, enemy = setup(name, seat)
    state, ledger = paid(state, source, seat)
    state = advance(state, ledger)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'land_from_hand' and pending['player_id'] == seat
    assert pending['min_count'] == 0 and pending['count'] == 1
    assert set(pending['options']) == {land.id for land in lands}
    assert all(land.id in state.players[seat].hand for land in lands)
    public = serialize_match(state, look_players=(3-seat,))['pending_mechanic_choice']
    assert set(public) == {'kind', 'player_id', 'label', 'count', 'min_count'}
    assert not RulesEngine().legal_moves(state, 3-seat)
    before = serialize_match_snapshot(state)
    for actor, ids in [(3-seat, [lands[1].id]), (seat, [enemy.id]),
                       (seat, [lands[1].id, lands[1].id]), (seat, [source.id])]:
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), actor, {'type': 'choose_mechanic', 'card_ids': ids})
        assert serialize_match_snapshot(state) == before
    state = roundtrip(state, tmp_path / 'pending.sqlite')
    state = action(state, seat, {'type': 'choose_mechanic',
                   'card_ids': [lands[1].id] if select else []}, ledger)
    state = advance(state, ledger)
    assert lands[0].id in state.players[seat].hand
    assert lands[1].id in (state.players[seat].battlefield if select else state.players[seat].hand)
    if select:
        assert not state.cards[lands[1].id].tapped
    assert state.cards[source.id].tapped and state.pending_mechanic_choice is None
    assert state.players[seat].lands_played_this_turn == 1
    roundtrip(state, tmp_path / 'completed.sqlite')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('invalid', ['sick', 'tapped', 'foreign', 'index'])
def test_unpayable_or_wrong_controller_activation_root_pure(seat, name, invalid):
    state, source, _, _ = setup(name, seat, sick=invalid == 'sick')
    request = activation(source)
    if invalid == 'tapped':
        source.tapped = True
    elif invalid == 'foreign':
        request_actor = 3-seat
        state.priority_player = request_actor
    elif invalid == 'index':
        request['ability_index'] = 99
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat if invalid == 'foreign' else seat, request)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_no_eligible_hand_land_consumes_tap_without_fabricated_choice(seat, name, tmp_path):
    state, source, _, _ = setup(name, seat, eligible=False)
    state, ledger = paid(state, source, seat)
    state = advance(state, ledger)
    assert state.cards[source.id].tapped and not state.stack
    assert state.pending_mechanic_choice is None
    roundtrip(state, tmp_path / 'no-land.sqlite')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_paid_creature_cast_cannot_pay_tap_cost_before_next_own_turn(seat, name, tmp_path):
    state = position('Ramp', 'Tempo', seat)
    state.mechanic_choice_players = {1, 2}
    source = raw_card(state, ROWS[name], seat, Zone.HAND)
    take(state, 'Forest', seat, Zone.BATTLEFIELD)
    take(state, 'Tropical Island', seat, Zone.BATTLEFIELD)
    take(state, 'Forest', seat, Zone.HAND)
    ledger = []
    state = action(state, seat, {'type': 'cast_spell', 'card_id': source.id,
                                'cost_choice': {'id': 'base'}}, ledger)
    assert state.stack[-1].payload['mana_spent'] == (1 if name == 'Sakura-Tribe Scout' else 2)
    state = advance(state, ledger)
    assert source.id in state.players[seat].battlefield
    assert state.cards[source.id].summoning_sick
    state = roundtrip(state, tmp_path / 'paid-cast.sqlite')
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, activation(source))
    assert serialize_match_snapshot(state) == before
