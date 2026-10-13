"""NEW vanilla controls; held70 remains byte-exact. Trusted tactical poses.

Full fixed official intake was archived/readback-verified before offline use.
These test public sequencing intent and actual checked casts, not whole games.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.information import decision_view, is_unknown
from game_state.serializers import serialize_match_snapshot
from knowledge.profiles import derive_profile, merge_profile_payload
from knowledge.service import estimate_for, snapshot_for, tags_for
from rules_engine.continuous import effective_combat_stats
from rules_engine.engine import RulesEngine
from rules_engine.mana import mana_value
from tests.task43_play_order_support import RAW, rules, add_profiled, replay, choose, checked_cast

INTAKE = Path(__file__).parent / 'fixtures/task43_fixed_intake'
receipt_bytes = (INTAKE / 'PROVENANCE.json').read_bytes()
assert hashlib.sha256(receipt_bytes).hexdigest() == '0a26df8babdf4820fc9f9c7fc2488d4e6fef44d22a159859ebaec583b59dfd5a'
VANILLA = {}
for receipt in json.loads(receipt_bytes)['raw_receipts']:
    raw_bytes = (INTAKE / receipt['filename']).read_bytes()
    assert hashlib.sha256(raw_bytes).hexdigest() == receipt['sha256']
    assert receipt['http_status'] == 200 and receipt['full_raw_unmodified'] and not receipt['oracle_modified']
    raw = json.loads(raw_bytes)
    assert raw['name'] == receipt['name'] and raw['id'] == receipt['id'] and raw['oracle_id'] == receipt['oracle_id']
    assert raw['power'] == raw['toughness'] == '3' and raw['cmc'] == 2
    assert raw['oracle_text'] == '' and raw['keywords'] == [] and raw['layout'] == 'normal'
    VANILLA[raw['name']] = raw
assert set(VANILLA) == {'Watchwolf', 'Kalonian Tusker'}


def controlled_pose(seat, name, scenario, secret=None):
    state = rules.bare(seat)
    state.turn = 4
    for player in state.players.values():
        player.life = 20
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    # Declared trusted five-mana pool pays either complete cost, not both.
    state.players[seat].mana_pool = {'W': 2, 'U': 1, 'G': 2}
    # Five total avoids starving Tusker GG while Verdict pays 1WWU; no claim
    # that printed costs changed or that this was produced by a paid land line.
    creature = add_profiled(state, VANILLA[name], seat, rules.Zone.HAND)
    sweeper = add_profiled(state, RAW['Supreme Verdict'], seat, rules.Zone.HAND)
    assert effective_combat_stats(state, creature.id) == (3, 3) and mana_value(creature.mana_cost) == 2
    friendly, opponents = [], []
    if scenario != 'empty':
        opponent_raw, tier = {
            'stable_low': (VANILLA[name], 1), 'urgent_low': (VANILLA[name], 1),
            'resource_low': (RAW['Llanowar Elves'], 1),
            'tier2': (RAW['Torrential Gearhulk'], 2),
            'tier3': (RAW['Sheoldred, the Apocalypse'], 3),
        }[scenario]
        for _ in range(2):
            card = add_profiled(state, opponent_raw, 3 - seat, rules.Zone.BATTLEFIELD)
            assert estimate_for(card).tier == derive_profile(opponent_raw).threat_level == tier
            assert not card.tapped and not card.summoning_sick
            opponents.append(card.id)
        assert sum(estimate_for(state.cards[cid]).tier for cid in opponents) / len(opponents) == tier
    if scenario == 'stable_low':
        # Public parity: two vanilla 3/3s on each side, life20, no engines,
        # grants or counters. Sweeping trades two own bodies for two opposing;
        # deployment adds a third body. This is a qualified sequencing intent.
        other = 'Kalonian Tusker' if name == 'Watchwolf' else 'Watchwolf'
        friendly = [add_profiled(state, VANILLA[other], seat, rules.Zone.BATTLEFIELD).id for _ in range(2)]
        assert all(effective_combat_stats(state, cid) == (3, 3) for cid in friendly + opponents)
    if scenario == 'urgent_low':
        state.players[seat].life = 3
        assert not state.players[seat].battlefield
        assert [effective_combat_stats(state, cid) for cid in opponents] == [(3, 3), (3, 3)]
        # Ready six power vs life3; one new blocker leaves three power.
        # This is declared immediate combat pressure, not an executed game.
    if secret:
        add_profiled(state, RAW[secret], 3 - seat, rules.Zone.HAND)
    return state, creature.id, sweeper.id, friendly, opponents


@pytest.mark.parametrize('name', ['Watchwolf', 'Kalonian Tusker'])
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
@pytest.mark.parametrize('scenario', ['empty', 'stable_low', 'urgent_low', 'resource_low', 'tier2', 'tier3'])
def test_canonical_vanilla_qualified_stable_hold_and_urgent_resource_developed_sweep(name, seat, roundtrip, scenario):
    state, creature, sweeper, friendly, opponents = controlled_pose(seat, name, scenario)
    state = replay(state, roundtrip)
    action, ranked = choose(state, seat, creature, sweeper)
    result = checked_cast(state, seat, action)
    swept = action['card_id'] == sweeper
    for cid in friendly + opponents:
        assert result.cards[cid].zone == (rules.Zone.GRAVEYARD if swept else rules.Zone.BATTLEFIELD)
    assert result.players[seat].life == state.players[seat].life
    print('TASK43_CONTROL=' + json.dumps({'name': name, 'seat': seat, 'replay': roundtrip,
        'scenario': scenario, 'selected': state.cards[action['card_id']].name,
        'friendly_cleared': len(friendly) if swept else 0,
        'opponents_cleared': len(opponents) if swept else 0, 'life': result.players[seat].life}, sort_keys=True))
    expected = creature if scenario in ('empty', 'stable_low') else sweeper
    assert action['card_id'] == expected, 'Qualified public-context sequencing intent differs from actual checked policy'
    # Urgent choose_action may use its existing stabilization override ahead of
    # rank. Preserve that seam; this assertion is about the actual decision.
    if scenario != 'urgent_low':
        assert ranked.index(expected) < ranked.index(creature if expected == sweeper else sweeper)


@pytest.mark.parametrize('name', ['Watchwolf', 'Kalonian Tusker'])
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
@pytest.mark.parametrize('scenario', ['stable_low', 'urgent_low'])
def test_vanilla_public_controls_are_hidden_identity_invariant_and_checked(name, seat, roundtrip, scenario):
    actions = []
    for secret in ('Counterspell', 'Lightning Bolt'):
        state, creature, sweeper, _, opponents = controlled_pose(seat, name, scenario, secret)
        state = replay(state, roundtrip)
        hidden = state.players[3 - seat].hand[0]
        before = serialize_match_snapshot(state)
        legal = RulesEngine().legal_moves(state, seat)
        public, _ = decision_view(state, seat, legal)
        assert is_unknown(public.cards[hidden]) and not public.cards[hidden].knowledge_snapshot
        assert estimate_for(public.cards[hidden]) is None
        action, _ = choose(state, seat, creature, sweeper)
        actions.append(action)
        result = checked_cast(state, seat, action)
        assert all(result.cards[cid].zone == (rules.Zone.GRAVEYARD if action['card_id'] == sweeper else rules.Zone.BATTLEFIELD) for cid in opponents)
        assert serialize_match_snapshot(state) == before
    assert actions[0] == actions[1]


@pytest.mark.parametrize('name', ['Watchwolf', 'Kalonian Tusker'])
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
@pytest.mark.parametrize('context', ['printed_only', 'known_own_corpus'])
def test_actual_vanilla_printed_and_declared_own_corpus_values_require_real_carrier(name, seat, roundtrip, context):
    state, cid, _, _, _ = controlled_pose(seat, name, 'empty')
    raw = VANILLA[name]
    corpus = []
    if context == 'known_own_corpus':
        for _ in range(2):
            add_profiled(state, raw, seat, rules.Zone.LIBRARY)
        corpus = [{'card_metadata': raw, 'quantity': 3}, {'card_metadata': RAW['Supreme Verdict'], 'quantity': 1}]
    profile = derive_profile(raw, corpus)
    expected = 5.4 if corpus else 4.9
    assert profile.play_value == expected and profile.context['curve_nonland_mean'] == (2.5 if corpus else None)
    assert profile.input_sha256 == derive_profile(raw).input_sha256
    assert profile.context['archetype_verification'] == 'caller_declared_not_verified'
    row = SimpleNamespace(name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall',
        profiles_json=json.dumps(merge_profile_payload({'card_data': raw}, profile)))
    hydrated = {key: raw.get(key, '') for key in ('oracle_text', 'type_line', 'mana_cost', 'layout')}
    hydrated['card_faces'] = deepcopy(raw.get('card_faces', []))
    state.cards[cid].knowledge_snapshot = snapshot_for(row, raw['name'], hydrated)
    assert state.cards[cid].knowledge_snapshot and tags_for(state.cards[cid]).source == 'persisted'
    state = replay(state, roundtrip)
    before = serialize_match_snapshot(state)
    estimate = estimate_for(state.cards[cid])
    assert estimate is not None and estimate.tier == 1
    value = getattr(estimate, 'play_value', None)
    print('TASK43_VANILLA_VALUE=' + json.dumps({'name': name, 'context': context, 'derived': expected,
        'transported': value, 'corpus_fingerprint': profile.context['corpus_fingerprint'],
        'input_sha256': profile.input_sha256}, sort_keys=True))
    assert type(value) is float and math.isfinite(value), 'Actual canonical vanilla persisted value is absent from typed service carrier'
    assert value == expected
    assert serialize_match_snapshot(state) == before
