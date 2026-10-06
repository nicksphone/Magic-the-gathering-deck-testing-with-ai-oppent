"""Standalone source-only media probe; never use an existing database/cache."""
import hashlib
import json
from pathlib import Path
import sys


def run(mode):
    backend = Path(__file__).resolve().parents[1]
    database = backend / 'mtg_lab.db'
    cache = backend / 'card_data/image_cache'
    asset = backend / 'card_data/assets/generic-token-creature.svg'
    assert not database.exists()
    assert not cache.exists()
    original = asset.read_bytes()
    network = []

    def guard(event, args):
        if event in ('socket.connect', 'socket.bind'):
            network.append(event)
            raise AssertionError('No external network')
        if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
            assert Path(str(args[0])).resolve() == database

    sys.addaudithook(guard)
    import main
    from fastapi.testclient import TestClient
    from card_data.token_images import resolve_token_image_uri

    target = cache / asset.name
    assert not database.exists(), 'main import is not SQLite lifespan startup'
    assert target.read_bytes() == original
    result = {'initial_database': 'absent', 'initial_cache': 'absent',
              'asset_sha256': hashlib.sha256(original).hexdigest(),
              'import_created_media': True, 'import_created_database': False}
    uri = resolve_token_image_uri('Phyrexian Golem', 3, 3)
    assert uri == '/card-images/generic-token-creature.svg'
    if mode == 'import_only':
        client = TestClient(main.app)
        try:
            response = client.get(uri)
            assert response.status_code == 200 and response.content == original
            assert not database.exists()
        finally:
            client.close()
        result['http_media_status'] = 200
        result['lifespan_entered'] = False
    else:
        assert mode in {'startup', 'evicted_after_import'}
        if mode == 'evicted_after_import':
            target.unlink()  # Own disposable runtime file, never tracked asset.
        with TestClient(main.app) as client:
            assert database.is_file()
            assert client.get('/health').json()['ok']
            response = client.get(uri)
            expected = 404 if mode == 'evicted_after_import' else 200
            assert response.status_code == expected, response.text
            if expected == 200:
                assert response.content == original
                assert response.headers['content-type'].startswith('image/svg+xml')
            else:
                assert resolve_token_image_uri('Phyrexian Golem', 3, 3) == uri
                assert not target.exists(), 'memoized URI does not reinstall evicted art'
            result['http_media_status'] = expected
            result['lifespan_entered'] = True
            result['startup_created_database'] = True
    assert network == []
    assert asset.read_bytes() == original
    result['network_attempts'] = network
    result['mode'] = mode
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    run(sys.argv[1])
