"""Every remaining normal-capture retag must be truthful before its consumer."""
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
from tests.test_library_fixture_fidelity import assert_printed


CASES = (
    ('top3-AI', 'top_card_choices', 'test_ai_top_three_choice_uses_resolution_time_cards',
     'resolve_effect', 21, 'Forest', {51: 'Tidings', 52: 'Preordain', 53: 'Explore'}),
    ('top6-AI', 'library_search_rules', 'test_ai_topdeck_put_chooses_stronger_creature_at_resolution',
     'resolve_effect', 11, 'Forest', {48: 'Deathbloom Gardener', 50: 'Brindle Boar', 52: 'Wayward Swordtooth'}),
    ('zero-overlimit', 'library_search_rules', 'test_topdeck_put_may_choose_zero_and_rejects_more_than_limit',
     'resolve_effect', 11, 'Forest', dict.fromkeys(range(48, 54), 'Llanowar Elves')),
    ('wrong-type', 'library_search_rules', 'test_library_search_rejects_nonmatching_explicit_selection',
     'build_cast_hints', 11, 'Forest', {53: 'Llanowar Elves'}),
    ('paid-Deluge', 'look_top_select_hand', 'test_paid_memory_deluge_pauses_for_two_cards_and_resumes_after_snapshot',
     'take_action', 17, 'Island', {46: 'Island', 47: 'Negate', 48: 'Counterspell',
                                49: 'Sheoldred, the Apocalypse'}),
)


@pytest.mark.parametrize('label,module,test_name,boundary,seed,basic,targets', CASES,
                         ids=[row[0] for row in CASES])
def test_real_consumer_snapshot_requires_genuine_birth_and_rejects_tampering(
        monkeypatch, label, module, test_name, boundary, seed, basic, targets):
    original = importlib.import_module('tests.test_' + module)
    deck = [{'quantity': 60, 'card_name': basic}]
    baseline = MatchFactory.from_decks(deck, deck, seed=seed)
    canonicalize_basics(baseline)
    baseline.pregame_pending = False
    if module != 'top_card_choices':
        baseline.kept_hands = {1, 2}
    if label == 'paid-Deluge':
        baseline.step = Step.DRAW
        baseline.priority_player = 1
        for _ in range(4):
            cid = baseline.players[1].library.pop()
            baseline.players[1].battlefield.append(cid)
            baseline.cards[cid].zone = Zone.BATTLEFIELD
        spell = canonical_card('Memory Deluge', id='deluge', owner=1,
                               controller=1, zone=Zone.HAND)
        baseline.cards[spell.id] = spell
        baseline.players[1].hand.append(spell.id)

    initialize = sideboard_facts.initialize
    births, observed, resumed = {}, [], []

    def observe_birth(state, inventory):
        result = initialize(state, inventory)
        if len(inventory) == 120:
            births[state.id] = deepcopy(state)
        return result

    def check_capture(state):
        facts = state.sideboard_facts
        assert facts and facts['capture_version'] == 3
        assert len(facts['inventory']) == 120
        assert sideboard_facts.copy_facts(facts, state) == facts
        return facts

    def before_consumer(state):
        facts = check_capture(state)
        assert facts['coverage_ok'] is True and facts['complete'] is False
        birth = births[state.id]
        assert facts['inventory'] == birth.sideboard_facts['inventory']
        assert state.starting_decks == birth.starting_decks
        expected_counts = Counter({basic: 60 - len(targets)}) + Counter(targets.values())
        assert sum((Counter({row['card_name']: row['quantity']})
                    for row in state.starting_decks[1]), Counter()) == expected_counts
        assert sum((Counter({row['card_name']: row['quantity']})
                    for row in state.starting_decks[2]), Counter()) == Counter({basic: 60})
        assert state.rng.getstate() == baseline.rng.getstate()
        assert state.kept_hands == baseline.kept_hands
        for pid in (1, 2):
            assert asdict(state.players[pid]) == asdict(baseline.players[pid])
            assert birth.players[pid].hand == []
            assert birth.players[pid].library == [f'p{pid}-{n:03d}' for n in range(1, 61)]
        if label == 'paid-Deluge':
            assert state.players[1].battlefield == [f'p1-{n:03d}' for n in (53, 52, 51, 50)]
            assert state.players[1].library[-4:] == [f'p1-{n:03d}' for n in (46, 47, 48, 49)]
        expected_names = {f'p1-{position:03d}': name for position, name in targets.items()}
        for cid, binding in facts['inventory'].items():
            name = expected_names.get(cid, basic)
            raw = ranking_raw_card(name) if name in RANKING_NAMES else raw_card(name)
            card = state.cards[cid]
            assert binding == {'owner': card.owner, 'stock_key': name}
            assert_printed(card, raw)
            assert_printed(birth.cards[cid], raw)
            assert birth.cards[cid].zone == Zone.LIBRARY
            if cid in expected_names:
                creature = 'Creature' in card.types
                assert card.summoning_sick is birth.cards[cid].summoning_sick is creature
                assert baseline.cards[cid].summoning_sick is False
                assert {k: v for k, v in asdict(card).items()
                        if k not in PRINTED | {'summoning_sick'}} == {
                            k: v for k, v in asdict(baseline.cards[cid]).items()
                            if k not in PRINTED | {'summoning_sick'}}
            else:
                assert asdict(card) == asdict(baseline.cards[cid])
        restored = deserialize_match_snapshot(serialize_match_snapshot(state))
        assert restored.sideboard_facts == facts and restored.sideboard_facts is not facts
        assert restored.starting_decks == state.starting_decks
        assert restored.rng.getstate() == state.rng.getstate()
        target = next(cid for cid, name in expected_names.items() if name != basic)
        for corruption in ('inventory', 'starting-deck', 'physical-printed-name'):
            broken = deepcopy(state)
            if corruption == 'inventory':
                broken.sideboard_facts['inventory'][target]['stock_key'] = basic
            elif corruption == 'starting-deck':
                row = next(row for row in broken.starting_decks[1]
                           if row['card_name'] == expected_names[target])
                row['card_name'] = basic
            else:
                broken.cards[target].printed_characteristics['name'] = basic
            with pytest.raises(ValueError):
                serialize_match_snapshot(broken)
        observed.append(state.id)

    owner = original.RulesEngine if boundary == 'take_action' else original
    delegate = getattr(owner, boundary)

    def capture(*args, **kwargs):
        state = args[1] if boundary == 'take_action' else args[0]
        if not observed:
            before_consumer(state)
        return delegate(*args, **kwargs)

    snapshot = getattr(original, 'serialize_match_snapshot', None)

    def program_snapshot(state, *args, **kwargs):
        facts = check_capture(state)
        result = snapshot(state, *args, **kwargs)
        assert result['sideboard_facts'] == facts
        resumed.append(state.id)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(sideboard_facts, 'initialize', observe_birth)
        patch.setattr(owner, boundary, capture)
        if label == 'paid-Deluge':
            patch.setattr(original, 'serialize_match_snapshot', program_snapshot)
        getattr(original, test_name)()
    assert len(observed) == 1
    assert len(resumed) == (1 if label == 'paid-Deluge' else 0)
