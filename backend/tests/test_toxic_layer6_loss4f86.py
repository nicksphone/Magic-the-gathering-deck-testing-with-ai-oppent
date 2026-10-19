"""Layer-six resolution goldens, not canonical spell-cast qualification.

Named cards retain pinned complete RAW. Repeated printed clauses/family labels
below are explicitly keyword-grammar protocol vectors, not official card data.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.combat import _deal_unblocked_damage
from rules_engine.continuous import effective_keyword_counts, printed_abilities_suppressed
from rules_engine.query_context import rule_query_scope
from tests.test_toxic_damage4f86 import pose


def keyword_effect(state, source, keywords, operation='grant'):
    resolve_effect(state, source.controller, 'grant_keyword', {
        'target_card_id': source.id, 'keywords': keywords, 'operation': operation,
    })


def check_damage(state, source, poison):
    target = state.players[3-source.controller]
    before = (target.life, target.poison)
    assert _deal_unblocked_damage(state, f'player:{3-source.controller}', 1, source.id) == 1
    assert (target.life, target.poison) == (before[0]-1, before[1]+poison)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_specific_keyword_removal_cannot_be_reintroduced_from_oracle(seat):
    state, source = pose(seat)
    keyword_effect(state, source, ['toxic 1'], 'remove')
    assert not effective_keyword_counts(state, source.id).get('toxic 1')
    assert not printed_abilities_suppressed(state, source.id)
    check_damage(state, source, 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_specific_loss_preserves_other_numeric_instances(seat):
    state, source = pose(seat)
    keyword_effect(state, source, ['toxic 1', 'toxic 2'])
    keyword_effect(state, source, ['toxic 1'], 'remove')
    check_damage(state, source, 2)
    assert effective_keyword_counts(state, source.id) == {'toxic 2': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_family_loss_removes_all_printed_and_granted_numeric_instances(seat):
    state, source = pose(seat)
    keyword_effect(state, source, ['toxic 1', 'toxic 2'])
    keyword_effect(state, source, ['toxic'], 'remove')
    check_damage(state, source, 0)
    assert not any(key.startswith('toxic') for key in effective_keyword_counts(state, source.id))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('loss', ['toxic 1', 'all abilities'])
@pytest.mark.parametrize('grant_after_loss', [False, True])
def test_resolved_grants_and_specific_or_whole_loss_use_actual_timestamp_order(
        seat, loss, grant_after_loss):
    state, source = pose(seat)
    grants = ['toxic 1', 'toxic 1', 'toxic 2']
    if not grant_after_loss:
        keyword_effect(state, source, grants)
    keyword_effect(state, source, [loss], 'remove')
    if grant_after_loss:
        keyword_effect(state, source, grants)
    check_damage(state, source, 4 if grant_after_loss else 2 if loss == 'toxic 1' else 0)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('period', ['', '.'])
@pytest.mark.parametrize('loss', [None, 'toxic 1', 'toxic'])
def test_repeated_printed_keyword_grammar_instances_are_counted_before_removals(seat, period, loss):
    state, _ = pose(seat, 'Grizzly Bears')
    source = CardInstance(id='keyword-grammar', name='Repeated toxic grammar vector',
        owner=seat, controller=seat, zone=Zone.BATTLEFIELD,
        types=['Creature'], power=1, toughness=1,
        oracle_text=f'Toxic 1{period}\nToxic 1{period}\nToxic 2{period}',
        keywords=['toxic'])
    state.cards[source.id] = source
    state.players[seat].battlefield.append(source.id)
    if loss:
        keyword_effect(state, source, [loss], 'remove')
    check_damage(state, source, 4 if loss is None else 2 if loss == 'toxic 1' else 0)
    counts = effective_keyword_counts(state, source.id)
    assert 'toxic' not in counts
    assert counts == ({'toxic 1': 2, 'toxic 2': 1} if loss is None else {'toxic 2': 1} if loss == 'toxic 1' else {})


def put_pinned_humility(state, seat):
    file = Path(__file__).parent / 'fixtures/ability_suppression.json'
    data = file.read_bytes()
    assert hashlib.sha256(data).hexdigest() == '91f7516a2a13ab79847fb57c39aee7e0bd9ca21e1d45316d1ae2d00980fd30cf'
    raw = next(row for row in json.loads(data) if row['name'] == 'Humility')
    assert raw['object'] == 'card'
    cached = ScryfallSyncService._normalize_payload(raw, '/owned-fixture-display/humility.svg')
    entry = {**raw, **cached, 'card_name': raw['name'], 'quantity': 1}
    factory = MatchFactory.from_decks([entry], [entry], seed=867)
    card = next(card for card in factory.cards.values() if card.owner == seat)
    card.id = 'humility'
    card.move_to_zone(Zone.BATTLEFIELD)
    assert card.oracle_text == raw['oracle_text'] and card.type_line == raw['type_line']
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant_after_humility', [False, True])
def test_full_pinned_humility_suppresses_printed_but_not_later_resolved_grants(seat, grant_after_humility):
    state, source = pose(seat)
    put_pinned_humility(state, 3-seat)
    assert printed_abilities_suppressed(state, source.id)
    if grant_after_humility:
        keyword_effect(state, source, ['toxic 2'])
    check_damage(state, source, 2 if grant_after_humility else 0)
    assert effective_keyword_counts(state, source.id) == ({'toxic 2': 1} if grant_after_humility else {})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('loss', ['toxic 1', 'toxic', 'all abilities'])
def test_snapshot_and_scoped_query_keep_final_loss_counts_unchanged_by_damage(seat, loss):
    state, source = pose(seat)
    keyword_effect(state, source, ['toxic 1', 'toxic 2'])
    keyword_effect(state, source, [loss], 'remove')
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(before)
    assert serialize_match_snapshot(restored) == before
    restored_source = restored.cards[source.id]
    with rule_query_scope(restored):
        counts = effective_keyword_counts(restored, source.id)
        saved = deepcopy(counts)
        check_damage(restored, restored_source, 2 if loss == 'toxic 1' else 0)
        assert counts == saved
        assert effective_keyword_counts(restored, source.id) == saved
    assert restored_source.keyword_effects == source.keyword_effects


@pytest.mark.parametrize('seat', [1, 2])
def test_full_canonical_printed_toxic_is_in_final_count_before_any_consumer(seat):
    state, source = pose(seat)
    assert effective_keyword_counts(state, source.id) == {'toxic 1': 1}
    check_damage(state, source, 1)
