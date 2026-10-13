"""Review controls: genuine paid rules episodes and explicit data mutations."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai import sideboard_facts as facts, sideboard_policy as policy
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, draw_card
from knowledge.profiles import derive_profile, merge_profile_payload
from knowledge import profiles
from knowledge.service import snapshot_for
from rules_engine.continuous import effective_types
from rules_engine.engine import RulesEngine
from tests.test_sideboard_finished_transition import RAW, act, settle, episode, metadata
import main


def protocol_row(text):
    # A generic COPY of verified raw data for grammar negatives, NOT an official
    # object or an executed custom spell. No StackItem or fake resolution.
    raw = deepcopy(RAW['Supreme Verdict'])
    raw['name'] = 'Protocol Sweeper'
    raw['oracle_text'] = text
    row = {**raw, 'card_name': raw['name'], 'quantity': 1}
    knowledge = SimpleNamespace(name=raw['name'], scryfall_id=raw['id'],
        oracle_source='scryfall', profiles_json=json.dumps(merge_profile_payload(
            {'card_data': raw, 'rulings_verified': False}, derive_profile(raw))))
    row['knowledge_snapshot'] = snapshot_for(knowledge, raw['name'], row)
    assert row['knowledge_snapshot']
    return row


@pytest.mark.parametrize('text', [
    "UNKNOWN.\nDestroy all creatures.",
    "This spell can't be countered if you control a creature.\nDestroy all creatures.",
    "Target spell can't be countered.\nDestroy all creatures.",
    "Spells you control can't be countered.\nDestroy all creatures.",
    "This spell can't be countered.\nDestroy all creatures. UNKNOWN.",
    "Destroy all creatures.\nUNKNOWN.",
    'Destroy all creatures.\n"UNKNOWN"',
    'Destroy all creatures.\n(UNKNOWN)',
    'Destroy all creatures. (UNKNOWN)',
    'Destroy all creatures if you control a creature.',
])
def test_incoming_whole_body_never_rewards_unknown_or_other_prohibition(text):
    row = protocol_row(text)
    before = deepcopy(row)
    assert policy._profile(row) is None
    assert row == before


@pytest.mark.parametrize('text', [
    "This spell can't be countered.\nDestroy all creatures.",
    "Protocol Sweeper cannot be countered.\nDestroy all creatures.",
    'Destroy all creatures.',
])
def test_existing_complete_self_prohibition_and_sweeper_grammar(text):
    assert policy._profile(protocol_row(text)) is not None


@pytest.mark.parametrize('clause, expected', [
    (" This spell can't be countered. ", True),
    ('Protocol Sweeper CANNOT be countered.', True),
    ("This spell can't be countered if you control a creature.", False),
    ("Target spell can't be countered.", False),
    ("This spell can't be countered. UNKNOWN.", False),
    ("This spell can't be countered.\nDestroy all creatures.", False),
])
def test_positive_self_prohibition_api_keeps_exact_existing_membership(clause, expected):
    assert hasattr(profiles, 'complete_self_counter_prohibition')
    assert profiles.complete_self_counter_prohibition(clause, 'Protocol Sweeper') is expected


@pytest.fixture(scope='module', params=[1, 2])
def earned(request, metadata):
    match = episode(request.param, 60, metadata)
    main._post_step_finalize(match, None)
    return request.param, serialize_match_snapshot(match.state)


def test_same_owner_stock_swap_cannot_relabel_protected_lethal_entry(earned):
    pid, original = earned
    raw = deepcopy(original)
    inv = raw['sideboard_facts']['inventory']
    protected = raw['sideboard_facts']['seats'][str(pid)]['protected']
    used = next(cid for cid in protected if inv[cid]['stock_key'] == 'Lightning Bolt')
    held = next(cid for cid in raw['players'][str(pid)]['hand']
                if inv[cid]['stock_key'] == 'Sheoldred, the Apocalypse')
    inv[used]['stock_key'], inv[held]['stock_key'] = inv[held]['stock_key'], inv[used]['stock_key']
    before = deepcopy(raw)
    with pytest.raises(ValueError):
        deserialize_match_snapshot(raw)
    assert raw == before


@pytest.mark.parametrize('kind', ['missing', 'own_hidden', 'public_noncreature'])
def test_observed_creature_ids_require_retained_public_source(earned, kind):
    pid, original = earned
    raw = deepcopy(original)
    if kind == 'missing':
        cid = 'unrelated-physical-id'
    elif kind == 'own_hidden':
        cid = raw['players'][str(pid)]['hand'][0]
    else:
        cid = next(cid for cid, item in raw['cards'].items()
                   if item['owner'] == pid and item['name'] == 'Lightning Bolt'
                   and item['zone'] == 'graveyard')
    raw['sideboard_facts']['seats'][str(pid)]['observed_creatures'].append(cid)
    before = deepcopy(raw)
    with pytest.raises(ValueError):
        deserialize_match_snapshot(raw)
    assert raw == before


def test_first_real_creature_witness_uses_explicit_new_capture_schema(earned):
    pid, raw = earned
    capture = raw['sideboard_facts']
    assert capture['capture_version'] == 3
    seat = capture['seats'][str(pid)]
    assert set(seat['observed_creature_sources']) == set(seat['observed_creatures'])
    assert len(seat['observed_creatures']) == 6
    for cid, witness in seat['observed_creature_sources'].items():
        assert witness['cid'] == cid
        assert witness['owner'] == witness['controller'] == 3-pid
        assert 'Creature' in witness['effective_types']
        assert witness['zone_change_sequence'] <= raw['cards'][cid]['zone_change_sequence']
        assert raw['card_observations'][str(pid)][cid]['id'] == cid


@pytest.mark.parametrize('mutation', ['future_sequence', 'unknown_type', 'foreign_controller', 'cid_swap'])
def test_invalid_retained_creature_source_witness_is_rejected(earned, mutation):
    pid, original = earned
    raw = deepcopy(original)
    seat = raw['sideboard_facts']['seats'][str(pid)]
    assert 'observed_creature_sources' in seat
    cid = seat['observed_creatures'][0]
    witness = seat['observed_creature_sources'][cid]
    if mutation == 'future_sequence':
        witness['zone_change_sequence'] = raw['cards'][cid]['zone_change_sequence'] + 1
    elif mutation == 'unknown_type':
        witness['effective_types'].append('UnknownType')
    elif mutation == 'foreign_controller':
        witness['controller'] = pid
    else:
        witness['cid'] = seat['observed_creatures'][1]
    before = deepcopy(raw)
    with pytest.raises(ValueError):
        deserialize_match_snapshot(raw)
    assert raw == before


def test_old_capture2_without_historical_witness_remains_playable_unknown(earned):
    pid, original = earned
    raw = deepcopy(original)
    raw['sideboard_facts']['capture_version'] = 2
    for seat in raw['sideboard_facts']['seats'].values():
        seat.pop('observed_creature_sources', None)
    state = deserialize_match_snapshot(raw)
    assert state.winner == original['winner']
    assert state.sideboard_facts['complete'] is False
    assert facts.summary_for(state, pid) == {'qualified': False}


def test_historical_witness_survives_later_control_and_effective_type_change(earned):
    pid, raw = earned
    state = deserialize_match_snapshot(deepcopy(raw))
    assert state.sideboard_facts['capture_version'] == 3
    cid = state.sideboard_facts['seats'][str(pid)]['observed_creatures'][0]
    original = deepcopy(state.sideboard_facts['seats'][str(pid)]['observed_creature_sources'][cid])
    # Trusted existing resolver/static-board seams AFTER genuine paid birth and
    # completion; NOT a claimed paid control spell or natural full-game episode.
    from rules_engine.control_effects import record_control_effect
    from tests.test_basic_land_layer_goldens import setter
    from game_state.observations import observe_cards
    record_control_effect(state, state.cards[cid], pid)
    setter(state, 'Song of the Dryads', pid, state.cards[cid])
    assert state.cards[cid].controller == pid
    assert 'Creature' not in effective_types(state, state.cards[cid])
    observe_cards(state, [cid])
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.sideboard_facts['seats'][str(pid)]['observed_creature_sources'][cid] == original
    assert facts.summary_for(restored, pid)['observed_creature_count'] == 6
    assert facts.summary_for(restored, pid)['own_creature_count'] == 0


@pytest.mark.parametrize('pid', [1, 2])
def test_physical_birth_stock_survives_canonical_face_change(pid, metadata):
    from card_data.hydration import hydrate_deck_cards
    from rules_engine.card_faces import apply_transform_face
    from game_state.observations import observe_cards
    name = 'Delver of Secrets // Insectile Aberration'
    deck = hydrate_deck_cards(metadata, [{'card_name': 'Island', 'quantity': 56},
                                         {'card_name': name, 'quantity': 4}])
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=13)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = pid
    state.players[pid].mana_pool = {'U': 1}
    for _ in range(len(state.players[pid].library)-1):
        draw_card(state, pid)
    move = next(move for move in RulesEngine().legal_moves(state, pid)
                if move['type'] == 'cast_spell'
                and state.sideboard_facts['inventory'][move['card_id']]['stock_key'] == name)
    cid = move['card_id']
    state = act(state, pid, {'type': 'cast_spell', 'card_id': cid})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = settle(state)
    # Existing face-application seam, not a claimed natural upkeep reveal.
    apply_transform_face(state.cards[cid], 1)
    observe_cards(state, [cid])
    assert state.cards[cid].name == RAW[name]['card_faces'][1]['name']
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.sideboard_facts['inventory'][cid]['stock_key'] == name
    assert restored.cards[cid].printed_characteristics['name'] == RAW[name]['card_faces'][0]['name']


def test_existing_unbound_nontoken_source_is_unknown_not_a_token_exception(earned):
    pid, raw = earned
    state = deserialize_match_snapshot(deepcopy(raw))
    cid = state.sideboard_facts['seats'][str(pid)]['observed_creatures'][0]
    from tests.test_basic_land_layer_goldens import setter
    # Explicit source-protocol negative using the existing trusted static-board
    # helper. This is NOT a claimed paid Song or genuine original stock birth.
    source = setter(state, 'Song of the Dryads', pid, state.cards[cid])
    assert source.id not in state.sideboard_facts['inventory'] and not source.is_token
    facts.protect_source(state, source.id)
    assert not state.sideboard_facts['coverage_ok']
    assert not state.sideboard_facts['complete']
    assert not facts.seal_game(state)


def paid_permanent(pid, raw):
    deck = [{**RAW['Mountain'], 'card_name': 'Mountain', 'quantity': 52},
            {**raw, 'card_name': raw['name'], 'quantity': 4},
            {**RAW['Lightning Bolt'], 'card_name': 'Lightning Bolt', 'quantity': 4}]
    game = MatchFactory.from_decks(deck, deepcopy(deck), seed=13)
    game.pregame_pending = False
    game.step = Step.PRECOMBAT_MAIN
    game.active_player = game.priority_player = pid
    game.players[pid].mana_pool = {'C': 10, 'R': 10, 'B': 10}
    game.players[3-pid].life = 3
    for _ in range(len(game.players[pid].library)):
        draw_card(game, pid)
    cid = next(cid for cid in game.players[pid].hand if game.cards[cid].name == raw['name'])
    kind = 'play_land' if 'Land' in game.cards[cid].types else 'cast_spell'
    assert any(move['type'] == kind and move.get('card_id') == cid
               for move in RulesEngine().legal_moves(game, pid))
    game = act(game, pid, {'type': kind, 'card_id': cid})
    return settle(game), cid


def finish(game, pid):
    bolt = next(cid for cid in game.players[pid].hand if game.cards[cid].name == 'Lightning Bolt')
    game = act(game, pid, {'type': 'cast_spell', 'card_id': bolt,
                          'targets': {'target_player': 3-pid}})
    game = settle(game)
    assert game.winner == pid and facts.seal_game(game)
    return game


@pytest.mark.parametrize('pid', [1, 2])
def test_current_own_board_includes_real_paid_canonical_animation(pid):
    directory = Path(__file__).parent / 'fixtures/canonical_land_animation_audit'
    index = json.loads((directory/'provenance.json').read_text())
    entry = next(row for row in index['cards'] if row['name'] == 'Mutavault')
    raw = json.loads((directory/entry['file']).read_text())
    game, cid = paid_permanent(pid, raw)
    assert 'Creature' not in effective_types(game, game.cards[cid])
    move = next(move for move in RulesEngine().legal_moves(game, pid)
                if move['type'] == 'activate_ability' and move.get('card_id') == cid
                and move.get('ability_index') == 1)
    before = serialize_match_snapshot(game)
    mana_before = sum(game.players[pid].mana_pool.values())
    game = act(game, pid, {'type': 'activate_ability', 'card_id': cid, 'ability_index': 1})
    assert sum(game.players[pid].mana_pool.values()) == mana_before - 1
    assert game.stack[-1].source_card_id == cid and game.stack[-1].effect_key != 'noop'
    game = settle(game)
    assert 'Creature' in effective_types(game, game.cards[cid])
    assert before['cards'][cid]['zone'] == 'battlefield'
    game = finish(game, pid)
    assert facts.summary_for(game, pid)['own_creature_count'] == 1
    restored = deserialize_match_snapshot(serialize_match_snapshot(game))
    assert facts.summary_for(restored, pid)['own_creature_count'] == 1


@pytest.mark.parametrize('pid', [1, 2])
def test_current_own_board_excludes_real_paid_canonical_devotion_noncreature(pid):
    rows = json.loads((Path(__file__).parent/'fixtures/conditional_types.json').read_text())
    raw = next(row for row in rows if row['name'] == 'Erebos, God of the Dead')
    game, cid = paid_permanent(pid, raw)
    assert 'Creature' in game.cards[cid].types
    assert 'Creature' not in effective_types(game, game.cards[cid])
    game = finish(game, pid)
    assert facts.summary_for(game, pid)['own_creature_count'] == 0
    assert facts.summary_for(deserialize_match_snapshot(serialize_match_snapshot(game)), pid)['own_creature_count'] == 0
