"""Desired identity/cohort contracts, separate from frozen characterizations."""
from copy import deepcopy
import json
import os
import pickle
from pathlib import Path

import pytest

from ai.agent import AIAgent
from card_data.hydration import hydrate_deck_cards
from decks import selection
from decks.bootstrap import ensure_builtin_decks
from decks.builtin_decks import BUILTIN_DECKS
from decks.service import DeckService
from scripts import regression_matrix_replay as replay
from scripts import overnight_verbose_round_robin as overnight
from tests.test_builtin_metadata_refresh import repo, builtin, rows, seed_cache


TRACE = []


def cohort(repo, candidates, limit=2):
    prepare = getattr(selection, 'prepare_cohort', None)
    if prepare:
        candidates = prepare(candidates, resolve_deck_fn=lambda board: hydrate_deck_cards(repo, board))
    chosen = selection.select_representative_decks(candidates, limit, guess_archetype_fn=lambda _: 'unknown')
    return [{**deck, 'mainboard': hydrate_deck_cards(repo, deck['mainboard'])} for deck in chosen]


@pytest.mark.parametrize('pair', [('Burn', 'Dimir Control'), ('Ramp', 'Tribal')])
def test_latest_builtin_view_and_all_distinct_custom_ids_survive(repo, pair):
    ensure_builtin_decks(repo)
    old = [builtin(repo, name) for name in pair]
    latest = [repo.save_deck(' '+r.name.swapcase()+' ', ' BuIlTiN ', json.loads(r.mainboard_json),
                             json.loads(r.sideboard_json), r.archetype_guess) for r in old]
    custom = repo.save_deck(old[0].name, 'user', json.loads(old[1].mainboard_json), [], 'Midrange')
    ensure_builtin_decks(repo)
    ids = {r.id for r in old+latest+[custom]}
    candidates = [r for r in repo.list_decks() if r.id in ids]
    before = rows(repo)
    result = cohort(repo, candidates, 3)
    assert {d.get('id') for d in result} == {r.id for r in latest+[custom]}
    assert all(d['classification_status'] == 'resolved' for d in result)
    assert all(d['analysis']['confidence'] > 0 for d in result)
    assert rows(repo) == before
    assert cohort(repo, candidates[::-1], 3) == result


@pytest.mark.parametrize('pair', [('Burn', 'Dimir Control'), ('Ramp', 'Tribal')])
def test_same_name_stable_ids_dedup_and_manifest_seed_round_trip(repo, tmp_path, pair):
    ensure_builtin_decks(repo)
    first, other = [builtin(repo, n) for n in pair]
    seed_cache(repo, json.loads(other.mainboard_json))
    imported = DeckService(repo).import_deck_text(first.name, BUILTIN_DECKS[pair[1]], 'user')
    custom = next(r for r in repo.list_decks() if r.id == imported['deck_id'])
    candidates = [custom, first, custom, first]
    before = rows(repo)
    decks = cohort(repo, candidates)
    assert len(decks) == 2 and {d.get('id') for d in decks} == {first.id, custom.id}
    assert decks[0]['name'] == decks[1]['name'] == first.name
    assert decks[0]['identity_key'] != decks[1]['identity_key']
    path = tmp_path / 'same-name.json'
    replay._write_deck_manifest(str(path), decks, {'fixture': 'existing canonical decks'})
    loaded, _ = replay._load_deck_manifest(str(path), 2)
    assert loaded == decks
    assert json.loads(path.read_text())['schema_version'] == 2
    assert list(replay._pair_schedule(*loaded, 2)) == list(replay._pair_schedule(*decks, 2))
    assert rows(repo) == before


@pytest.mark.parametrize('mutation', ['source', 'board'])
def test_conflicting_same_id_is_explicit_not_silent(repo, mutation):
    ensure_builtin_decks(repo)
    original = rows(repo)[builtin(repo, 'Burn').id]
    conflict = deepcopy(original)
    if mutation == 'source':
        conflict['source'] = 'user'
    else:
        conflict['mainboard_json'] = builtin(repo, 'Dimir Control').mainboard_json
    with pytest.raises(ValueError, match='identity'):
        cohort(repo, [original, conflict])


def test_partial_metadata_is_unknown_and_export_never_creates_unrestorable_file(repo, tmp_path, monkeypatch):
    from card_data import hydration
    ensure_builtin_decks(repo)
    candidates = [builtin(repo, n) for n in ['Burn', 'Dimir Control']]
    monkeypatch.setattr(hydration, 'fallback_card_payload', lambda _: None)
    before = rows(repo)
    decks = cohort(repo, candidates)
    assert len(decks) == 2 and all(d['archetype'] == 'unknown' for d in decks)
    assert all(d['classification_status'] == 'unknown' for d in decks)
    assert {d['id']: d['stored_archetype'] for d in decks} == {r.id: r.archetype_guess for r in candidates}
    path = tmp_path / 'partial.json'
    with pytest.raises(ValueError):
        replay._write_deck_manifest(str(path), decks, {})
    assert not path.exists() and rows(repo) == before


def test_manifest_identity_tamper_and_duplicate_rejected_before_write(repo, tmp_path):
    ensure_builtin_decks(repo)
    decks = cohort(repo, [builtin(repo, n) for n in ['Burn', 'Dimir Control']])
    assert all(d.get('identity_key') for d in decks)
    path = tmp_path / 'bad.json'
    changed = deepcopy(decks)
    changed[1]['identity_key'] = changed[0]['identity_key']
    with pytest.raises(ValueError):
        replay._write_deck_manifest(str(path), changed, {})
    with pytest.raises(ValueError):
        replay._write_deck_manifest(str(path), [decks[0], decks[0]], {})
    assert not path.exists()


@pytest.mark.parametrize('pair', [('Burn', 'Dimir Control'), ('Ramp', 'Tribal')])
@pytest.mark.parametrize('consumer', ['matrix', 'overnight'])
def test_actual_consumer_readonly_same_name_identity_and_original_policy(repo, tmp_path, monkeypatch, pair, consumer):
    ensure_builtin_decks(repo)
    first, other = [builtin(repo, n) for n in pair]
    seed_cache(repo, json.loads(other.mainboard_json))
    imported = DeckService(repo).import_deck_text(first.name, BUILTIN_DECKS[pair[1]], 'user')
    custom_id = imported['deck_id']
    before = rows(repo)
    # Use only these real catalog records; production reads, original AI and rules run unchanged.
    original_list = type(repo).list_decks
    monkeypatch.setattr(type(repo), 'list_decks', lambda self: [r for r in original_list(self) if r.id in {first.id, custom_id}])
    module = replay if consumer == 'matrix' else overnight
    monkeypatch.setattr(module, 'engine', repo.session.get_bind())
    attempted_writes = []
    for name in ['init_db', 'ensure_builtin_decks', 'ensure_expansion_top_decks']:
        monkeypatch.setattr(module, name, lambda *a, _name=name: attempted_writes.append(_name))
    constructors, choices = [], []
    actual_init, actual_choose = AIAgent.__init__, AIAgent.choose_action
    def init(self, *a, **k):
        actual_init(self, *a, **k)
        constructors.append({'own': self.archetype, 'opponent': self.opponent_archetype,
                             'profile': deepcopy(self.matchup_profile)})
    def choose(self, state, moves, seat):
        root = pickle.dumps(state, 5)
        picked = actual_choose(self, state, moves, seat)
        assert pickle.dumps(state, 5) == root
        choices.append({'seat': seat, 'action': picked.action, 'reasoning': picked.reasoning, 'root_unchanged': True})
        return picked
    monkeypatch.setattr(AIAgent, '__init__', init)
    monkeypatch.setattr(AIAgent, 'choose_action', choose)
    if consumer == 'matrix':
        output, manifest = tmp_path/'result.json', tmp_path/'inputs.json'
        monkeypatch.setattr('sys.argv', ['matrix', '--output', str(output), '--write-deck-manifest', str(manifest),
                                      '--max-decks', '2', '--matches-per-pair', '1', '--max-ticks', '1'])
        replay.main()
        result = json.loads(output.read_text())
    else:
        output = tmp_path/'overnight'
        monkeypatch.setattr('sys.argv', ['overnight', '--output-dir', str(output), '--sources', 'builtin,user',
                                      '--max-decks', '2', '--matches-per-pair', '1', '--max-ticks', '1'])
        overnight.run()
        result = json.loads(next(output.glob('*/summary.json')).read_text())
    TRACE.append({'consumer': consumer, 'names': pair, 'expected_ids': [first.id, custom_id],
                  'attempted_bootstrap_writes': attempted_writes, 'constructors': constructors,
                  'actual_decisions': choices, 'result': result, 'scope': 'one-tick pregame, not strength'})
    assert not attempted_writes
    assert choices and constructors
    assert len({c['own'] for c in constructors}) == 2
    if consumer == 'matrix':
        loaded, _ = replay._load_deck_manifest(str(manifest), 2)
        assert {d['id'] for d in loaded} == {first.id, custom_id}
        assert result['decks'] == 2 and result['pairs'] == 1 and result['matches'] == 2
        row = result['pair_results'][0]
        assert row['deck_a_identity'] != row['deck_b_identity']
        assert row['deck_a'] == row['deck_b'] == first.name
        assert result['determinism_failures'] == 0
    else:
        assert {d['id'] for d in result['decks']} == {first.id, custom_id}
        row = result['pair_summaries'][0]
        assert row['deck_a_identity'] != row['deck_b_identity']
    assert original_list(repo) and {r.id: r.model_dump(mode='json') for r in original_list(repo)} == before


@pytest.fixture(scope='module', autouse=True)
def trace():
    yield
    path = os.environ.get('MTG_COHORT_CONTRACT_TRACE')
    if path:
        Path(path).write_text(json.dumps({'schema_version': 1, 'cases': TRACE}, indent=2)+'\n')
