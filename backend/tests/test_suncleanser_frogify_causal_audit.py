"""Paid canonical attached ability loss versus already resolved/announced effects."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import test_suncleanser_desired as s
import test_paid_modal as modal
from game_state.serializers import serialize_match_snapshot
from rules_engine.continuous import effective_power, effective_toughness, effective_keywords
from rules_engine.colors import card_color_symbols
from rules_engine.type_effects import effective_types


facts = s.facts


@pytest.fixture(scope='module')
def flash_facts(facts):
    root = Path(__file__).parent / 'fixtures/global_flash_timing_audit'
    entry = next(row for row in json.loads((root / 'provenance.json').read_text())['cards']
                 if row['name'] == 'Leyline of Anticipation')
    raw = (root / entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    return {**facts, entry['name']: json.loads(raw)}


def restored(state, restore):
    return s.cold(state) if restore else state


def frogify(state, facts, seat, target):
    state, aura = s.paid(state, facts, seat, 'Frogify', {'C': 1, 'U': 1}, target_card_id=target)
    s.drain(state)
    assert state.cards[aura].zone == s.Zone.BATTLEFIELD
    assert state.cards[aura].attached_to == target
    assert state.cards[aura].oracle_text == facts['Frogify']['oracle_text']
    assert state.cards[target].zone == s.Zone.BATTLEFIELD
    assert not any(item.source_card_id == aura for item in state.stack)
    return state, aura


def observe(state, source, aura):
    before = serialize_match_snapshot(state)
    result = {
        'suppressed': s.printed_abilities_suppressed(state, source),
        'power': effective_power(state, source), 'toughness': effective_toughness(state, source),
        'keywords': effective_keywords(state, source),
        'types': effective_types(state, state.cards[source]),
        'colors': sorted(card_color_symbols(state.cards[source], state)),
        'attached_to': state.cards[aura].attached_to,
    }
    assert serialize_match_snapshot(state) == before
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('mode', ['creature', 'player'])
def test_actual_paid_frogify_suppresses_source_printed_abilities(facts, seat, restore, mode):
    state, source, target = modal.resolved(facts, seat, mode)
    state, aura = frogify(state, facts, seat, source)
    state = restored(state, restore)
    actual = observe(state, source, aura)
    s.record(f'loss-{seat}-{restore}-{mode}', state, source=source, aura=aura,
             target=target, observed=actual, full_canonical_paid=True)
    assert actual['suppressed'], 'actual attached canonical Frogify must suppress printed source abilities'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('mode', ['creature', 'player'])
def test_resolved_counter_prohibition_survives_aura_then_expires_on_real_departure(facts, seat, restore, mode):
    state, source, target = modal.resolved(facts, seat, mode)
    retained = deepcopy(state.retained_counter_prohibitions)
    state, aura = frogify(state, facts, seat, source)
    state = restored(state, restore)
    assert state.retained_counter_prohibitions == retained
    kwargs = {'target_card_id': target} if mode == 'creature' else {'target_player': target}
    assert s.counter_placement_forbidden(state, '+1/+1' if mode == 'creature' else 'experience', **kwargs)
    state = s.placement(state, facts, seat, mode, target)
    assert s.count(state, mode, target) == 0
    s.record(f'retained-{seat}-{restore}-{mode}', state, observed=observe(state, source, aura),
             retained_effect_preserved=True, suppression_not_certified_by_this_control=True)
    state, _ = s.paid(state, facts, seat, 'Long Goodbye', {'C': 1, 'B': 1}, target_card_id=source)
    s.drain(state)
    assert state.cards[source].zone == s.Zone.GRAVEYARD
    assert not s.counter_placement_forbidden(state, '+1/+1' if mode == 'creature' else 'experience', **kwargs)
    state = s.placement(state, facts, seat, mode, target)
    assert s.count(state, mode, target) > 0
    s.record(f'departed-{seat}-{restore}-{mode}', state, genuine_paid_departure=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('mode', ['creature', 'player'])
def test_actual_public_targeted_etb_frame_survives_later_paid_frogify(flash_facts, seat, restore, mode):
    facts = flash_facts
    state, target = s.prepare(facts, seat, mode)
    state, leyline = s.paid(state, facts, seat, 'Leyline of Anticipation', {'C': 2, 'U': 2})
    s.drain(state)
    assert state.cards[leyline].zone == s.Zone.BATTLEFIELD
    state, source = modal.source_entry(state, facts, seat)
    state = modal.select(state, seat, mode, target)
    frame = next(item.id for item in state.stack if item.source_card_id == source)
    assert not state.retained_counter_prohibitions
    state = s.g.respond(state, seat)
    aura = s.g.add(state, facts, 'Frogify', seat, s.Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'U': 1}
    state = s.g.cast(state, seat, aura, target_card_id=source)
    paid = next(item for item in state.stack if item.source_card_id == aura)
    assert paid.payload['mana_spent'] == 2 and not sum(state.players[seat].mana_pool.values())
    s.g.resolve(state)
    assert state.cards[aura].zone == s.Zone.BATTLEFIELD and state.cards[aura].attached_to == source
    assert any(item.id == frame for item in state.stack)
    state = restored(state, restore)
    s.record(f'pending-{seat}-{restore}-{mode}', state, observed=observe(state, source, aura),
             announced_frame=frame, actual_selected_public_target=target)
    s.drain(state)
    assert s.count(state, mode, target) == 0
    assert len(state.retained_counter_prohibitions) == 1
    state = s.placement(state, facts, seat, mode, target)
    assert s.count(state, mode, target) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_complete_canonical_frogify_body_on_actual_paid_keyword_creature(facts, seat, restore):
    state = s.g.position(facts, seat)
    state, source = s.paid(state, facts, seat, 'Monastery Swiftspear', {'R': 1})
    s.drain(state)
    state, aura = frogify(state, facts, seat, source)
    # Frogify's cast triggers prowess before attachment; that resolved buff survives
    # ability loss. Expire it via real priority/turn actions, not forced cleanup.
    state = s.advance_main(state, 3 - seat)
    state = restored(state, restore)
    actual = observe(state, source, aura)
    s.record(f'complete-{seat}-{restore}', state, observed=actual, full_raw_oracle=facts['Frogify']['oracle_text'])
    assert actual['suppressed'], 'canonical attached all-ability loss must suppress prowess and haste'
    assert actual['keywords'] == []
    assert actual['types'] == ['Creature'] and actual['colors'] == ['U']
    assert (actual['power'], actual['toughness']) == (1, 1)
