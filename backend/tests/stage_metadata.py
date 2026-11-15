"""Optional literal-stage receipts for explicitly configured test instrumentation."""
import json
import os
from pathlib import Path


def mark(stage):
    output = os.environ.get('MTG_TEST_STAGE_METADATA_DIR')
    if not output:
        return
    if type(stage) is not str:
        raise TypeError('A literal stage string is required')
    (Path(output) / 'CONTROL.json').write_text(json.dumps({
        'stage': stage, 'literal_stage_metadata_only': True,
    }))
