"""Actual source-only subprocess startup and canonical token HTTP media."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest
from tests.test_api_input_contracts import game

ARCHIVE = Path('/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/entry-current-20261006/published-source.tar')
ARCHIVE_SHA = '05d5d42fb89efce8c7dd2c77ab6cfc51c78861b3ee1484de8236131bc71bd7f1'


@pytest.mark.parametrize('mode', ['import_only', 'startup', 'evicted_after_import'])
def test_fresh_source_subprocess_media_and_lifespan_semantics(tmp_path, mode):
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == ARCHIVE_SHA
    source = tmp_path / 'source'
    source.mkdir()
    with tarfile.open(ARCHIVE) as archive:
        archive.extractall(source, filter='data')
    backend = source / 'backend'
    probe = Path(__file__).with_name('release_media_packaging_probe.py')
    destination = backend / 'tests' / probe.name
    destination.write_bytes(probe.read_bytes())
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(backend)}
    result = subprocess.run([sys.executable, str(destination), mode], cwd=backend,
                            env=env, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(result.stdout.splitlines()[-1])
    assert record['initial_database'] == record['initial_cache'] == 'absent'
    assert record['network_attempts'] == []
    assert record['http_media_status'] == (404 if mode == 'evicted_after_import' else 200)
    evidence = os.environ.get('MTG_RELEASE_MEDIA_EVIDENCE')
    if evidence:
        out = Path(evidence)
        out.mkdir(exist_ok=True)
        (out / (mode + '.json')).write_text(json.dumps(record, indent=2) + '\n')


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_blade_splicer_paid_http_token_serves_tracked_fallback_after_restore(game, seat):
    import main
    from game_state.state import Zone
    from game_state.serializers import serialize_match_snapshot
    from rules_engine.continuous import effective_keywords
    from tests.test_canonical_token_descriptors import cards
    from tests.test_api_input_contracts import persist, snapshot
    from tests.test_selected_mana_http import restart

    client, controller = game
    state = cards.position(seat)
    source = cards.add(state, 'Blade Splicer', seat, Zone.HAND)
    state.players[seat].mana_pool = {'W': 1, 'C': 2}
    state.id = controller.state.id
    controller.state = state
    controller.controllers = {1: 'human', 2: 'human'}
    persist(controller)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat,
                           'action': {'type': 'cast_spell', 'card_id': source.id}})
    assert response.status_code == 200, response.text
    controller = restart(state.id)
    while controller.state.stack:
        response = client.post(f'/matches/{state.id}/action', json={'player_id': controller.state.priority_player,
                               'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
        controller = main.ACTIVE_MATCHES[state.id]
    controller = restart(state.id)
    assert controller.state.cards[source.id].zone == Zone.BATTLEFIELD
    tokens = [card for card in controller.state.cards.values() if card.is_token and card.zone == Zone.BATTLEFIELD]
    assert len(tokens) == 1
    token = tokens[0]
    assert token.name == 'Phyrexian Golem'
    assert set(token.types) == {'Artifact', 'Creature', 'Token'}
    assert token.colors == [] and token.power == token.toughness == 3
    assert token.keywords == []
    assert effective_keywords(controller.state, token.id) == ['first strike']
    assert token.image_uri == '/card-images/generic-token-creature.svg'
    before = snapshot(controller)
    image = client.get(token.image_uri)
    asset = Path(__file__).parents[1] / 'card_data/assets/generic-token-creature.svg'
    assert image.status_code == 200 and image.content == asset.read_bytes()
    assert image.headers['content-type'].startswith('image/svg+xml')
    assert snapshot(controller) == before
    assert serialize_match_snapshot(restart(state.id).state) == serialize_match_snapshot(controller.state)
