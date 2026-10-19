"""Captured canonical stock must exist before draws, not be repaired afterward."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict

import pytest

from ai import sideboard_facts
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from tests.library_canonical_fixtures import PRINTED, RANKING_NAMES, ranking_raw_card, raw_card
from tests.test_library_fixture_fidelity import assert_printed
from tests import test_library_search_rules as search


SCENES = (
    ('buried-three', 0, {51: 'Grizzly Bears', 52: 'Grizzly Bears', 53: 'Grizzly Bears'}),
    ('buried-RiP', 1, {53: 'Grizzly Bears'}),
    ('buried-optional', 2, {53: 'Grizzly Bears'}),
    ('explicit-tutor', 0, {48: 'Deathbloom Gardener', 50: 'Brindle Boar',
                           52: 'Wayward Swordtooth'}),
)


@pytest.mark.parametrize('scene,index,targets', SCENES, ids=[row[0] for row in SCENES])
def test_original_scene_has_genuine_birth_capture_and_rejects_stock_tampering(
        monkeypatch, scene, index, targets):
    baseline = search._state_with_searcher()
    initialize, make_state = sideboard_facts.initialize, search._state_with_searcher
    births, setups = {}, []

    def observe_birth(state, inventory):
        result = initialize(state, inventory)
        if len(inventory) == 120:
            births[state.id] = deepcopy(state)
        return result

    def observe_setup(*args, **kwargs):
        state = make_state(*args, **kwargs)
        setups.append(deepcopy(state))
        return state

    with monkeypatch.context() as patch:
        patch.setattr(sideboard_facts, 'initialize', observe_birth)
        patch.setattr(search, '_state_with_searcher', observe_setup)
        if scene == 'explicit-tutor':
            search.test_topdeck_battlefield_tutor_chooses_only_at_resolution()
        else:
            search.test_buried_alive_searches_three_creatures_into_graveyard_with_replacement()

    assert len(setups) == (1 if scene == 'explicit-tutor' else 3)
    state = setups[index]
    birth = births[state.id]
    expected_names = {f'p1-{position:03d}': name for position, name in targets.items()}
    expected_counts = Counter({'Forest': 60 - len(targets)}) + Counter(targets.values())
    assert len(state.cards) == len(birth.cards) == len(state.sideboard_facts['inventory']) == 120
    assert birth.starting_decks == state.starting_decks
    assert sum(
        (Counter({row['card_name']: row['quantity']}) for row in state.starting_decks[1]),
        Counter()) == expected_counts
    assert sum(row['quantity'] for row in state.starting_decks[2]) == 60
    assert {row['card_name'] for row in state.starting_decks[2]} == {'Forest'}

    for pid in (1, 2):
        assert asdict(state.players[pid]) == asdict(baseline.players[pid])
        assert state.players[pid].hand == [f'p{pid}-{position:03d}' for position in range(60, 53, -1)]
        assert state.players[pid].library == [f'p{pid}-{position:03d}' for position in range(1, 54)]
        assert birth.players[pid].hand == []
        assert birth.players[pid].library == [f'p{pid}-{position:03d}' for position in range(1, 61)]
        assert state.sideboard_facts['seats'][str(pid)] == baseline.sideboard_facts['seats'][str(pid)]
    assert state.rng.getstate() == baseline.rng.getstate()
    assert state.pregame_pending is baseline.pregame_pending is False
    assert state.kept_hands == baseline.kept_hands == {1, 2}

    for cid, card in state.cards.items():
        name = expected_names.get(cid, 'Forest')
        raw = ranking_raw_card(name) if name in RANKING_NAMES else raw_card(name)
        assert_printed(card, raw)
        assert_printed(birth.cards[cid], raw)
        assert birth.cards[cid].zone == Zone.LIBRARY
        assert birth.sideboard_facts['inventory'][cid] == {'owner': card.owner, 'stock_key': name}
        if cid in expected_names:
            assert card.summoning_sick is birth.cards[cid].summoning_sick is True
            assert baseline.cards[cid].summoning_sick is False
            assert {key: value for key, value in asdict(card).items()
                    if key not in PRINTED | {'summoning_sick'}} == {
                        key: value for key, value in asdict(baseline.cards[cid]).items()
                        if key not in PRINTED | {'summoning_sick'}}
        else:
            assert asdict(card) == asdict(baseline.cards[cid])

    facts = state.sideboard_facts
    assert facts['capture_version'] == 3 and facts['coverage_ok'] is True
    assert facts['complete'] is False and facts['terminal_winner'] is None
    assert facts['inventory'] == birth.sideboard_facts['inventory']
    assert sideboard_facts.copy_facts(facts, state) == facts
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.sideboard_facts == facts and restored.sideboard_facts is not facts
    assert restored.starting_decks == state.starting_decks
    assert restored.rng.getstate() == state.rng.getstate()

    target = next(iter(expected_names))
    for corruption in ('inventory', 'starting-deck', 'physical-printed-name'):
        broken = deepcopy(state)
        if corruption == 'inventory':
            broken.sideboard_facts['inventory'][target]['stock_key'] = 'Forest'
        elif corruption == 'starting-deck':
            row = next(row for row in broken.starting_decks[1] if row['card_name'] != 'Forest')
            row['card_name'] = 'Forest'
        else:
            broken.cards[target].printed_characteristics['name'] = 'Forest'
        with pytest.raises(ValueError):
            serialize_match_snapshot(broken)
