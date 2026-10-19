"""Query-only canonical Jailer contracts; no actions, payments or native startup."""
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import pickle
import random

import pytest

from game_state.state import CardInstance, MatchState, PlayerState, Step, Zone
from rules_engine.card_faces import select_cast_face
from rules_engine.card_types import printed_card_types
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.graveyard_permissions import battlefield_entry_prohibited
from rules_engine.query_context import query_cache, rule_query_scope
from rules_engine.restrictions import can_cast_in_current_timing


FIXTURES = Path(__file__).parent / 'fixtures'
PERMANENTS = (
    ('Delighted Halfling', 'Creature'),
    ('Shuko', 'Artifact'),
    ('Up the Beanstalk', 'Enchantment'),
    ('Nissa, Ascended Animist', 'Planeswalker'),
    ('Forest', 'Land'),
)
ADVENTURE = "Imodane's Recruiter // Train Troops"


@pytest.fixture(scope='module')
def rows():
    directory = FIXTURES / 'historical_event_catalog'
    provenance = json.loads((directory / 'provenance.json').read_text())
    raw = (directory / 'canonical.jsonl').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == provenance['files_sha256']['canonical.jsonl']
    assert provenance['raw_facts_modified'] is False
    data = {row['name']: row for row in map(json.loads, raw.splitlines())}
    assert len(data) == provenance['unique_canonical_cards'] == 67
    jailer = data['Soulless Jailer']
    assert hashlib.sha256(json.dumps(jailer, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == (
        '0744750a744b010552b631b2b5578e76f13b7a2c68d81b1eea4ede7080b6fe33')
    builtin = json.loads((Path(__file__).parents[1] / 'card_data' /
                          'builtin_oracle_seed.json').read_text())['cards']['Soulless Jailer']
    for field in ('id', 'oracle_id', 'name', 'type_line', 'oracle_text'):
        assert builtin[field] == jailer[field]
    data['Humility'] = json.loads((FIXTURES / 'creature_observer_fix/humility.json').read_text())
    assert data['Humility']['id'] == '55ad6a45-a840-45ba-89ad-066e20e983f3'
    return data


def position(seat):
    return MatchState(id='jailer-query', players={
        pid: PlayerState(id=pid, name='Seat ' + str(pid)) for pid in (1, 2)},
        cards={}, stack=[], rng=random.Random(37), active_player=seat,
        priority_player=seat, step=Step.PRECOMBAT_MAIN, pregame_pending=False)


def add(state, row, seat, zone):
    # Seed complete canonical characteristics without invoking entry or action routes.
    front = (row.get('card_faces') or [row])[0]
    card = CardInstance(id='query-' + str(len(state.cards)), name=front['name'],
        owner=seat, controller=seat, zone=zone,
        types=printed_card_types(front['type_line']), type_line=front['type_line'],
        oracle_text=front.get('oracle_text', ''), mana_cost=front.get('mana_cost', ''),
        card_faces=deepcopy(row.get('card_faces', [])), layout=row.get('layout', ''),
        power=int(front['power']) if str(front.get('power', '')).isdigit() else None,
        toughness=int(front['toughness']) if str(front.get('toughness', '')).isdigit() else None,
        loyalty=int(front['loyalty']) if str(front.get('loyalty', '')).isdigit() else None,
        colors=deepcopy(front.get('colors', row.get('colors'))))
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


@contextmanager
def pure_scope(state):
    before = pickle.dumps(state, protocol=5)
    assert query_cache(state) is None
    try:
        with rule_query_scope(state):
            yield
    finally:
        assert query_cache(state) is None
        assert pickle.dumps(state, protocol=5) == before


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('name,kind', PERMANENTS)
def test_graveyard_permanent_entry_is_blocked(rows, seat, name, kind):
    results = []
    for controller in (seat, 3 - seat):
        state = position(seat)
        add(state, rows['Soulless Jailer'], controller, Zone.BATTLEFIELD)
        target = add(state, rows[name], seat, Zone.GRAVEYARD)
        assert kind in target.types
        with pure_scope(state):
            results.extend(battlefield_entry_prohibited(state, target.id) for _ in range(2))
    assert results == [True, True, True, True]


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('name,kind', PERMANENTS)
def test_library_permanent_entry_is_unaffected(rows, seat, name, kind):
    for controller in (seat, 3 - seat):
        state = position(seat)
        add(state, rows['Soulless Jailer'], controller, Zone.BATTLEFIELD)
        target = add(state, rows[name], seat, Zone.LIBRARY)
        assert kind in target.types
        with pure_scope(state):
            assert battlefield_entry_prohibited(state, target.id) is False
            assert battlefield_entry_prohibited(state, target.id) is False


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('face,zone,allowed', (
    (0, Zone.GRAVEYARD, True), (1, Zone.GRAVEYARD, False),
    (0, Zone.EXILE, True), (1, Zone.EXILE, False),
    (0, Zone.HAND, True), (1, Zone.HAND, True),
    (0, Zone.LIBRARY, True), (1, Zone.LIBRARY, True),
))
def test_cast_timing_uses_actual_selected_spell_characteristics(rows, seat, face, zone, allowed):
    # The shared zone-only query has no typed ABI; exercise its real typed caller.
    probes = [(ADVENTURE, face)]
    if face == 1:
        probes += [(name, 0) for name in ('Shuko', 'Up the Beanstalk',
                                         'Nissa, Ascended Animist', 'Negate')]
    results = []
    for controller in (seat, 3 - seat):
        for name, selected in probes:
            state = position(seat)
            add(state, rows['Soulless Jailer'], controller, Zone.BATTLEFIELD)
            card = add(state, rows[name], seat, zone)
            before_face = pickle.dumps(state, protocol=5)
            view = select_cast_face(card, selected)
            assert pickle.dumps(state, protocol=5) == before_face
            assert ('Creature' in view.types) is (face == 0)
            with pure_scope(state):
                result = can_cast_in_current_timing(state, view, seat)
                assert isinstance(result, tuple) and type(result[0]) is bool
                assert can_cast_in_current_timing(state, view, seat) == result
                results.append(result[0])
    assert results == [allowed] * (2 * len(probes))


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('mode', ('not_on_battlefield', 'suppressed'))
def test_inactive_or_suppressed_source_cannot_block_entry_or_cast_queries(rows, seat, mode):
    for controller in (seat, 3 - seat):
        state = position(seat)
        jailer = add(state, rows['Soulless Jailer'], controller,
                     Zone.HAND if mode == 'not_on_battlefield' else Zone.BATTLEFIELD)
        if mode == 'suppressed':
            add(state, rows['Humility'], seat, Zone.BATTLEFIELD)
        target = add(state, rows['Shuko'], seat, Zone.GRAVEYARD)
        with pure_scope(state):
            assert printed_abilities_suppressed(state, jailer.id) is (mode == 'suppressed')
            assert battlefield_entry_prohibited(state, target.id) is False
            assert can_cast_in_current_timing(state, target, seat)[0] is True
