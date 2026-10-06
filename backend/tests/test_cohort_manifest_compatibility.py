"""Transport identity is explicit; legacy names/seeds are not silently migrated."""
from copy import deepcopy
import json

import pytest

from card_data.hydration import hydrate_deck_cards
from decks.selection import cohort_identity, select_representative_decks
from scripts import regression_matrix_replay as replay
from ai.deck_analysis import analyze_deck
from decks.builtin_decks import BUILTIN_DECKS
from decks.parser import DeckParser
from tests.test_deck_bootstrap import _FakeRepo
from tests.test_builtin_metadata_refresh import repo, builtin, rows


def legacy_decks():
    board = hydrate_deck_cards(None, [{'quantity': 60, 'card_name': 'Island'}])
    return [{'name': name, 'mainboard': deepcopy(board)} for name in ['First', 'Second']]


@pytest.mark.parametrize('extra', [False, True])
def test_v1_roundtrip_and_exact_legacy_seed_even_with_extra_metadata(tmp_path, extra):
    decks = legacy_decks()
    if extra:
        for i, deck in enumerate(decks):
            deck.update(id=str(i+1), source='old-freeform', note='not admitted identity metadata')
    path = tmp_path/'v1.json'
    replay._write_deck_manifest(str(path), decks, {'legacy': True})
    assert json.loads(path.read_text())['schema_version'] == 1
    loaded, _ = replay._load_deck_manifest(str(path), 2)
    assert loaded == decks
    for index, forward in enumerate(list(replay._pair_schedule(*loaded, 3))[::2]):
        assert forward[0] == replay._stable_seed('First', 'Second', index)


def test_legacy_duplicate_names_rejected_before_file_creation(tmp_path):
    decks = legacy_decks()
    decks[1]['name'] = decks[0]['name']
    path = tmp_path/'duplicate.json'
    with pytest.raises(ValueError, match='unique'):
        replay._write_deck_manifest(str(path), decks, {})
    assert not path.exists()


def test_id_only_records_remain_distinct_without_inventing_source_or_names(tmp_path):
    rows = [{'id': i, 'name': 'Burn', 'archetype_guess': 'unknown',
             'mainboard': legacy_decks()[0]['mainboard']} for i in [11, 22]]
    decks = select_representative_decks(rows, 2, guess_archetype_fn=lambda _: 'unknown')
    assert len(decks) == 2 and {d['id'] for d in decks} == {11, 22}
    assert {d['source'] for d in decks} == {''}
    assert {d['name'] for d in decks} == {'Burn'}
    path = tmp_path/'identified.json'
    replay._write_deck_manifest(str(path), decks, {})
    assert replay._load_deck_manifest(str(path), 2)[0] == decks


@pytest.mark.parametrize('kind', ['identity', 'duplicate', 'boolean_id', 'source', 'unselected', 'hash'])
def test_v2_all_identities_and_hash_validated_before_subset(tmp_path, kind):
    decks = legacy_decks()
    decks.append(deepcopy(decks[0]))
    for i, deck in enumerate(decks):
        deck.update(id=i+1, source='user')
        deck['identity_key'] = cohort_identity(deck)
    path = tmp_path/'v2.json'
    replay._write_deck_manifest(str(path), decks, {})
    data = json.loads(path.read_text())
    if kind == 'identity':
        data['decks'][0]['identity_key'] = 'forged'
    elif kind == 'duplicate':
        data['decks'][1] = deepcopy(data['decks'][0])
    elif kind == 'boolean_id':
        data['decks'][0]['id'] = True
    elif kind == 'source':
        data['decks'][0]['source'] = False
    elif kind == 'unselected':
        data['decks'][2]['identity_key'] = 'forged'
    else:
        data['decks'][0]['mainboard'][0]['oracle_text'] = 'not the pinned canonical fact'
    if kind != 'hash':
        data['corpus_sha256'] = replay._corpus_hash(data['decks'])
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        replay._load_deck_manifest(str(path), 2)


def test_identity_seed_survives_export_and_distinguishes_same_name_records(tmp_path):
    decks = legacy_decks()
    for i, deck in enumerate(decks):
        deck.update(name='Burn', id=i+1, source='user')
        deck['identity_key'] = cohort_identity(deck)
    other = deepcopy(decks[1]); other['id'] = 3; other['identity_key'] = cohort_identity(other)
    first = list(replay._pair_schedule(*decks, 1))
    assert first[0][0] == first[1][0]
    assert first[0][0] != list(replay._pair_schedule(decks[0], other, 1))[0][0]
    path = tmp_path/'ids.json'
    replay._write_deck_manifest(str(path), decks, {})
    loaded, _ = replay._load_deck_manifest(str(path), 2)
    assert list(replay._pair_schedule(*loaded, 1)) == first


def test_source_only_identity_and_legacy_priority_floor_are_compatible():
    candidates = []
    for source, canonical_name in [('user', 'Dimir Control'), ('file', 'Burn')]:
        parsed = DeckParser(_FakeRepo()).parse(BUILTIN_DECKS[canonical_name])
        assert not parsed.errors
        board = hydrate_deck_cards(None, parsed.mainboard)
        candidates.append({'name': 'Burn', 'source': source,
                           'archetype_guess': analyze_deck(board)['primary_archetype'], 'mainboard': board})
    selected = select_representative_decks(candidates, 1, guess_archetype_fn=lambda _: 'unknown')
    assert [d['archetype'] for d in selected] == ['Burn', 'Control']
    assert len({d['identity_key'] for d in selected}) == 2


@pytest.mark.parametrize('source', [None, 'user'])
def test_conflicting_unidentified_inventories_fail_instead_of_collapsing(source):
    candidates = [{'name': 'Burn', 'mainboard': hydrate_deck_cards(None, [{'name': land, 'quantity': 60}])}
                  for land in ['Island', 'Mountain']]
    if source is not None:
        for row in candidates:
            row['source'] = source
    before = deepcopy(candidates)
    with pytest.raises(ValueError, match='Ambiguous cohort identity'):
        select_representative_decks(candidates, 2, guess_archetype_fn=lambda _: 'unknown')
    assert candidates == before


def test_partial_repository_cannot_execute_or_export(repo, tmp_path, monkeypatch):
    from decks.bootstrap import ensure_builtin_decks
    from card_data import hydration
    ensure_builtin_decks(repo)
    ids = {builtin(repo, n).id for n in ['Burn', 'Dimir Control']}
    before = rows(repo)
    original = type(repo).list_decks
    monkeypatch.setattr(type(repo), 'list_decks', lambda self: [r for r in original(self) if r.id in ids])
    monkeypatch.setattr(replay, 'engine', repo.session.get_bind())
    monkeypatch.setattr(hydration, 'fallback_card_payload', lambda _: None)
    for name in ['init_db', 'ensure_builtin_decks', 'ensure_expansion_top_decks', 'run_match']:
        monkeypatch.setattr(replay, name, lambda *a: pytest.fail('partial input initialized or executed'))
    output, export = tmp_path/'output.json', tmp_path/'inputs.json'
    monkeypatch.setattr('sys.argv', ['matrix', '--output', str(output), '--write-deck-manifest', str(export)])
    with pytest.raises(SystemExit) as error:
        replay.main()
    assert error.value.code == 2 and not output.exists() and not export.exists()
    assert {r.id: r.model_dump(mode='json') for r in original(repo)} == before
