"""Whole API/policy views normalize without dispatching their private metadata."""
from copy import deepcopy
from uuid import uuid4

import pytest

from tests.test_private_choice_http_restart import server, fixture, choice, stable


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('decline', [False, True])
def test_whole_views_checked_http_restart_and_stale_context(server, family, seat, decline):
    data = fixture(server, family, seat)
    identifier = data['id']
    base = f'/matches/{identifier}'
    endpoint = f'/fixture/private-choice/{identifier}/intent?seat={seat}'
    before = server.audit(identifier)
    status, legal = server.call(base + f'/legal-moves?player_id={seat}')
    assert status == 200
    view = legal['moves'][0]
    action = choice(view, family, decline)
    status, observed = server.call(f'/fixture/private-choice/{identifier}/observe?seat={seat}')
    assert status == 200
    hint = observed['pending_choice']['prompts'][0]['hint']
    for metadata in (view, hint):
        status, result = server.call(endpoint, {**metadata, **action})
        assert status == 200 and result['action'] == action
        assert stable(server.audit(identifier)) == stable(before)
    status, _ = server.call(f'/fixture/private-choice/{identifier}/intent?seat={3-seat}', {**view, **action})
    assert status == 422 and stable(server.audit(identifier)) == stable(before)
    tampered = deepcopy(view)
    tampered['inspected_cards'][0]['unsupported_nested_alias'] = None
    for request in ({**tampered, **action}, {**view, **action, 'effect_payload': None},
                    {**view, 'card_ids': None}, {**view, **action, 'targets': {'card_ids': action['card_ids']}}):
        status, _ = server.call(endpoint, request)
        assert status == 422 and stable(server.audit(identifier)) == stable(before)
    # Nullable siblings remain compatible, but no null-only selection is inferred.
    status, result = server.call(endpoint, {**view, **action, 'choice_id': None, 'damage_assignment': None})
    assert status == 200 and result['action'] == action
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': {**view, **action}})
    assert status == 422 and stable(server.audit(identifier)) == stable(before)
    server.restart()
    assert stable(server.audit(identifier)) == stable(before)
    status, result = server.call(endpoint, {**view, **action})
    assert status == 200 and result['action'] == action
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': result['action']},
                           {'X-Match-Revision': str(before['revision']), 'Idempotency-Key': str(uuid4())})
    assert status == 200
    after = server.audit(identifier)
    assert after['revision'] == before['revision'] + 1
    assert not after['state']['pending_mechanic_choice'] and not after['state']['stack']
    if family == 'officer':
        assert after['state']['players'][str(seat)]['hand'] == ([] if decline else action['card_ids'])
    else:
        source = before['state']['pending_mechanic_choice']['effect_payload']['target_card_id']
        assert (after['state']['cards'][source]['selected_face_index'] or 0) == int(not decline)
        assert after['state']['players'][str(seat)]['library'] == before['state']['players'][str(seat)]['library']
    status, _ = server.call(endpoint, {**view, **action})
    assert status == 422 and stable(server.audit(identifier)) == stable(after)
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': action},
                           {'X-Match-Revision': str(before['revision']), 'Idempotency-Key': str(uuid4())})
    assert status == 409 and stable(server.audit(identifier)) == stable(after)
    server.restart()
    assert stable(server.audit(identifier)) == stable(after)


@pytest.mark.parametrize('seat', [1, 2])
def test_nonfirst_officer_selection_is_not_replaced_by_adapter(server, seat):
    data = fixture(server, 'officer', seat)
    identifier = data['id']
    before = server.audit(identifier)
    _, legal = server.call(f'/matches/{identifier}/legal-moves?player_id={seat}')
    view = legal['moves'][0]
    eligible = [cid for cid in view['options'] if cid != '__none__']
    assert len(eligible) >= 2
    action = {'type': 'choose_mechanic', 'card_ids': [eligible[1]]}
    status, result = server.call(f'/fixture/private-choice/{identifier}/intent?seat={seat}', {**view, **action})
    assert status == 200 and result['action'] == action
    assert stable(server.audit(identifier)) == stable(before)
    status, _ = server.call(f'/matches/{identifier}/action', {'player_id': seat, 'action': result['action']},
                           {'X-Match-Revision': str(before['revision']), 'Idempotency-Key': str(uuid4())})
    assert status == 200
    after = server.audit(identifier)
    assert after['state']['players'][str(seat)]['hand'] == action['card_ids']
    assert eligible[0] in after['state']['players'][str(seat)]['library']
    server.restart()
    assert stable(server.audit(identifier)) == stable(after)
