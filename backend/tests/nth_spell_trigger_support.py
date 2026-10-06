"""Canonical fixture extension; no invented Oracle or token defaults."""
import json
from pathlib import Path
from tests import readiness_rules_seam_support as original
RAW=json.loads((Path(__file__).parent/'fixtures/nth_spell_triggers/canonical.json').read_text())

def add(state,name,seat,zone=original.Zone.BATTLEFIELD):
    before=original.RAW
    try:
        original.RAW=RAW
        return original.add(state,name,seat,zone)
    finally:
        original.RAW=before
