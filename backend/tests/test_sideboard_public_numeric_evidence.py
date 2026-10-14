"""Numeric advice baseline: canonical paid observations, no policy admission."""
from copy import deepcopy
from random import Random

import pytest

from ai import sideboard_facts as facts, sideboard_policy as policy
from card_data.hydration import hydrate_deck_cards
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from knowledge.service import estimate_for, tags_for
from main import MatchController, _post_step_finalize
from rules_engine.engine import RulesEngine
from tests.sideboard_finished_fixture_support import birth_order, cast, checked, settle
from tests.test_sideboard_finished_transition import MetadataRows, RAW


CASES = (
    ('known_one', ('Shuko',), 2),
    ('known_three', ('Teferi, Time Raveler',), 2),
    ('high_artifact', ('The One Ring',), 0),
    ('high_creature', ('Sheoldred, the Apocalypse',), 0),
    ('cheap_land_high_artifact', ('Forest', 'The One Ring'), 0),
    ('hidden_low', ('The One Ring',), 0),
    ('unknown_cost', ('Shuko',), 0),
    ('malformed_cost', ('Shuko',), 0),
    ('cross_record_cost', ('Forest', 'The One Ring'), 0),
    ('stale_incoming', ('Shuko',), None),
    ('public_return', ('Shuko',), 2),
    ('private_restart', ('Shuko',), 2),
)


@pytest.fixture(scope='module')
def incoming():
    metadata = MetadataRows()
    row = hydrate_deck_cards(metadata, [{'card_name': 'Abrupt Decay', 'quantity': 1}])[0]
    card = policy._view(row)
    assert tags_for(card).source == 'persisted'
    assert estimate_for(card) is not None
    assert policy._profile(row) is not None
    assert row['oracle_text'] == RAW['Abrupt Decay']['oracle_text']
    return metadata, row


def own_main(match, pid):
    for _ in range(160):
        state = match.state
        if state.active_player == pid and state.step == Step.PRECOMBAT_MAIN and not state.stack:
            return
        assert state.winner is None
        progress(match)
    raise AssertionError('Real empty turn did not reach actor main')


def progress(match):
    pending = match.state.pending_mechanic_choice
    if pending:
        assert pending['kind'] == 'cleanup_discard'
        options = sorted(pending['options'],
            key=lambda cid: ('Land' not in match.state.cards[cid].types, cid))
        checked(match, pending['player_id'],
            {'type': 'choose_mechanic', 'card_ids': options[:pending['count']]})
    else:
        checked(match, match.state.priority_player, {'type': 'pass_priority'})


def position(pid, names, metadata, *, return_public=False):
    other = 3-pid
    actor = hydrate_deck_cards(metadata, [
        {'card_name': 'Mountain', 'quantity': 58},
        {'card_name': 'Lightning Bolt', 'quantity': 1},
        {'card_name': 'Teferi, Time Raveler', 'quantity': 1},
    ])
    opponent = hydrate_deck_cards(metadata, [
        {'card_name': 'Forest', 'quantity': 56},
        *({'card_name': name, 'quantity': 1} for name in (
            'Shuko', 'Teferi, Time Raveler', 'The One Ring', 'Sheoldred, the Apocalypse')),
    ])
    order_rng = Random(73)
    permutations = {seat: list(range(60)) for seat in (1, 2)}
    for seat in (1, 2):
        order_rng.shuffle(permutations[seat])
    decks = {
        pid: birth_order(actor, {'Lightning Bolt': 1, 'Teferi, Time Raveler': 1}, permutations[pid]),
        other: birth_order(opponent, {name: 1 for name in (
            'Shuko', 'Teferi, Time Raveler', 'The One Ring', 'Sheoldred, the Apocalypse', 'Forest')},
            permutations[other]),
    }
    state = MatchFactory.from_decks(decks[1], decks[2], seed=73)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = other
    state.mechanic_choice_players = {1, 2}
    state.players[other].life = 3  # Trusted unit pose, NOT a natural-game sample.
    for player in state.players.values():
        player.mana_pool = {'U': 20, 'R': 20, 'W': 20, 'B': 20, 'G': 20, 'C': 20}
    match = MatchController(state=state, rules=RulesEngine(), controllers={1: 'human', 2: 'human'},
        ai={}, mode='player_vs_player', deck_ids=(None, None), mainboards=decks,
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3, root_seed=73)
    ids = {}
    for name in names:
        if name == 'Forest':
            cid = next(cid for cid in match.state.players[other].hand
                       if match.state.cards[cid].name == name)
            checked(match, other, {'type': 'play_land', 'card_id': cid})
        else:
            cid = cast(match, other, name)
            assert match.state.stack[-1].payload['mana_spent'] == {
                'Shuko': 1, 'Teferi, Time Raveler': 3,
                'The One Ring': 4, 'Sheoldred, the Apocalypse': 4,
            }[name]
            settle(match)
        ids[name] = cid
        record = match.state.card_observations[pid][cid]
        assert record['mana_cost'] == RAW[name]['mana_cost']
        assert record['id'] == cid and record['controller'] == other
    own_main(match, pid)
    if return_public:
        match.state.players[pid].mana_pool = {'W': 1, 'U': 1, 'C': 1, 'R': 1}
        pw = cast(match, pid, 'Teferi, Time Raveler')
        assert match.state.stack[-1].payload['mana_spent'] == 3
        settle(match)
        offered = next(move for move in match.rules.legal_moves(match.state, pid)
            if move['type'] == 'activate_loyalty' and move['card_id'] == pw and move['ability_index'] == 1)
        checked(match, pid, {**offered, 'targets': {'target_card_id': ids['Shuko']}})
        settle(match)
        assert match.state.cards[ids['Shuko']].zone == Zone.HAND
    # The Ring's real protection must expire naturally, not be removed by setup.
    if 'The One Ring' in names:
        for _ in range(160):
            if match.state.active_player == other:
                break
            progress(match)
        else:
            raise AssertionError('Real protection expiry turn did not begin')
        own_main(match, pid)
    match.state.players[pid].mana_pool['R'] = 1  # Explicit unit resource, genuine payment follows.
    cast(match, pid, 'Lightning Bolt', {'target_player': other})
    assert match.state.stack[-1].payload['mana_spent'] == 1
    settle(match)
    assert match.state.winner == pid and match.state.players[other].life == 0
    _post_step_finalize(match, None)
    assert match.state.sideboard_facts['complete'] is True
    return match.state, ids


@pytest.mark.parametrize('pid', (1, 2))
@pytest.mark.parametrize('case,names,want', CASES, ids=[case[0] for case in CASES])
def test_persisted_numeric_public_evidence(pid, case, names, want, incoming):
    metadata, original_row = incoming
    row = deepcopy(original_row)
    state, ids = position(pid, names, metadata, return_public=case == 'public_return')
    if case == 'hidden_low':
        cid = next(cid for cid in state.players[3-pid].hand if state.cards[cid].name == 'Shuko')
        assert cid not in state.card_observations.get(pid, {})
    if case in {'unknown_cost', 'malformed_cost', 'cross_record_cost', 'private_restart'}:
        wire = serialize_match_snapshot(state)
        if case != 'private_restart':
            # Explicit malformed-observation protocol COPY; canonical live card is unchanged.
            cid = ids['The One Ring'] if case == 'cross_record_cost' else ids['Shuko']
            record = wire['card_observations'][str(pid)][cid]
            record['mana_cost'] = {'unknown_cost': '', 'malformed_cost': '{UNKNOWN} tail',
                                   'cross_record_cost': '{1}'}[case]
        state = deserialize_match_snapshot(wire)
    before = serialize_match_snapshot(state)
    rng_before = state.rng.getstate()
    events = facts.summary_for(state, pid)
    assert events['qualified'] is True
    if case == 'stale_incoming':
        row['mana_cost'] = '{1}'
        assert tags_for(policy._view(row)).source != 'persisted'
        assert policy._profile(row) is None
    else:
        profile = policy._profile(row)
        assert profile is not None
        observed_fit = policy._fit(profile, events, row['oracle_text'])
    assert serialize_match_snapshot(state) == before
    assert state.rng.getstate() == rng_before
    if case != 'stale_incoming':
        assert row == original_row
        assert observed_fit == want
