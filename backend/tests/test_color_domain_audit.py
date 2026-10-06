"""Canonical color classification audit; ordinary strict assertions, no fixes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.colors import card_color_symbols
from rules_engine.continuous import effective_combat_stats, effective_keywords
from rules_engine.domain import basic_land_type_count
from rules_engine.engine import RulesEngine
from rules_engine.land_types import effective_type_line
from rules_engine.protection import protection_match_reason
from rules_engine.query_context import rule_query_scope
from rules_engine.type_effects import effective_types
from tests.test_ai_recurring_engines import resolve
from tests.test_basic_land_layer_goldens import position


ROOT = Path(__file__).resolve().parents[2]
RECEIPTS = json.loads((Path(__file__).parent / 'fixtures/color_domain_audit/provenance.json').read_text())
CARDS = {entry['row']['name']: entry['row'] for entry in RECEIPTS}
FAMILIES = [('Creakwood Liege', 'Llanowar Elves', 2, 3),
            ('Creakwood Liege', 'Blood Artist', 1, 3),
            ('Angel of Jubilation', 'Blood Artist', 0, 4)]


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    sample = MatchFactory.from_decks([{**CARDS[name], 'card_name': name, 'quantity': 1}], [], seed=83)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    card.summoning_sick = False
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def checked(state, seat, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    return result


def convert(state, cid, seat):
    assert not state.stack and state.active_player == state.priority_player == seat
    song = add(state, 'Song of the Dryads', seat, Zone.HAND)
    state = resolve(checked(state, seat, {'type': 'cast_spell', 'card_id': song.id,
                    'targets': {'target_card_id': cid}}))
    assert state.cards[song.id].attached_to == cid
    assert effective_types(state, cid) == ['Land']
    assert card_color_symbols(state.cards[cid], state) == set()
    assert not state.stack and state.priority_player == seat
    return state


def reanimate(state, cid, seat):
    # Initial source placement is a controlled fixture; activation and resolution
    # are real checked actions, not direct effect inference or a response cast.
    nissa = add(state, 'Nissa, Who Shakes the World', seat)
    state = resolve(checked(state, seat, {'type': 'activate_loyalty', 'card_id': nissa.id,
                    'ability_index': 0, 'targets': {'target_card_id': cid}}))
    assert {'Land', 'Creature'} <= set(effective_types(state, cid))
    assert state.cards[cid].counters['+1/+1'] == 3
    assert card_color_symbols(state.cards[cid], state) == set()
    assert {'haste', 'vigilance'} <= set(effective_keywords(state, cid))
    return state


def conditional_position(seat, source_name, target_name, before_power):
    state = position(seat)
    add(state, source_name, seat)
    target = add(state, target_name, seat)
    assert effective_combat_stats(state, target.id)[0] == before_power
    state = convert(state, target.id, seat)
    return reanimate(state, target.id, seat), target.id


def test_exact_canonical_receipts():
    for entry in RECEIPTS:
        content = (ROOT / entry['source']).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry['source_sha256']
        assert entry['row'] in json.loads(content)
        assert entry['row'].get('oracle_id') or entry['row']['provenance']['oracle_id']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source_name,target_name,before_power,expected', FAMILIES)
@pytest.mark.parametrize('restart', [False, True])
def test_continuous_color_subject_uses_live_color_after_legal_conversion(
        seat, source_name, target_name, before_power, expected, restart):
    state, cid = conditional_position(seat, source_name, target_name, before_power)
    if restart:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    with rule_query_scope(state):
        actual = effective_combat_stats(state, cid)
        assert card_color_symbols(state.cards[cid], state) == set()
    assert serialize_match_snapshot(state) == before
    # Colorless is neither black nor green, and is nonblack. The animated base
    # is 0/0 with three +1/+1 counters; only the nonblack anthem should apply.
    assert actual[0] == expected, (source_name, target_name, actual, expected)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source_name,target_name,quality', [
    ('Kelsien, the Plague', 'Archon of Absolution', 'white'),
    ('Royal Assassin', 'Mystic Enforcer', 'black'),
])
@pytest.mark.parametrize('restart', [False, True])
def test_activated_target_protection_domain_tracks_actual_legal_alteration(
        seat, source_name, target_name, quality, restart):
    state = position(seat)
    source = add(state, source_name, seat)
    target_seat = 3-seat if source_name == 'Kelsien, the Plague' else seat
    target = add(state, target_name, target_seat)
    # Royal's tapped-target precondition is controlled initially; the post-Nissa
    # target is tapped with its real intrinsic Forest mana ability below.
    if source_name == 'Royal Assassin':
        target.tapped = True
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
              'targets': {'target_card_id': target.id}}
    assert protection_match_reason(state, target.id, source) == quality
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    assert target.id not in activation_target_ids(state, seat, source.id)
    # Kelsien targets only opposing creatures. A separate controlled main-phase
    # fixture starts the target controller's legal Song/Nissa sequence; this is
    # not a claim to have played the intervening full turn or cast Song in response.
    if target_seat != seat:
        state.active_player = state.priority_player = target_seat
    state = reanimate(convert(state, target.id, target_seat), target.id, target_seat)
    if target_seat != seat:
        state = checked(state, target_seat, {'type': 'pass_priority'})
        assert state.priority_player == seat
    if source_name == 'Royal Assassin':
        mana = next(move for move in RulesEngine().legal_moves(state, seat)
                    if move['type'] == 'activate_mana_ability' and move['card_id'] == target.id)
        state = checked(state, seat, {'type': 'activate_mana_ability', 'card_id': target.id,
                         'ability_index': mana['ability_index'], 'color': 'G'})
    if restart:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert protection_match_reason(state, target.id, state.cards[source.id]) is None
    assert target.id in activation_target_ids(state, seat, source.id)
    result = resolve(checked(state, seat, action))
    assert result.cards[target.id].zone == (Zone.GRAVEYARD if source_name == 'Royal Assassin' else Zone.BATTLEFIELD)
    if source_name == 'Kelsien, the Plague':
        assert result.cards[target.id].counters['__damage_marked'] == 1


def activation_target_ids(state, seat, cid):
    before = serialize_match_snapshot(state)
    with rule_query_scope(state):
        moves = RulesEngine().legal_moves(state, seat)
        ids = {target['id'] for move in moves
               if move['type'] == 'activate_ability' and move['card_id'] == cid
               for key, values in move['target_hints'].items()
               if key.endswith('_targets') and isinstance(values, list)
               for target in values if isinstance(target, dict) and 'id' in target}
    assert serialize_match_snapshot(state) == before
    return ids


@pytest.mark.parametrize('seat', [1, 2])
def test_domain_counts_live_land_subtypes_not_printed_or_effective_color(seat):
    state = position(seat)
    target = add(state, 'Blood Artist', seat)
    assert basic_land_type_count(state, seat) == 0
    state = convert(state, target.id, seat)
    assert basic_land_type_count(state, seat) == 1
    assert 'Forest' in effective_type_line(state, state.cards[target.id])
    seas = add(state, 'Spreading Seas', seat, Zone.HAND)
    state = resolve(checked(state, seat, {'type': 'cast_spell', 'card_id': seas.id,
                    'targets': {'target_card_id': target.id}}))
    assert state.cards[seas.id].attached_to == target.id
    for candidate in (state, deserialize_match_snapshot(serialize_match_snapshot(state))):
        assert basic_land_type_count(candidate, seat) == 1
        assert 'Island' in effective_type_line(candidate, candidate.cards[target.id])
        assert card_color_symbols(candidate.cards[target.id], candidate) == set()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source_name,target_name,before_power,expected', FAMILIES)
def test_actual_song_removal_refreshes_color_qualified_queries(
        seat, source_name, target_name, before_power, expected):
    state, cid = conditional_position(seat, source_name, target_name, before_power)
    with rule_query_scope(state):
        assert card_color_symbols(state.cards[cid], state) == set()
        assert effective_combat_stats(state, cid)[0] == expected
    song_id = next(card.id for card in state.cards.values()
                   if card.name == 'Song of the Dryads' and card.attached_to == cid)
    naturalize = add(state, 'Naturalize', seat, Zone.HAND)
    state = resolve(checked(state, seat, {'type': 'cast_spell', 'card_id': naturalize.id,
                    'targets': {'target_card_id': song_id}}))
    assert state.cards[song_id].zone == Zone.GRAVEYARD
    for candidate in (state, deserialize_match_snapshot(serialize_match_snapshot(state))):
        before = serialize_match_snapshot(candidate)
        with rule_query_scope(candidate):
            assert card_color_symbols(candidate.cards[cid], candidate) == set(CARDS[target_name]['colors'])
            restored_power = 3 if source_name == 'Angel of Jubilation' else 4
            assert effective_combat_stats(candidate, cid) == (restored_power, restored_power)
        assert serialize_match_snapshot(candidate) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source_name,target_name,before_power,expected', FAMILIES)
def test_current_queries_are_restart_private_info_invariant_not_correctness_certificate(
        seat, source_name, target_name, before_power, expected):
    state, cid = conditional_position(seat, source_name, target_name, before_power)
    hidden = add(state, 'Mystic Enforcer', 3-seat, Zone.HAND)
    unseen = add(state, 'Archon of Absolution', 3-seat, Zone.LIBRARY)
    root = serialize_match_snapshot(state)
    observed = effective_combat_stats(state, cid)
    restored = deserialize_match_snapshot(root)
    alternate = deepcopy(restored)
    for old, name in ((hidden, 'Archon of Absolution'), (unseen, 'Mystic Enforcer')):
        sample = MatchFactory.from_decks([{**CARDS[name], 'card_name': name, 'quantity': 1}], [], seed=83)
        replacement = next(iter(sample.cards.values()))
        replacement.id, replacement.owner, replacement.controller = old.id, old.owner, old.controller
        replacement.move_to_zone(old.zone)
        alternate.cards[old.id] = replacement
    moves = RulesEngine().legal_moves(state, seat)
    expected_view = serialize_match_snapshot(decision_view(state, seat, moves)[0])
    for candidate in (state, restored, alternate):
        before = serialize_match_snapshot(candidate)
        assert effective_combat_stats(candidate, cid) == observed
        view, _ = decision_view(candidate, seat, moves)
        assert serialize_match_snapshot(view) == expected_view
        for private_id in (hidden.id, unseen.id):
            assert view.cards[private_id].ai_unknown
            assert view.cards[private_id].name == '' and view.cards[private_id].oracle_text == ''
        assert serialize_match_snapshot(candidate) == before
    assert serialize_match_snapshot(state) == root


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source_name,target_name,before_power,expected', FAMILIES)
def test_fresh_process_restores_current_classification_without_db_or_root_mutation(
        seat, source_name, target_name, before_power, expected):
    state, cid = conditional_position(seat, source_name, target_name, before_power)
    snapshot = serialize_match_snapshot(state)
    script = '''
import json,sys
def audit(event,args):
    if event in {'sqlite3.connect','socket.connect','socket.bind'}:
        raise AssertionError(event)
sys.addaudithook(audit)
from game_state.serializers import deserialize_match_snapshot,serialize_match_snapshot
from rules_engine.colors import card_color_symbols
from rules_engine.continuous import effective_combat_stats
from rules_engine.domain import basic_land_type_count
from rules_engine.query_context import rule_query_scope
request=json.load(sys.stdin)
state=deserialize_match_snapshot(request['snapshot'])
before=serialize_match_snapshot(state)
cid=request['cid']
with rule_query_scope(state):
    result={'stats':effective_combat_stats(state,cid),
            'colors':sorted(card_color_symbols(state.cards[cid],state)),
            'domain':basic_land_type_count(state,request['seat'])}
assert serialize_match_snapshot(state)==before
print(json.dumps(result))
'''
    result = subprocess.run([sys.executable, '-c', script],
        input=json.dumps({'snapshot': snapshot, 'cid': cid, 'seat': seat}),
        text=True, capture_output=True, check=True, timeout=20, cwd=ROOT)
    assert json.loads(result.stdout) == {
        'stats': list(effective_combat_stats(state, cid)), 'colors': [], 'domain': 1}
    assert serialize_match_snapshot(state) == snapshot
