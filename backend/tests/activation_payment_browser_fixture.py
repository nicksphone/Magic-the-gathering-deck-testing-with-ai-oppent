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
