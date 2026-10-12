"""Actual cold HTTP choice: only the owner epoch changes before explicit selection."""
from uuid import uuid4

import pytest

from tests.test_private_choice_http_restart import (
    assert_restart_audit, fixture, server, stable,
)


from tests.test_private_choice_consumer_http import saved_match_bytes


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
def test_cold_epoch_preserves_saved_match_and_offered_explicit_selection(server, family, seat):
    data = fixture(server, family, seat)
    identifier = data['id']
    base = f'/matches/{identifier}'
    assert (server.root / '.private-choice-owned').read_text() == server.token
    before = server.audit(identifier)
    saved = saved_match_bytes(server, identifier)
    status, legal = server.call(base + f'/legal-moves?player_id={seat}')
    assert status == 200 and len(legal['moves']) == 1
    view = legal['moves'][0]
    assert view['player_id'] == seat
    assert [card['id'] for card in view['inspected_cards']] == data['inspected_ids']
    eligible = [token for token in view['options'] if token != '__none__']
    if family == 'officer':
        assert len(eligible) >= 2
        selected = eligible[1]  # Deliberately choose the offered nonfirst card.
    else:
        assert 'reveal' in eligible
        selected = 'reveal'
    action = {'type': 'choose_mechanic', 'card_ids': [selected]}
    previous = server.proc
    server.restart()
    restored = server.audit(identifier)
    assert_restart_audit(before, restored, previous_pid=previous.pid,
                         current_pid=server.proc.pid, previous_returncode=previous.poll())
    assert saved_match_bytes(server, identifier) == saved
    assert stable(before) != stable(restored)
    assert stable(before, restart=True) == stable(restored, restart=True)
    assert restored['capacity_ledger'] == {
        **before['capacity_ledger'], 'owner_epoch': restored['capacity_owner_epoch'],
    }
    assert stable(server.audit(identifier)) == stable(restored)
    status, normalized = server.call(
        f'/fixture/private-choice/{identifier}/intent?seat={seat}', {**view, **action},
    )
    assert status == 200 and normalized['action'] == action
    assert saved_match_bytes(server, identifier) == saved
    assert stable(server.audit(identifier)) == stable(restored)
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': action},
                           {'X-Match-Revision': str(restored['revision']),
                            'Idempotency-Key': str(uuid4())})
    assert status == 200
    after = server.audit(identifier)
    assert after['revision'] == restored['revision'] + 1
    assert not after['state']['pending_mechanic_choice'] and not after['state']['stack']
    if family == 'officer':
        assert after['state']['players'][str(seat)]['hand'] == [selected]
        assert eligible[0] in after['state']['players'][str(seat)]['library']
    else:
        source = restored['state']['pending_mechanic_choice']['effect_payload']['target_card_id']
        assert after['state']['cards'][source]['selected_face_index'] == 1
        assert after['state']['players'][str(seat)]['library'] == restored['state']['players'][str(seat)]['library']
