"""Real canonical paid land-sacrifice activation and atomic public negatives."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path

import pytest
import test_suncleanser_desired as s
from rules_engine.ability_model import build_ability_spec
from rules_engine.continuous import has_keyword
from rules_engine.costs import parse_activated_cost
from rules_engine.oracle_effects import extract_activated_abilities

facts = s.facts


@pytest.fixture(scope='module')
def full_facts(facts):
    root = Path(s.g.inv.ROOT) / 'backend/tests/fixtures/attached_characteristics'
    proof = json.loads((root / 'provenance.json').read_text())['cards']
    result = dict(facts)
    for name in ['Unsummon', 'Claim the Firstborn']:
        entry = proof[name]
        raw = (root / entry['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        result[name] = json.loads(raw)
    return result


def position(facts, actor):
    state = s.g.position(facts, actor)
    state, target = s.paid(state, facts, actor, 'Monastery Swiftspear', {'R': 1})
    state, source = s.paid(state, facts, actor, 'Sylvan Safekeeper', {'G': 1})
    land = s.g.add(state, facts, 'Forest', actor, s.Zone.HAND)
    state = s.g.act(s.g.respond(state, actor), actor, 'play_land', card_id=land)
    s.drain(state)
    return s.g.respond(state, actor), source, target, land


def activate(state, actor, source, target, lands):
    return s.g.act(state, actor, 'activate_ability', card_id=source, ability_index=0,
                   targets={'target_card_id': target}, payment_choices={'sacrifice_card_ids': lands})


def paid_bounce(state, facts, actor, target):
    state = s.g.respond(state, actor)
    source = s.g.add(state, facts, 'Unsummon', actor, s.Zone.HAND)
    state.players[actor].mana_pool = {'U': 1}
    state = s.g.cast(state, actor, source, target_card_id=target)
    frame = next(item for item in state.stack if item.source_card_id == source)
    assert frame.payload['mana_spent'] == 1
    assert sum(state.players[actor].mana_pool.values()) == 0
    for _ in range(8):
        if not any(item.id == frame.id for item in state.stack):
            break
        s.g.resolve(state)
    assert not any(item.id == frame.id for item in state.stack)
    assert state.cards[source].zone == s.Zone.GRAVEYARD
    return state


def record(label, state, **extra):
    out = s.OUT / (os.environ['ADMISSION_PHASE'] + '-' + label + '.json')
    with out.open('x') as stream:
        json.dump({'snapshot': s.serialize_match_snapshot(state), **extra}, stream, indent=2, sort_keys=True)


@pytest.mark.parametrize('actor', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_real_paid_safekeeper_land_shroud_and_natural_expiry(full_facts, actor, restore):
    state, source, target, land = position(full_facts, actor)
    unused = s.g.add(state, full_facts, 'Forest', actor)
    oracle = state.cards[source].oracle_text
    assert oracle == full_facts['Sylvan Safekeeper']['oracle_text']
    assert state.cards[source].zone == s.Zone.BATTLEFIELD
    assert not has_keyword(state, target, 'shroud')
    state = activate(state, actor, source, target, [land])
    assert state.cards[land].zone == s.Zone.GRAVEYARD
    assert state.cards[unused].zone == s.Zone.BATTLEFIELD
    frame = state.stack[-1]
    assert frame.source_card_id == source and frame.effect_key == 'grant_keyword'
    assert frame.payload['keyword'] == 'shroud' and frame.payload['target_card_id'] == target
    assert not has_keyword(state, target, 'shroud')
    state = s.cold(state) if restore else state
    s.drain(state)
    assert has_keyword(state, target, 'shroud')
    state = s.cold(state) if restore else state
    assert has_keyword(state, target, 'shroud')
    state = s.advance_main(state, 3 - actor)
    assert not has_keyword(state, target, 'shroud')
    assert state.cards[source].oracle_text == oracle
    assert state.cards[unused].zone == s.Zone.BATTLEFIELD
    record(f'paid-{actor}-{restore}', state, canonical_oracle=oracle, chosen_land=land, unchosen_land=unused)


@pytest.mark.parametrize('actor', [1, 2])
@pytest.mark.parametrize('case', ['missing-target', 'foreign-target', 'wrong-type-target',
    'stale-target', 'changed-control-target', 'foreign-source', 'wrong-type-source',
    'no-land', 'nonland-payment', 'foreign-land', 'duplicate-land', 'missing-land'])
def test_actual_public_activation_negative_is_atomic(full_facts, actor, case):
    state, source, target, land = position(full_facts, actor)
    selected = [land]
    targets = {'target_card_id': target}
    if case == 'missing-target':
        targets = {}
    elif case == 'foreign-target':
        targets = {'target_card_id': s.g.add(state, full_facts, 'Monastery Swiftspear', 3-actor)}
    elif case == 'wrong-type-target':
        targets = {'target_card_id': land}
    elif case == 'stale-target':
        state = paid_bounce(state, full_facts, actor, target)
        assert state.cards[target].zone == s.Zone.HAND
    elif case == 'changed-control-target':
        state = s.advance_main(state, 3-actor)
        state, _ = s.paid(state, full_facts, 3-actor, 'Claim the Firstborn', {'R': 1}, target_card_id=target)
        assert state.cards[target].controller == 3-actor
    elif case == 'foreign-source':
        source = s.g.add(state, full_facts, 'Sylvan Safekeeper', 3-actor)
    elif case == 'wrong-type-source':
        source = land
    elif case == 'no-land':
        state = activate(s.g.respond(state, actor), actor, source, target, [land])
        s.drain(state)
        assert state.cards[land].zone == s.Zone.GRAVEYARD
        targets = {'target_card_id': source}
    elif case == 'nonland-payment':
        selected = [target]
    elif case == 'foreign-land':
        selected = [s.g.add(state, full_facts, 'Forest', 3-actor)]
    elif case == 'duplicate-land':
        selected = [land, land]
    elif case == 'missing-land':
        selected = ['missing-physical-land']
    state = s.g.respond(state, actor)
    before = s.serialize_match_snapshot(state)
    with pytest.raises(s.ActionRejected):
        s.g.act(state, actor, 'activate_ability', card_id=source, ability_index=0,
                targets=targets, payment_choices={'sacrifice_card_ids': selected})
    assert s.serialize_match_snapshot(state) == before
    record(f'negative-{case}-{actor}', state)


@pytest.mark.parametrize('actor', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_real_paid_target_bounce_pending_activation_fizzles(full_facts, actor, restore):
    state, source, target, land = position(full_facts, actor)
    state = activate(state, actor, source, target, [land])
    state = paid_bounce(state, full_facts, actor, target)
    assert state.cards[target].zone == s.Zone.HAND
    state = s.cold(state) if restore else state
    s.drain(state)
    assert not has_keyword(state, target, 'shroud')
    assert state.cards[land].zone == s.Zone.GRAVEYARD
    record(f'bounce-{actor}-{restore}', state)


@pytest.mark.parametrize('cost', ['Sacrifice a land', 'Sacrifice two lands', 'Sacrifice 3 lands'])
def test_closed_land_parse_uses_existing_typed_kind(cost):
    parsed = parse_activated_cost(cost)
    assert parsed.supported and parsed.sacrifice_kind == 'land'
    assert parsed.sacrifice_creatures == {'Sacrifice a land': 1, 'Sacrifice two lands': 2,
                                          'Sacrifice 3 lands': 3}[cost]


@pytest.mark.parametrize('cost', ['Sacrifice a land and gain life', 'Sacrifice a land, Sacrifice a creature',
                                'Sacrifice a creature, Sacrifice a land', 'Sacrifice a library'])
def test_unknown_or_conflicting_cost_remains_unsupported(cost):
    assert not parse_activated_cost(cost).supported


def test_unbound_complete_body_no_fabricated_target(facts):
    state = s.g.position(facts, 1)
    source = s.g.add(state, facts, 'Sylvan Safekeeper', 1)
    ability = extract_activated_abilities(state.cards[source])[0]
    proxy = type('ActivatedOracleProxy', (), {'id': source, 'oracle_text': ability['text'],
                 'mana_cost': '', 'name': state.cards[source].name})()
    spec = build_ability_spec(state, proxy, 1, report_unsupported=False)
    assert spec.effect.key == 'grant_keyword' and spec.effect.payload['target_card_id'] is None
    assert spec.effect.payload['keyword'] == 'shroud'
    record('unbound', state, spec=asdict(spec))
