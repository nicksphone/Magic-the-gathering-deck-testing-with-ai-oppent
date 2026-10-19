"""Complete negative bodies and paid object/type lifetime controls."""
import gzip
import json
from pathlib import Path

import pytest
import inventory as inv
import test_suncleanser_desired as s
import test_paid_modal as m
from rules_engine.counter_placement import counter_placement_forbidden
from rules_engine.type_effects import effective_types

facts = s.facts


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suffix', [' Draw a card.', '\nUnknown.', '\n\u2022 Draw a card.', ' unless you pay {1}.'])
def test_paid_unknown_complete_body_never_partially_removes(facts, seat, suffix):
    state, target = s.prepare(facts, seat, 'creature')
    source = s.g.add(state, facts, s.SOURCE, seat, s.Zone.HAND)
    # Deliberate adversarial compiler input, not an invented canonical card.
    state.cards[source].oracle_text += suffix
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = s.g.cast(s.g.respond(state, seat), seat, source)
    for _ in range(2):
        state = s.g.act(state, state.priority_player, 'pass_priority')
    assert not state.pending_mechanic_choice
    trigger = next(item for item in state.stack if item.source_card_id == source)
    assert trigger.effect_key == 'noop' and trigger.payload['__unsupported_trigger_instruction']
    s.drain(state)
    assert s.count(state, 'creature', target) == 1
    assert not state.retained_counter_prohibitions
    s.record('closed-negative-' + str(seat) + '-' + str(len(suffix)), state, explicit_negative_text=suffix)


@pytest.fixture(scope='module')
def song_facts(facts):
    proof = json.loads((s.HERE / 'provenance.json').read_text())
    bulk = Path(proof['bulk_path'])
    assert inv.sha(bulk) == proof['bulk_sha256']
    candidates = []
    exact = None
    size = 0
    with gzip.open(bulk, 'rb') as stream:
        for count in range(1, inv.MAX_RECORDS + 1):
            line = stream.readline(inv.MAX_LINE_BYTES + 1)
            if not line:
                break
            size += len(line)
            assert len(line) <= inv.MAX_LINE_BYTES and size <= inv.MAX_EXPANDED_BYTES
            raw = json.loads(line)
            if raw.get('name') == 'Song of the Dryads' and raw.get('lang') == 'en':
                candidates.append(raw)
                if raw['id'] == '161e66e3-0339-495c-bd06-0a799a254906':
                    exact = raw
        else:
            raise AssertionError('Canonical record bound exceeded')
    assert inv.sha(bulk) == proof['bulk_sha256']
    assert exact is not None or len(candidates) == 1
    song = exact if exact is not None else candidates[0]
    raw = {**facts, song['name']: song}
    with (s.OUT / (s.PHASE + '-song-canonical-facts.json')).open('x') as stream:
        json.dump({'bulk_sha256': proof['bulk_sha256'], 'records': count-1, 'expanded_bytes': size,
                   'full_raw': song, 'canonical_hash': s.digest(song),
                   'join': 'exact-printing' if exact else 'unique-English-name-representative'}, stream, sort_keys=True, indent=2)
    return raw


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_target_loses_creature_type_retains_object_ban(song_facts, seat):
    state, source, target = m.resolved(song_facts, seat, 'creature')
    reference = [s.object_incarnation(state.cards[target]), state.cards[target].zone_change_sequence]
    state, aura = s.paid(state, song_facts, seat, 'Song of the Dryads', {'C': 2, 'G': 1}, target_card_id=target)
    s.drain(state)
    s.record('closed-paid-type-change-' + str(seat), state, aura=aura, target=target)
    assert 'Creature' not in effective_types(state, state.cards[target])
    assert 'Land' in effective_types(state, state.cards[target])
    assert [s.object_incarnation(state.cards[target]), state.cards[target].zone_change_sequence] == reference
    assert counter_placement_forbidden(s.cold(state), '+1/+1', target_card_id=target)
