"""Tests-first custom-deck bridge; authentic rows, no DB or live application."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from api_contracts import DeckPairInput
from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory
from tests.browser_positive83_canonical import raw_card
from training import TrainingEnvironment
from training.dataset import episode_groups, episode_records, model_input
from training.environment import ACTION_PREFIX, VERSION, _deck, _digest, _engine_hash


FRONT_AND_BACK = 'Valki, God of Lies // Tibalt, Cosmic Impostor'
CUSTOM_SOURCE = 'validated_canonical_deck_rows'
ROOT = Path(__file__).resolve().parents[2]


class CanonicalCache:
    """Only the existing local hydration read ABI, backed by pinned official RAW."""

    def __init__(self, names):
        self.rows = {}
        for name in names:
            raw = raw_card(name)
            uri = ScryfallSyncService._extract_remote_image_uri(raw)
            assert uri, 'Selected official fixtures must not need placeholder writes'
            self.rows[name.lower()] = SimpleNamespace(
                **ScryfallSyncService._normalize_payload(raw, uri))

    def get_cached_cards_by_names(self, names):
        return {name.lower(): self.rows[name.lower()] for name in names}


def custom_rows():
    request = DeckPairInput(
        deck_a=[{'card_name': name, 'quantity': quantity} for name, quantity in (
            ('Mountain', 28), ('Forest', 28), ('Grizzly Bears', 2),
            ('Lightning Bolt', 1), ('Lightning Bolt', 1))],
        deck_b=[{'card_name': name, 'quantity': quantity} for name, quantity in (
            ('Island', 28), ('Swamp', 28), (FRONT_AND_BACK, 4))],
    )
    rows = [[entry.model_dump() for entry in entries]
            for entries in (request.deck_a, request.deck_b)]
    cache = CanonicalCache({row['card_name'] for deck in rows for row in deck})
    result = [hydrate_deck_cards(cache, deck) for deck in rows]
    assert all(ready_for_match(row) for deck in result for row in deck)
    return deepcopy(result)


def bridge(environment):
    method = getattr(environment, 'reset_from_decks', None)
    assert callable(method), 'Missing canonical custom-deck reset_from_decks bridge'
    return method


def custom_environment(seed=73):
    environment = TrainingEnvironment()
    reset = bridge(environment)
    decks = custom_rows()
    reset(*decks, seed=seed)
    return environment, decks


def source_inventory():
    return {str(path.relative_to(ROOT)): (
                path.stat().st_mode, sha256(path.read_bytes()).hexdigest())
            for path in ROOT.rglob('*') if path.is_file()
            and not {'.git', '__pycache__', '.pytest_cache'}.intersection(
                path.relative_to(ROOT).parts)}


def assert_private_boundary(value):
    if isinstance(value, dict):
        assert not {'provenance', 'seed', 'rng_state', 'starting_decks',
                    'initial_decks', 'engine_hash', 'deck_hashes',
                    'metadata_source'}.intersection(value)
        for child in value.values():
            assert_private_boundary(child)
    elif isinstance(value, list):
        for child in value:
            assert_private_boundary(child)


@pytest.mark.parametrize('reverse', [False, True])
def test_canonical_custom_rows_and_duplicate_quantities_exist_at_real_birth(monkeypatch, reverse):
    environment = TrainingEnvironment()
    reset = bridge(environment)
    decks = custom_rows()[::(-1 if reverse else 1)]
    original = MatchFactory.from_decks
    births = []

    def retaining_factory(*args, **kwargs):
        supplied = deepcopy(args[:2])
        state = original(*args, **kwargs)
        births.append((supplied, kwargs.copy(), state, deepcopy(state.sideboard_facts)))
        return state

    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(retaining_factory))
    result = reset(*decks, seed=73)
    assert len(births) == 1
    supplied, kwargs, state, facts = births[0]
    assert supplied == tuple(decks)
    assert kwargs['seed'] == 73 and kwargs['game_id'] == state.id
    assert state is environment._state
    assert facts['game_id'] == state.id and facts['coverage_ok'] is True
    assert len(facts['inventory']) == 120 and state.sideboard_facts == facts
    assert state.starting_decks == {1: decks[0], 2: decks[1]}
    for seat, deck in enumerate(decks, 1):
        expected = Counter()
        for row in deck:
            expected[row['card_name']] += row['quantity']
        assert Counter(binding['stock_key'] for binding in facts['inventory'].values()
                       if binding['owner'] == seat) == expected
    valki = next(row for deck in supplied for row in deck
                 if row['card_name'] == FRONT_AND_BACK)
    raw = raw_card(FRONT_AND_BACK)
    assert valki['layout'] == raw['layout'] and len(valki['card_faces']) == 2
    for actual, printed in zip(valki['card_faces'], raw['card_faces']):
        for key in ('name', 'oracle_text', 'mana_cost', 'type_line'):
            assert actual[key] == printed[key]
    assert state.mechanic_choice_players == {1, 2}
    assert state.replacement_choice_required and state.replacement_choice_players == {1, 2}
    assert state.trigger_order_choice_required and state.trigger_order_choice_players == {1, 2}
    assert result == environment.observe(environment.acting_seat)


def test_custom_input_and_returned_rows_are_detached():
    environment, decks = custom_environment()
    before = environment.snapshot()
    decks[0][0]['quantity'] = 1
    decks[1][-1]['card_faces'][0]['colors'].append('R')
    decks[1][-1]['card_data_sources'].append('caller-only-mutant')
    assert environment.snapshot() == before
    exposed = environment.snapshot()
    exposed['state']['starting_decks']['2'][-1]['card_faces'][0]['colors'].clear()
    exposed['provenance']['deck_hashes'][0] = '0' * 64
    assert environment.snapshot() == before


def test_custom_seed_and_seat_order_bind_deterministic_initial_provenance():
    first, decks = custom_environment()
    second, _ = custom_environment()
    assert first.snapshot() == second.snapshot()
    provenance = first.snapshot()['provenance']
    assert provenance['metadata_source'] == CUSTOM_SOURCE
    assert provenance['deck_hashes'] == [_digest(rows) for rows in decks]
    assert first._state.id == _digest(provenance)
    different, _ = custom_environment(seed=74)
    assert different.snapshot() != first.snapshot()
    swapped = TrainingEnvironment()
    bridge(swapped)(decks[1], decks[0], seed=73)
    assert swapped.snapshot()['provenance']['deck_hashes'] == list(reversed(provenance['deck_hashes']))
    assert swapped._state.id != first._state.id


@pytest.mark.parametrize('seat', [1, 2])
def test_custom_both_seat_observations_and_genuine_dataset_rows_stay_private(seat):
    environment, _ = custom_environment()
    provenance = environment.snapshot()['provenance']
    records = list(episode_records(
        environment, lambda _: {'type': 'keep_hand'}, episode='episode-0000',
        groups=episode_groups(73, ['custom-a', 'custom-b'], provenance['deck_hashes']),
        tick_budget=2, origin='scripted'))
    transitions = [row for row in records if row['kind'] == 'transition']
    assert len(transitions) == 2 and {row['input']['seat'] for row in transitions} == {1, 2}
    for row in transitions:
        assert_private_boundary(model_input(row))
    observation, prompts = environment.observe(seat), environment.prompts(seat)
    assert_private_boundary(observation)
    assert_private_boundary(prompts)
    assert 'hand' not in observation['players'][str(3 - seat)]
    assert all('library' not in player for player in observation['players'].values())
    if seat != environment.acting_seat:
        assert prompts == []
    before = environment.snapshot()
    environment.observe(seat)
    environment.prompts(seat)
    assert environment.snapshot() == before
    state = environment._state
    for ids in (state.players[3 - seat].hand,
                state.players[1].library, state.players[2].library):
        a, b = ids[:2]
        one, two = deepcopy(state.cards[a]), deepcopy(state.cards[b])
        one.id, two.id = b, a
        state.cards[a], state.cards[b] = two, one
    state.players[1].library.reverse()
    state.players[2].library.reverse()
    assert environment.observe(seat) == observation
    assert environment.prompts(seat) == prompts


def test_custom_resume_uses_initial_rows_after_real_zone_changes():
    environment, decks = custom_environment()
    initial_hashes = environment.snapshot()['provenance']['deck_hashes']
    environment.step({'type': 'keep_hand'})
    environment.step({'type': 'keep_hand'})
    land = None
    for _ in range(16):
        land = next((row['action'] for row in environment.simple_actions()
                     if row['action']['type'] == 'play_land'), None)
        environment.step(land or {'type': 'pass_priority'})
        if land is not None:
            break
    assert land is not None, 'Genuine custom-deck main-phase land play was not reached'
    saved = environment.snapshot()
    assert saved['provenance']['deck_hashes'] == initial_hashes
    assert saved['state']['starting_decks'] == {'1': decks[0], '2': decks[1]}
    restored = TrainingEnvironment()
    restored.restore(saved)
    assert restored.snapshot() == saved
    assert restored.observe(1) == environment.observe(1)
    assert restored.observe(2) == environment.observe(2)
    action = {'type': 'pass_priority'}
    assert restored.step(action) == environment.step(action)
    assert restored.snapshot() == environment.snapshot()


@pytest.mark.parametrize('invalid', [
    'zero-quantity', 'bool-quantity', 'float-quantity', 'string-quantity',
    'missing-type', 'malformed-oracle', 'nonplayable-layout', 'blank-name',
])
def test_bad_custom_rows_fail_before_factory_and_preserve_existing_episode(monkeypatch, invalid):
    environment = TrainingEnvironment()
    reset = bridge(environment)
    environment.reset(seed=73)
    before = environment.snapshot()
    decks = custom_rows()
    if invalid.endswith('quantity'):
        decks[0][0]['quantity'] = {'zero-quantity': 0, 'bool-quantity': True,
                                 'float-quantity': 28.0, 'string-quantity': '28'}[invalid]
    elif invalid == 'missing-type':
        decks[0][0]['type_line'] = ''
    elif invalid == 'malformed-oracle':
        decks[0][0]['oracle_text'] = []
    elif invalid == 'nonplayable-layout':
        decks[0][0]['layout'] = 'token'
    else:
        decks[0][0]['card_name'] = ' '
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError('Invalid custom rows reached real Factory birth')

    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(forbidden))
    with pytest.raises(ValueError):
        reset(*decks, seed=73)
    assert calls == [] and environment.snapshot() == before


@pytest.mark.parametrize('quantity,sandbox,accepted', [
    (59, False, False), (8, False, False), (8, True, True), (251, True, False),
])
def test_custom_deck_size_boundary_matches_the_public_input_contract(quantity, sandbox, accepted):
    environment = TrainingEnvironment()
    reset = bridge(environment)
    decks = custom_rows()
    decks = [[{**deepcopy(rows[0]), 'quantity': quantity}] for rows in decks]
    request = {key: [{'quantity': row['quantity'], 'card_name': row['card_name']}
                     for row in rows] for key, rows in zip(('deck_a', 'deck_b'), decks)}
    if accepted:
        DeckPairInput(**request, sandbox=sandbox)
        reset(*decks, seed=73, sandbox=sandbox)
        assert len(environment._state.cards) == quantity * 2
    else:
        with pytest.raises(ValueError):
            DeckPairInput(**request, sandbox=sandbox)
        with pytest.raises(ValueError):
            reset(*decks, seed=73, sandbox=sandbox)
        assert environment._state is None and environment._provenance is None


@pytest.mark.parametrize('seed', [False, None, '73', 73.0])
def test_custom_seed_is_strict_and_invalid_reset_is_atomic(seed):
    environment, decks = custom_environment()
    before = environment.snapshot()
    with pytest.raises(ValueError):
        bridge(environment)(*decks, seed=seed)
    assert environment.snapshot() == before


@pytest.mark.parametrize('field', [
    'engine_hash', 'deck_hash', 'seed_type', 'seed_value', 'state_hash', 'initial_content', 'origin',
])
def test_custom_snapshot_tampering_is_rejected_atomically(field):
    custom, _ = custom_environment()
    changed = custom.snapshot()
    if field == 'engine_hash':
        changed['provenance']['engine_hash'] = '0' * 64
    elif field == 'deck_hash':
        changed['provenance']['deck_hashes'][0] = '0' * 64
    elif field == 'seed_type':
        changed['provenance']['seed'] = True
    elif field == 'seed_value':
        changed['provenance']['seed'] += 1
    elif field == 'state_hash':
        changed['state_hash'] = '0' * 64
    elif field == 'origin':
        changed['provenance']['metadata_source'] = 'unrecognized_deck_origin'
    else:
        changed['state']['starting_decks']['1'][0]['quantity'] -= 1
        changed['state_hash'] = _digest(changed['state'])
    existing = TrainingEnvironment()
    existing.reset(seed=73)
    before = existing.snapshot()
    with pytest.raises(ValueError):
        existing.restore(changed)
    assert existing.snapshot() == before


def test_custom_reset_queries_restore_and_invalid_input_do_not_write_the_source_root():
    environment = TrainingEnvironment()
    reset = bridge(environment)
    before = source_inventory()
    decks = custom_rows()
    reset(*decks, seed=73)
    saved = environment.snapshot()
    environment.observe(1)
    environment.observe(2)
    environment.prompts()
    restored = TrainingEnvironment()
    restored.restore(saved)
    invalid = deepcopy(decks)
    invalid[0][0]['quantity'] = True
    with pytest.raises(ValueError):
        bridge(restored)(*invalid, seed=73)
    assert restored.snapshot() == saved
    assert source_inventory() == before


def test_existing_builtin_reset_keeps_its_exact_provenance_and_restore_contract():
    environment = TrainingEnvironment()
    environment.reset('Mono Red Aggro', 'Blue Control', seed=73)
    decks = [_deck('Mono Red Aggro'), _deck('Blue Control')]
    expected = {'version': VERSION, 'action_version': ACTION_PREFIX,
                'seed': 73, 'deck_names': ['Mono Red Aggro', 'Blue Control'],
                'deck_hashes': [_digest(rows) for rows in decks],
                'engine_hash': _engine_hash(),
                'metadata_source': 'card_data/builtin_oracle_seed.json'}
    saved = environment.snapshot()
    assert saved['provenance'] == expected and environment._state.id == _digest(expected)
    restored = TrainingEnvironment()
    restored.restore(saved)
    assert restored.snapshot() == saved
