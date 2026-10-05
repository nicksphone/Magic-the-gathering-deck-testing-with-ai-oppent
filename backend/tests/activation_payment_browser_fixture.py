"""Canonical payment controls in a disposable loopback-only fixture server."""
from pathlib import Path
import main

if (Path(main.__file__).resolve().parents[1] / '.git').exists():
    raise RuntimeError('Activation-payment fixtures require a disposable backend source copy')

from fastapi import HTTPException
from tests.browser_fixture_server import app, publish
from tests.test_activation_payment_choices import position, activation_card
from tests.test_ai_search_prefix import bare_state


@app.post('/fixture/activation-payment')
def activation_payment(seat: int = 1, kind: str = 'sacrifice'):
    if seat not in (1, 2) or kind not in {'sacrifice', 'discard', 'artifact'}:
        raise HTTPException(422, 'Invalid payment fixture')
    if kind == 'artifact':
        state = bare_state(seat)
        source = activation_card(state, 'trading-post', seat)
        cards = [source, activation_card(state, 'trading-post', seat)]
        state.players[seat].mana_pool = {color: int(color == 'C') for color in 'WUBRGC'}
        index, chosen = 3, source
    else:
        state, source, cards, _ = position(seat, kind)
        index, chosen = 0, cards[0 if kind == 'sacrifice' else 1]
    state.log.append('Canonical activation-payment test position, not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    return {'match': result, 'source_id': source.id, 'source_name': source.name,
            'ability_index': index, 'chosen_id': chosen.id,
            'retained_id': next(card.id for card in cards if card.id != chosen.id)}


@app.post('/fixture/joint-activation-payment')
def joint_activation_payment(seat: int = 1):
    if seat not in (1, 2):
        raise HTTPException(422, 'Invalid seat')
    from tests.test_joint_activation_payment import petal
    state = bare_state(seat)
    source = activation_card(state, 'trading-post', seat)
    chosen, mana_source = petal(state, seat), petal(state, seat)
    state.log.append('Canonical joint-payment test position, not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    return {'match': result, 'source_id': source.id, 'chosen_id': chosen.id,
            'mana_source_id': mana_source.id}


@app.post('/fixture/nested-mana-life')
def nested_mana_life(seat: int = 1, life: int = 5):
    if seat not in (1, 2) or life not in (3, 5):
        raise HTTPException(422, 'Invalid nested-life fixture')
    from tests.test_nested_mana_life import position
    state, source = position(seat, life)
    state.log.append('Canonical nested-life test position, not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    return {'match': result, 'source_id': source.id}
