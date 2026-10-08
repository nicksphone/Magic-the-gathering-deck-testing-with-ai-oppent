"""Paid source/target proof; separate target-free and legacy-reference controls."""
from copy import copy, deepcopy
import pytest
import test_generic_prerequisite_repairs as p
from game_state.state import Zone, object_incarnation
from rules_engine.oracle_effects import infer_effect_from_oracle, extract_activated_abilities

e, c = p.e, p.c
basefacts = p.basefacts
existingfacts = p.existingfacts
facts = p.facts
action_receipt = p.action_receipt


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('renamed', [False, True])
@pytest.mark.parametrize('target_owner', ['own', 'foreign'])
def test_paid_seeker_preview_and_resolution(facts, seat, renamed, target_owner, request):
    derived = deepcopy(facts)
    name = 'Isolated untap source' if renamed else 'Seeker of Skybreak'
    if renamed:
        derived[name] = deepcopy(derived['Seeker of Skybreak'])
        derived[name]['name'] = name
    state = c.g.position(facts, seat)
    target = (e.add(state, facts, 'Raging Goblin', 3-seat, Zone.BATTLEFIELD)
              if target_owner == 'foreign' else None)
    source = e.add(state, derived, name, seat)
    if target is None:
        target = source
    state, frame = c.paid(state, seat, source, {'C': 1, 'G': 1})
    state = e.frame_done(c.cold(state), frame)
    state = c.sun.advance_main(c.cold(state), 3-seat)
    state = c.sun.advance_main(c.cold(state), seat)
    assert not state.cards[source].summoning_sick
    if target_owner == 'foreign':
        state = p.tap_paid(state, facts, seat, target)
    else:
        assert not state.cards[target].tapped
    before_ref = (object_incarnation(state.cards[target]), state.cards[target].zone_change_sequence)
    state = c.priority(c.cold(state), seat)
    state.players[seat].mana_pool = {}
    moves = c.offers(state, seat)
    assert any(m['type'] == 'activate_ability' and m.get('card_id') == source for m in moves)
    before = c.snapshot(state)
    ability = extract_activated_abilities(state.cards[source])[0]
    proxy = copy(state.cards[source])
    proxy.oracle_text = ability['text']
    key, payload = infer_effect_from_oracle(state, proxy, seat, {}, report_unsupported=False)
    assert key == 'untap' and payload == {'target_card_id': None}
    assert c.snapshot(state) == before
    hidden = c.private(state, 3-seat)
    invalid = state.players[3-seat].library[0]
    e.reject(state, seat, {'type': 'activate_ability', 'card_id': source,
                          'ability_index': 0, 'targets': {'target_card_id': invalid}})
    state = c.act(state, seat, {'type': 'activate_ability', 'card_id': source,
                 'ability_index': 0, 'targets': {'target_card_id': target}})
    assert state.cards[source].tapped and sum(state.players[seat].mana_pool.values()) == 0
    item = state.stack[-1]
    assert item.effect_key == 'untap' and item.payload['target_card_id'] == target
    state = e.frame_done(c.cold(state), item.id)
    assert not state.cards[target].tapped
    assert (object_incarnation(state.cards[target]), state.cards[target].zone_change_sequence) == before_ref
    assert c.private(state, 3-seat) == hidden
    p.record(request, state, derived, [name, 'Seeker of Skybreak', 'Icy Manipulator'],
             renamed_synthetic=renamed, target_owner=target_owner, preview_target=None)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('line', ['Untap it.', 'Untap that creature.'])
@pytest.mark.parametrize('selected', [False, True])
def test_current_legacy_reference_unchanged(facts, seat, line, selected):
    state = c.g.position(facts, seat)
    target = e.add(state, facts, 'Raging Goblin', seat, Zone.BATTLEFIELD)
    source = e.add(state, facts, 'Seeker of Skybreak', seat)
    proxy = copy(state.cards[source])
    proxy.oracle_text = line
    before = c.snapshot(state)
    key, payload = infer_effect_from_oracle(state, proxy, seat,
                    {'target_card_id': target} if selected else {}, report_unsupported=False)
    assert key == ('untap' if selected else 'noop')
    if selected:
        assert payload['target_card_id'] == target
    else:
        assert not payload.get('target_card_id')
    assert c.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('line', [
    'Untap target creature. Then perform an unspecified operation.',
    'Untap target creature (UNPARSED-SUFFIX).',
    'Untap target creature spell.', 'Untap target unknown.',
])
def test_unknown_raw_preview_no_partial_effect(facts, seat, line):
    state = c.g.position(facts, seat)
    source = e.add(state, facts, 'Seeker of Skybreak', seat)
    proxy = copy(state.cards[source])
    proxy.oracle_text = line
    before = c.snapshot(state)
    key, payload = infer_effect_from_oracle(state, proxy, seat, {}, report_unsupported=False)
    assert key == 'noop' and not payload.get('target_card_id')
    assert c.snapshot(state) == before
