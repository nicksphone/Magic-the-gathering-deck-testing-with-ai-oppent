"""Exercise the public cold-read boundary before unchanged restart assertions."""
import json
from pathlib import Path
import sys

from tests import library_reorder_restart_worker as original

original_flow = original.reorder_flow


def cold_flow(client, phase, seat, name, root, evidence):
    if phase == 'restore':
        import main

        saved = json.loads((root / 'reorder-expected.json').read_text())
        assert not main.ACTIVE_MATCHES
        response = client.get('/matches/' + saved['id'])
        assert response.status_code == 200, response.text
        assert set(main.ACTIVE_MATCHES) == {saved['id']}
        evidence['cold_http_loaded_only_requested_id'] = True
    original_flow(client, phase, seat, name, root, evidence)


original.reorder_flow = cold_flow

if __name__ == '__main__':
    from tests.spell_admission_safety_restart_worker import run

    run(sys.argv[1], int(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), 'reorder')
