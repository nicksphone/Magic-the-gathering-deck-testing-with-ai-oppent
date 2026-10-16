"""Three review reproductions; legacy records and suppression are explicit protocols."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.attached_token_payment import copiable_lki
from rules_engine.copiable_values import values
from rules_engine.counter_placement import put_counters
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import cast_vaults, choose, place, snapshot
from tests.test_entry_copy_native_936 import cast, position, raw


def coated_walker(seat):
    names = ['Sculpting Steel', 'Liquimetal Coating', 'Disenchant',
             'Teferi, Hero of Dominaria']
    state = position(names, names, seat)
    state, walker = cast(state, seat, 'Teferi, Hero of Dominaria')
    assert resolve_top_of_stack(state)
    assert state.cards[walker].printed_characteristics['loyalty'] == 4
    put_counters(state, 'loyalty', 3, target_card_id=walker)
    coating = place(state, 'Liquimetal Coating', Zone.BATTLEFIELD, seat)
    state.active_player = state.priority_player = seat
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': coating, 'ability_index': 0, 'targets': {'target_card_id': walker}})
    assert resolve_top_of_stack(state)
    assert state.cards[walker].loyalty == 7 and 'Artifact' in state.cards[walker].types
    return state, walker


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('record', ['null', 'missing', 'adequate'])
def test_snapshot_absence_is_unavailable_not_live_fields_as_new_birth(seat, record):
    state, walker = coated_walker(seat)
    saved = serialize_match_snapshot(state)
    if record == 'null':
        saved['cards'][walker]['characteristic_record'] = None
    elif record == 'missing':
        del saved['cards'][walker]['characteristic_record']
    state = deserialize_match_snapshot(saved)
    assert state.cards[walker].loyalty == 7 and 'Artifact' in state.cards[walker].types
    caster = 3-seat
    state, steel = cast(state, caster, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    assert walker in state.pending_mechanic_choice['options']
    before = serialize_match_snapshot(state)
    if record != 'adequate':
        with pytest.raises(ActionRejected):
            choose(state, caster, walker)
        assert serialize_match_snapshot(state) == before
        with pytest.raises(ActionRejected):
            values(state.cards[walker])
        assert copiable_lki(state, state.cards[walker])['descriptor'] is None
    else:
        state = choose(snapshot(state), caster, walker)
        assert state.cards[steel].loyalty == 4
        assert 'Artifact' not in state.cards[steel].types
        assert values(state.cards[walker])['loyalty'] == 4
        assert values(state.cards[walker])['types'] == ['Planeswalker']
        assert state.cards[walker].loyalty == 7
        assert saved['cards'][walker]['characteristic_record']['values']['loyalty'] == 4


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('record', ['empty_physical', 'null_physical', 'adequate'])
def test_ordinary_paid_departure_keeps_inadequate_copy_metadata_unavailable(seat, record):
    state, walker = coated_walker(seat)
    saved = serialize_match_snapshot(state)
    if record != 'adequate':
        saved['cards'][walker]['characteristic_record'] = {
            'version': 1, 'physical': {} if record == 'empty_physical' else None, 'values': {}}
    state = deserialize_match_snapshot(saved)
    retained = deepcopy(state.cards[walker].characteristic_record)
    assert state.cards[walker].printed_characteristics
    if record != 'adequate':
        assert copiable_lki(state, state.cards[walker])['descriptor'] is None
    state, spell = cast(state, seat, 'Disenchant', target_card_id=walker)
    assert resolve_top_of_stack(state)
    assert state.cards[spell].zone == state.cards[walker].zone == Zone.GRAVEYARD
    assert walker in state.players[seat].graveyard
    assert state.cards[walker].owner == seat
    assert state.sideboard_facts['inventory'][walker]['stock_key'] == 'Teferi, Hero of Dominaria'
    state = snapshot(state)
    if record != 'adequate':
        assert state.cards[walker].characteristic_record == retained
        with pytest.raises(ActionRejected):
            values(state.cards[walker])
    else:
        assert values(state.cards[walker])['loyalty'] == 4
        assert values(state.cards[walker])['types'] == ['Planeswalker']
    assert state.cards[walker].name == 'Teferi, Hero of Dominaria'


PROTOCOL = 'Noncanonical Controller-Suppression Protocol'
TIBALT = 'Valki, God of Lies // Tibalt, Cosmic Impostor'


def controller_position(seat):
    path = Path(__file__).parent / 'fixtures/modal_spell_faces.json'
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == 'b42872610ae3f6c5a29974b23deb8f033cd86cc0c285e34a2bfa08d969432081'
    tibalt = json.loads(data)[TIBALT]
    # Declared noncanonical static-grammar witness, born before normal stock capture.
    protocol = {'name': PROTOCOL, 'type_line': 'Enchantment', 'mana_cost': '{1}',
                'oracle_text': 'Creatures you control lose all abilities.', 'colors': []}
    def deck():
        counts = Counter(['Sculpting Steel', 'Triskelion', 'Open the Vaults', TIBALT, PROTOCOL])
        counts['Island'] = 60 - sum(counts.values())
        return [{**(protocol if name == PROTOCOL else tibalt if name == TIBALT else raw(name)),
                 'card_name': name, 'quantity': count} for name, count in counts.items()]
    state = MatchFactory.from_decks(deck(), deck(), seed=991)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    return state


def foreign_paid_steel(state, caster):
    owner = 3-caster
    source = place(state, 'Valki, God of Lies', Zone.HAND, caster)
    state.players[caster].mana_pool = dict(C=30, W=10, U=10, B=10, R=10, G=10)
    state = checked_action(state, RulesEngine(), caster, {'type': 'cast_spell',
        'card_id': source, 'selected_face_index': 1})
    assert resolve_top_of_stack(state)
    steel = place(state, 'Sculpting Steel', Zone.LIBRARY, owner)
    state.priority_player = caster
    state = checked_action(state, RulesEngine(), caster, {'type': 'activate_loyalty',
        'card_id': source, 'ability_index': 0})
    assert resolve_top_of_stack(state)
    from rules_engine.card_faces import exile_permission
    assert state.cards[steel].zone == Zone.EXILE and exile_permission(state, caster, steel)
    state.active_player = state.priority_player = caster
    before = sum(state.players[caster].mana_pool.values())
    state = checked_action(snapshot(state), RulesEngine(), caster, {'type': 'cast_spell',
        'card_id': steel, 'from_exile': True})
    assert sum(state.players[caster].mana_pool.values()) == before-3
    frame = deepcopy(state.stack[-1])
    assert frame.source_card_id == steel and frame.controller == caster
    assert state.cards[steel].owner == owner and state.cards[steel].controller == caster
    return state, steel


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suppressed', [False, True])
@pytest.mark.parametrize('route', ['foreign_spell', 'vaults_owner_default'])
def test_entry_counter_seed_uses_future_controller_without_rewriting_owner(seat, suppressed, route):
    state = controller_position(seat)
    target = place(state, 'Triskelion', Zone.BATTLEFIELD, 3-seat)
    # The spell recipient is opponent-owned; Vaults must still use its own owner.
    owner = 3-seat if route == 'foreign_spell' else seat
    if route == 'foreign_spell':
        state, steel = foreign_paid_steel(state, seat)
    else:
        steel = place(state, 'Sculpting Steel', Zone.GRAVEYARD, seat)
        state, _ = cast_vaults(state, seat)
    place(state, PROTOCOL, Zone.BATTLEFIELD, seat if suppressed else 3-seat)
    stock = deepcopy(state.sideboard_facts['inventory'][steel])
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['player_id'] == seat
    state = choose(snapshot(state), seat, target)
    assert not state.pending_mechanic_choice and not state.pending_replacement_choice
    assert state.cards[steel].zone == Zone.BATTLEFIELD and state.cards[steel].controller == seat
    assert state.cards[steel].owner == owner
    assert state.cards[steel].counters.get('+1/+1', 0) == (0 if suppressed else 3)
    assert state.cards[steel].oracle_text == raw('Triskelion')['oracle_text']
    assert state.cards[steel].characteristic_record['physical']['name'] == 'Sculpting Steel'
    assert snapshot(state).sideboard_facts['inventory'][steel] == stock
