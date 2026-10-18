"""Seeded HTTP testpilot certificate; no injected wins or gameplay state edits."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fastapi.testclient import TestClient
from ai.agent import AIAgent
from ai.action_contract import complete_action
from game_state.serializers import serialize_match_snapshot
import main
from sqlmodel import Session
from persistence.db import engine
from persistence.repository import Repository
from card_data.sync import ScryfallSyncService
from tests.test_api_input_contracts import snapshot
from tests.ci_input_contracts import human_bo3_decks


from tests.human_bo3_series_fixture import native_human_bo3_series


def test_seeded_human_bo3_checked_http_cold_restart(native_human_bo3_series):
    native_human_bo3_series()
