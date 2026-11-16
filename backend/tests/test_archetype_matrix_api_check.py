"""Declared boundary handler/SQLite parity, not HTTP transport acceptance."""
import importlib
import importlib.util


def test_real_handler_saved_roundtrip_and_original_key_retry(tmp_path):
    name = 'scripts.archetype_matrix_api_check'
    assert importlib.util.find_spec(name) is not None, 'Boundary handler check is missing'
    from card_data.seed_cards import seed_card_payload
    from scripts.archetype_matrix_game import play_game
    rows = [{**seed_card_payload('Island'), 'card_name': 'Island', 'quantity': 60}]
    records = []
    # One real master decision, a unit limit and a non-pilot seed.
    play_game(rows, rows, seed=9936, game_id='unit-handler',
              policy={'max_ticks': 1, 'max_turns': 100}, emit=records.append)
    module = importlib.import_module(name)
    with module.HandlerChecks(tmp_path / 'boundary.db') as check:
        report = check(records[0], records[1])
    assert report['step'] == 0 and report['transition_equal'] is True
    assert report['sqlite_roundtrip'] is True and report['original_key_retry'] is True
    assert report['transport'] == 'direct_handler'
    assert report['continuous_api_game'] is False
