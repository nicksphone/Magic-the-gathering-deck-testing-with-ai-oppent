"""Canonical life-payment UI setup; disposable loopback test source only."""
from pathlib import Path

import main

if (Path(main.__file__).resolve().parents[1] / '.git').exists():
    raise RuntimeError('Life-lock UI fixtures require a disposable backend source copy')

from fastapi import HTTPException
from rules_engine.keyword_effects import add_keyword_effect
from tests.browser_fixture_server import app, publish
from tests.test_life_conversion import permanent
from tests.test_life_lock_suppression import restriction
from tests.test_life_total_lock import game


@app.post('/fixture/life-lock')
def life_lock(seat: int = 1, suppressed: bool = True):
    if seat not in (1, 2):
        raise HTTPException(422, 'Expected a valid seat')
    state = game()
    state.active_player = state.priority_player = seat
    state.kept_hands = {1, 2}
    lock = permanent(state, 'platinum-emperion', seat)
    source = restriction(state, 'erebos-god-of-the-dead', seat)
    state.players[seat].mana_pool = {color: int(color in 'BC') for color in 'WUBRGC'}
    if suppressed:
        add_keyword_effect(state, lock.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    state.log.append('Canonical life-lock UI fixture; not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    return {'match': result, 'ability_source_id': source.id, 'lock_id': lock.id,
            'hand_count_before': len(state.players[seat].hand)}
