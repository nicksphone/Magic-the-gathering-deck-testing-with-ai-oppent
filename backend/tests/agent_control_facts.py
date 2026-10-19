"""Pinned full canonical control facts; no production or gameplay fixtures."""
import hashlib
import json
from pathlib import Path

DATA = (Path(__file__).parent / 'fixtures/agent_self_entry/facts.json').read_bytes()
assert hashlib.sha256(DATA).hexdigest() == '27c507f0e9aafc8fc68d3d8c7267833223031eaaf6e690fbbe63a582af5ff2e3'
ROWS = {row['name']: row for row in json.loads(DATA)}
