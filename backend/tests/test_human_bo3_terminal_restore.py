"""Cold completed-series replay; requires the actual native HTTP certificate."""
import json
import os
from pathlib import Path
import subprocess
import sys
from fastapi.testclient import TestClient
import main
from game_state.serializers import serialize_match_snapshot
from tests.test_api_input_contracts import snapshot


def test_native_completed_series_survives_cold_read_without_sql_mutation():
    root = Path(__file__).resolve().parents[2]
    evidence = Path(os.environ['MTG_HUMAN_BO3_EVIDENCE']) / 'interactive'
    native = json.loads((evidence / 'terminal.json').read_text())
    mid = native['view']['id']
    assert native['view']['match_complete'] and max(native['view']['score'].values()) == 2
    child = subprocess.run([sys.executable, str(Path(__file__).with_name('human_bo3_cold_worker.py')), mid], cwd=root / 'backend',
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, capture_output=True, text=True, timeout=60)
    out = Path(os.environ['MTG_HUMAN_BO3_EVIDENCE']) / 'terminal-restore'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'completed-cold.stderr').write_text(child.stderr)
    assert child.returncode == 0, child.stderr
    read = json.loads(child.stdout)
    assert read['snapshot'] == native['snapshot']
    assert read['view']['match_complete']
    assert read['view']['score'] == native['view']['score']
    assert read['controller']['root_seed'] == 1972639901
    main.ACTIVE_MATCHES.pop(mid, None)
    with TestClient(main.app) as client:
        restored = client.get('/matches/' + mid)
        assert restored.status_code == 200, restored.text
        match = main.ACTIVE_MATCHES[mid]
        assert json.loads(json.dumps(serialize_match_snapshot(match.state))) == native['snapshot']
        assert restored.json()['score'] == native['view']['score']
        before = snapshot(match)
        result = client.post('/matches/' + mid + '/next-game', json={'player_id': 1, 'play_first': True})
        assert result.status_code == 400
        assert snapshot(match) == before
    main.ACTIVE_MATCHES.pop(mid, None)
    (out / 'completed-cold.json').write_text(json.dumps(read))
