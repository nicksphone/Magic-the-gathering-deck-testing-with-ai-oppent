"""Complete canonical bodies and real paid search paths; missing support stays RED."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.oracle_effects import extract_activated_abilities, inspect_target_hints
from rules_engine.action_validation import ActionRejected
from tests.test_paid_counter_family_audit import board, raw_card, act, snap, restart, passes
from tests.test_batch_graveyard_publication_audit import assert_private

FIXTURE = Path(__file__).parent / 'fixtures/targeted_search'
ROWS = {}
for entry in json.loads((FIXTURE / 'provenance.json').read_text())['cards']:
    raw = (FIXTURE / entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    row = json.loads(raw)
    assert row['oracle_id'] == entry['oracle_id']
    ROWS[row['name']] = row


def setup(name, seat):
    state, old, target = board(seat, 'Fertilid')
    if name == 'Fertilid':
        assert state.cards[old].oracle_text == ROWS[name]['oracle_text']
        source = old
    else:
        source = raw_card(state, ROWS[name], seat, Zone.HAND).id
        state.players[seat].mana_pool = {'G': 1, 'C': 3 if name == "Fertilid's Favor" else 1}
    basic = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_text())['cards']['Island']
    lands = {pid: [raw_card(state, basic, pid, Zone.LIBRARY).id for _ in range(3)] for pid in (1, 2)}
    return state, source, target, lands


@pytest.mark.parametrize('name', ['Fertilid', "Fertilid's Favor"])
@pytest.mark.parametrize('seat', [1, 2])
def test_full_body_compiles_explicit_target_and_entire_ordered_suffix(name, seat):
    state, source, target, _ = setup(name, seat)
    proxy = deepcopy(state.cards[source])
    if name == 'Fertilid':
        # Pure analysis of the actual extracted body; never executed as a fake card.
        proxy.oracle_text = extract_activated_abilities(proxy)[0]['text']
        proxy.mana_cost = ''
        proxy.card_faces = []
    before = snap(state)
    spec = build_ability_spec(state, proxy, seat,
                              {'target_player': 3-seat, 'target_card_id': target}, report_unsupported=False)
    assert snap(state) == before
    assert not spec.used_fallback and spec.effect.key != 'noop'
    if name == "Fertilid's Favor":
        assert spec.effect.key == 'effect_sequence'
        effects = spec.effect.payload['effects']
        assert [part['effect_key'] for part in effects] == ['search_library', 'add_counters']
        assert effects[1]['payload']['target_card_id'] == target
        assert effects[1]['payload']['counter'] == '+1/+1' and effects[1]['payload']['amount'] == 2
        payload = effects[0]['payload']
    else:
        assert spec.effect.key == 'search_library'
        payload = spec.effect.payload
    assert payload['target_player'] == 3-seat
    assert payload['contains'] == 'basic_land' and payload['count'] == 1
    assert payload['destination'] == 'battlefield' and payload['tapped'] and payload['shuffle']


@pytest.mark.parametrize('name', ['Fertilid', "Fertilid's Favor"])
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('find', [False, True])
def test_actual_paid_affected_private_search_find_or_fail_restart_then_compound(name, seat, find, tmp_path):
    state, source, target, lands = setup(name, seat)
    affected = 3-seat
    initial_counters = state.cards[target].counters.get('+1/+1', 0)
    if name == 'Fertilid':
        request = {'type': 'activate_ability', 'card_id': source, 'ability_index': 0,
                   'targets': {'target_player': affected}}
    else:
        request = {'type': 'cast_spell', 'card_id': source, 'cost_choice': {'id': 'base'},
                   'targets': {'target_player': affected, 'target_card_id': target}}
    state = act(state, seat, request)
    assert state.stack[-1].controller == seat and state.stack[-1].source_card_id == source
    if name == 'Fertilid':
        assert state.cards[source].counters['+1/+1'] == 1
    else:
        assert state.stack[-1].payload['mana_spent'] == 4
    state = passes(restart(state, tmp_path, 'paid-stack'))
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'search_library' and pending['player_id'] == affected
    assert pending['min_count'] == 0 and set(lands[affected]) <= set(pending['options'])
    assert not set(lands[seat]).intersection(pending['options'])
    assert state.cards[target].counters.get('+1/+1', 0) == initial_counters
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'choose_mechanic', 'card_ids': [lands[affected][0]]})
    assert snap(state) == before
    state = restart(state, tmp_path, 'private-pending')
    rng = state.rng.getstate()
    state = act(state, affected, {'type': 'choose_mechanic',
                                 'card_ids': [lands[affected][1]] if find else []})
    assert state.rng.getstate() != rng and state.pending_mechanic_choice is None
    assert state.players[seat].library == before['players'][str(seat)]['library']
    if find:
        card = state.cards[lands[affected][1]]
        assert card.zone == Zone.BATTLEFIELD and card.tapped
        assert card.owner == card.controller == affected
    if name == "Fertilid's Favor":
        assert state.cards[target].counters.get('+1/+1', 0) == initial_counters + 2
    assert_private(restart(state, tmp_path, 'completed'))


@pytest.mark.parametrize('seat', [1, 2])
def test_full_canonical_rampant_growth_retains_own_search_control(seat, tmp_path):
    state, source, _, lands = setup('Rampant Growth', seat)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source, 'cost_choice': {'id': 'base'}})
    assert state.stack[-1].payload['mana_spent'] == 2
    state = passes(restart(state, tmp_path, 'rampant-paid'))
    assert state.pending_mechanic_choice['player_id'] == seat
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [lands[seat][1]]})
    assert state.cards[lands[seat][1]].zone == Zone.BATTLEFIELD and state.cards[lands[seat][1]].tapped
    assert_private(restart(state, tmp_path, 'rampant-complete'))


@pytest.mark.parametrize('seat', [1, 2])
def test_full_favor_deliberately_zero_optional_counter_target_no_inferred_creature(seat, tmp_path):
    state, source, target, lands = setup("Fertilid's Favor", seat)
    counters = {cid: dict(card.counters) for cid, card in state.cards.items()}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source, 'cost_choice': {'id': 'base'},
                             'targets': {'target_player': seat}})
    assert state.stack[-1].payload['mana_spent'] == 4
    state = passes(restart(state, tmp_path, 'zero-target-paid'))
    assert state.pending_mechanic_choice['player_id'] == seat
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [lands[seat][1]]})
    assert state.pending_mechanic_choice is None
    assert state.cards[lands[seat][1]].zone == Zone.BATTLEFIELD
    assert {cid: dict(card.counters) for cid, card in state.cards.items()} == counters
    assert_private(restart(state, tmp_path, 'zero-target-complete'))
