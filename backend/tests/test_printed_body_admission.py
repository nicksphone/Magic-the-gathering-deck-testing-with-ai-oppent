"""Complete printed text must be checked before a public or direct cast pays."""
from copy import deepcopy
import pytest
import json
from pathlib import Path
import domain_paid_support as g
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot as snapshot
from rules_engine.engine import RulesEngine
from rules_engine.ability_model import build_spell_spec, spell_resolution_gaps
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.bestow import bestow_cast_view

RULES = RulesEngine()
HERE = Path(__file__).parent


@pytest.fixture
def facts():
    packet = json.loads((HERE / 'fixtures/printed_body_admission/canonical-six.json').read_text())
    rows = {name: data['canonical'] for name, data in packet['cards'].items()}
    for path in (HERE / 'fixtures/archangel_pair').glob('*.json'):
        card = json.loads(path.read_text())
        if card.get('object') == 'card' and card.get('name') == 'Forest':
            rows['Forest'] = card
    assert 'Forest' in rows
    return rows


def add(state, rows, name, seat):
    return g.add(state, rows, name, seat, Zone.HAND)
NAMES = ['Archangel of Wrath', 'Springheart Nantuko', 'Suncleanser',
         'Veil of Summer', 'Volatile Stormdrake']


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', ['\nDraw an unspecified number of cards.',
                                   ' (Draw an unspecified number of cards.)'])
def test_public_and_direct_cast_reject_whole_unknown_body_before_payment(facts, name, seat, tail):
    state = g.position(facts, seat)
    rows = deepcopy(facts)
    rows[name]['oracle_text'] += tail
    source = add(state, rows, name, seat)
    state.players[seat].mana_pool = {'W': 10, 'U': 10, 'B': 10, 'R': 10, 'G': 10, 'C': 10}
    action = {'type': 'cast_spell', 'card_id': source, 'cost_choice': {'id': 'base'}, 'targets': {}}
    before = snapshot(state)
    with pytest.raises(ActionRejected, match='Unsupported spell resolution'):
        checked_action(state, RULES, seat, action)
    assert snapshot(state) == before
    with pytest.raises(ActionRejected, match='Unsupported spell resolution'):
        RULES.take_action(state, seat, action, reject_invalid=True)
    assert snapshot(state) == before
    assert not any(move['type'] == 'cast_spell' and move.get('card_id') == source
                   for move in RULES.legal_moves(state, seat))
    assert snapshot(state) == before


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_complete_contract_does_not_depend_on_catalog_name_or_printed_mana_cost(facts, name, seat):
    state = g.position(facts, seat)
    source = add(state, facts, name, seat)
    card = state.cards[source]
    card.name = 'Independent grammar specimen'
    card.oracle_text = card.oracle_text.replace(name, card.name)
    card.mana_cost = '{7}'
    before = snapshot(state)
    assert spell_resolution_gaps(card) == ()
    assert build_spell_spec(state, card, seat).unsupported_resolution == ()
    if name == 'Springheart Nantuko':
        view = bestow_cast_view(card)
        assert spell_resolution_gaps(view) == ()
        assert build_spell_spec(state, view, seat).unsupported_resolution == ()
    assert snapshot(state) == before


@pytest.mark.parametrize('name', ['Archangel of Wrath', 'Veil of Summer'])
@pytest.mark.parametrize('change', ['nested', 'extra', 'truncated', 'wrong-reminder'])
def test_only_matching_complete_reminder_is_ignored(facts, name, change):
    state = g.position(facts, 1)
    source = add(state, facts, name, 1)
    card = state.cards[source]
    if change == 'nested':
        card.oracle_text = card.oracle_text.replace('(', '(Unspecified (nested) text. ', 1)
    elif change == 'extra':
        card.oracle_text += ' (Unspecified text.)'
    elif change == 'truncated':
        card.oracle_text = card.oracle_text.replace(')', '', 1)
    else:
        card.oracle_text = card.oracle_text.replace('You may pay', 'You must pay').replace('targets of blue', 'targets of green')
    assert spell_resolution_gaps(card)


@pytest.mark.parametrize('name', ['Veil of Summer', 'Volatile Stormdrake'])
def test_supported_body_does_not_require_unrelated_printed_keywords_or_spell_speed(facts, name):
    state = g.position(facts, 1)
    source = add(state, facts, name, 1)
    card = state.cards[source]
    if name == 'Veil of Summer':
        card.types = ['Sorcery']
        card.type_line = 'Sorcery'
    else:
        card.oracle_text = card.oracle_text.split('\n', 1)[1]
        card.keywords = []
    assert spell_resolution_gaps(card) == ()
