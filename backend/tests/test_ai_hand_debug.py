"""API tests must run in disposable source, never the live database."""
import pytest
from tests.test_api_input_contracts import game, snapshot


@pytest.mark.parametrize('flag', [None, '0', 'false', '2'])
def test_debug_hand_endpoint_requires_explicit_server_opt_in(game, monkeypatch, flag):
    client, match = game
    if flag is None:
        monkeypatch.delenv('MTG_DEBUG_HANDS', raising=False)
    else:
        monkeypatch.setenv('MTG_DEBUG_HANDS', flag)
    before = snapshot(match)
    response = client.get(f'/matches/{match.state.id}/debug/ai-hands')
    assert response.status_code == 403
    assert snapshot(match) == before


@pytest.mark.parametrize('ai_seats', [[1], [2], [1, 2], []])
def test_debug_hands_are_read_only_and_do_not_change_normal_redaction(game, monkeypatch, ai_seats):
    client, match = game
    monkeypatch.setenv('MTG_DEBUG_HANDS', '1')
    match.controllers = {pid: 'ai' if pid in ai_seats else 'human' for pid in (1, 2)}
    before = snapshot(match)
    response = client.get(f'/matches/{match.state.id}/debug/ai-hands')
    assert response.status_code == 200
    debug = response.json()
    assert debug['debug_only'] is True
    assert debug['revision'] == match.revision
    assert debug['game_number'] == match.game_number
    assert set(debug['hands']) == {str(pid) for pid in ai_seats}
    for pid in ai_seats:
        assert [card['id'] for card in debug['hands'][str(pid)]] == match.state.players[pid].hand
        assert all(card['mana_cost'] == '' and card['name'] == 'Island' for card in debug['hands'][str(pid)])
    assert snapshot(match) == before
    normal = client.get(f'/matches/{match.state.id}').json()
    for pid in ai_seats:
        assert normal['players'][str(pid)]['hand'] == []
        assert normal['players'][str(pid)]['hand_count'] == len(match.state.players[pid].hand)
