"""The two real consumer snapshots require truthful stock at factory birth."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import importlib

import pytest

from ai import sideboard_facts
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from tests.library_canonical_fixtures import (
    PRINTED, RANKING_NAMES, canonical_card, canonicalize_basics, ranking_raw_card, raw_card,
)
from tests.test_library_fixture_fidelity import SUBJECTS, actual_input, assert_printed, official


SCENES = (
    (13, 21, 'Forest', {51: 'Preordain', 52: 'Divination', 53: 'Explore'}),
    (22, 61, 'Island', {53: 'Forest'}),
)


@pytest.mark.parametrize('index,seed,basic,targets', SCENES, ids=('iteration-13', 'Realmwalker-22'))
def test_actual_consumer_retains_genuine_birth_snapshot_and_tamper_rejection(
        monkeypatch, index, seed, basic, targets):
    deck = [{'quantity': 60, 'card_name': basic}]
    baseline = MatchFactory.from_decks(deck, deck, seed=seed)
    canonicalize_basics(baseline)
    baseline.pregame_pending = False
    baseline.kept_hands = {1, 2}
    if index == 13:
        spell = canonical_card('Expressive Iteration', id='iteration', owner=1,
                               controller=1, zone=Zone.HAND)
        baseline.cards[spell.id] = spell
    else:
        baseline.active_player = baseline.priority_player = 1
        baseline.step = Step.PRECOMBAT_MAIN
        land = baseline.players[1].library.pop()
        baseline.players[1].battlefield.append(land)
        baseline.cards[land].zone = Zone.BATTLEFIELD
        baseline.cards[land].summoning_sick = False
        walker = canonical_card('Realmwalker', id='walker', owner=1, controller=1,
                                zone=Zone.BATTLEFIELD, chosen_creature_type='Elf')
        elf = canonical_card('Llanowar Elves', id='top-elf', owner=1, controller=1,
                             zone=Zone.LIBRARY)
        baseline.cards.update({walker.id: walker, elf.id: elf})
        baseline.players[1].battlefield.append(walker.id)
        baseline.players[1].library.append(elf.id)

    initialize = sideboard_facts.initialize
    births = {}

    def observe_birth(state, inventory):
        result = initialize(state, inventory)
        if len(inventory) == 120:
            births[state.id] = deepcopy(state)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(sideboard_facts, 'initialize', observe_birth)
        state, card = actual_input(monkeypatch, SUBJECTS[index])
    assert_printed(card, official(SUBJECTS[index][3]))
    assert state.cards[card.id] is card
    # A post-birth canonical reprint must not evade the real snapshot stock check.
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert_printed(restored.cards[card.id], official(SUBJECTS[index][3]))
    assert restored.sideboard_facts == state.sideboard_facts
    assert restored.sideboard_facts is not state.sideboard_facts
    assert restored.rng.getstate() == state.rng.getstate() == baseline.rng.getstate()

    birth = births[state.id]
    inventory = state.sideboard_facts['inventory']
    expected_names = {f'p1-{position:03d}': name for position, name in targets.items()}
    assert len(inventory) == len(birth.cards) == 120
    assert inventory == birth.sideboard_facts['inventory']
    assert state.sideboard_facts['capture_version'] == 3
    assert state.sideboard_facts['coverage_ok'] is True
    assert state.sideboard_facts['complete'] is False
    assert state.starting_decks == birth.starting_decks == restored.starting_decks
    assert sum((Counter({r['card_name']: r['quantity']}) for r in state.starting_decks[1]),
               Counter()) == Counter({basic: 60 - len(targets)}) + Counter(targets.values())
    assert sum((Counter({r['card_name']: r['quantity']}) for r in state.starting_decks[2]),
               Counter()) == Counter({basic: 60})
    for pid in (1, 2):
        assert asdict(state.players[pid]) == asdict(baseline.players[pid])
        assert state.players[pid].hand == [f'p{pid}-{n:03d}' for n in range(60, 53, -1)]
        assert birth.players[pid].hand == []
        assert birth.players[pid].library == [f'p{pid}-{n:03d}' for n in range(1, 61)]
    for cid, binding in inventory.items():
        name = expected_names.get(cid, basic)
        raw = ranking_raw_card(name) if name in RANKING_NAMES else raw_card(name)
        assert binding == {'owner': state.cards[cid].owner, 'stock_key': name}
        assert_printed(state.cards[cid], raw)
        assert_printed(birth.cards[cid], raw)
        assert birth.cards[cid].zone == Zone.LIBRARY
        assert state.cards[cid].summoning_sick is baseline.cards[cid].summoning_sick is False
        if cid in expected_names:
            assert {k: v for k, v in asdict(state.cards[cid]).items() if k not in PRINTED} == {
                k: v for k, v in asdict(baseline.cards[cid]).items() if k not in PRINTED}
        else:
            assert asdict(state.cards[cid]) == asdict(baseline.cards[cid])
    assert sideboard_facts.copy_facts(state.sideboard_facts, state) == state.sideboard_facts

    target = next(iter(expected_names))
    for corruption in ('inventory', 'starting-deck', 'physical-printed-name'):
        broken = deepcopy(state)
        if corruption == 'inventory':
            broken.sideboard_facts['inventory'][target]['stock_key'] = basic
        elif corruption == 'starting-deck':
            row = next(r for r in broken.starting_decks[1] if r['card_name'] == expected_names[target])
            row['card_name'] = basic
        else:
            broken.cards[target].printed_characteristics['name'] = basic
        with pytest.raises(ValueError):
            serialize_match_snapshot(broken)

    module, test_name = SUBJECTS[index][:2]
    getattr(importlib.import_module('tests.test_' + module), test_name)()
