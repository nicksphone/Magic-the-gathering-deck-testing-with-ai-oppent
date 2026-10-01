"""Canonical printed/conditional ward, not certification of whole cards."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.ward import ward_instances, printed_ward_costs
from tests.test_ai_recurring_engines import add as add_card
from tests.test_restricted_mana import clean
from tests.test_ward_resolution import add, resolve, choose


ROWS = {r['name']: r for r in json.loads((Path(__file__).parent / 'fixtures' / 'ward_forms.json').read_text())}
for row in ROWS.values():
    for field in ('power', 'toughness', 'keywords', 'colors'):
        row.setdefault(field, None)


def target(state, name, player):
    card = add_card(state, name, player, cards=ROWS)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


@pytest.mark.parametrize('name,cost', [('Rith, Liberated Primeval', '{2}'),
    ('Voja, Jaws of the Conclave', '{3}'), ('Colossal Skyturtle', '{2}'),
    ('Sauron, the Dark Lord', 'sacrifice a legendary artifact or legendary creature')])
def test_printed_keyword_lists(name, cost):
    state = clean()
    card = target(state, name, 2)
    assert [c.lower() for c in printed_ward_costs(card)] == [cost.lower()]
    assert [c.lower() for c in ward_instances(state, card)] == [cost.lower()]


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name,cost', [('Rith, Liberated Primeval', 2), ('Iymrith, Desert Doom', 4)])
def test_real_cast_triggers_payment_and_survives_snapshot(player, name, cost):
    state = clean(player)
    card = target(state, name, 3-player)
    bolt = add(state, 'Lightning Bolt', player, Zone.HAND)
    state.players[player].mana_pool.update(R=1, C=cost)
    state = checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': bolt.id,
                          'targets': {'target_card_id': card.id}})
    assert len(state.stack) == 2 and state.stack[-1].effect_key == 'ward_payment'
    # Losing the conditional grant after triggering does not remove the trigger.
    state.cards[card.id].tapped = True
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve(state)
    assert state.pending_mechanic_choice['ward_cost'] == {'kind': 'mana', 'cost': '{'+str(cost)+'}'}
    state = choose(state, ['pay'], player)
    resolve(state)
    assert not state.stack and state.cards[card.id].zone == Zone.BATTLEFIELD


def test_conditional_self_ward_tracks_current_tap_state_and_incarnation():
    state = clean()
    card = target(state, 'Iymrith, Desert Doom', 2)
    assert ward_instances(state, card) == ['{4}']
    card.tapped = True
    assert ward_instances(state, card) == []
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert ward_instances(restored, restored.cards[card.id]) == []
    restored.cards[card.id].tapped = False
    assert ward_instances(restored, restored.cards[card.id]) == ['{4}']


@pytest.mark.parametrize('player', [1, 2])
def test_tapped_conditional_source_does_not_trigger_when_targeted(player):
    state = clean(player)
    card = target(state, 'Iymrith, Desert Doom', 3-player)
    card.tapped = True
    bolt = add(state, 'Lightning Bolt', player, Zone.HAND)
    state.players[player].mana_pool.update(R=1)
    state = checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': bolt.id,
                          'targets': {'target_card_id': card.id}})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == bolt.id


def test_payment_labels_keep_oracle_capitalization():
    state = clean()
    card = target(state, 'Sauron, the Dark Lord', 2)
    assert printed_ward_costs(card) == ['Sacrifice a legendary artifact or legendary creature']


@pytest.mark.parametrize('name', ['Dancing Sword', 'Leyline Immersion'])
def test_effect_body_or_attachment_grant_is_not_printed_self_ward(name):
    state = clean()
    card = target(state, name, 2)
    assert printed_ward_costs(card) == []
    assert ward_instances(state, card) == []


def test_inline_player_counter_cost_is_supported():
    row = ROWS['Minthara, Merciless Soul']
    assert 'unsupported ward cost' not in known_unsupported_mechanics(row['oracle_text'])
    assert 'unsupported ward cost' not in known_unsupported_mechanics('', [row])
    state = clean()
    card = target(state, row['name'], 2)
    assert ward_instances(state, card) == ['{X}, where X is the number of experience counters you have']


@pytest.mark.parametrize('name', ['Rith, Liberated Primeval', 'Iymrith, Desert Doom',
    'Voja, Jaws of the Conclave', 'Sauron, the Dark Lord'])
def test_supported_costs_do_not_receive_false_cost_warning(name):
    assert 'unsupported ward cost' not in known_unsupported_mechanics(ROWS[name]['oracle_text'])
