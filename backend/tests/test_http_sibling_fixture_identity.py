"""Native prefix/serde + explicit inert persistence seam, not HTTP acceptance."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

import main
from card_data.seed_cards import seed_card_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory
from tests import fixture_state_support as support
from tests import test_kicker_goldens as kicker
from tests import test_private_choice_intent_boundary as boundary
from tests import test_archangel_pair_http_goldens as archangel
from tests.test_activated_top_selection import position as officer_position


class PrefixCaptured(Exception):
    pass


class InertRepository:
    def __init__(self, state):
        self.rows = {state.id: serialize_match_snapshot(state)}
        self.deleted = []

    def delete_active_match(self, mid):
        self.deleted.append(mid)
        del self.rows[mid]


def protocol(monkeypatch, module):
    raw = seed_card_payload('Island')
    assert raw is not None
    deck = [{**raw, 'card_name': 'Island', 'quantity': 60}]
    original = MatchFactory.from_decks(deck, deck, seed=4)
    controller = SimpleNamespace(state=original, controllers={1: 'human', 2: 'human'},
                                 mode='human_vs_human', settings={'retained': True})
    configuration = deepcopy({k: v for k, v in vars(controller).items() if k != 'state'})
    repo = InertRepository(original)
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {original.id: controller})

    def inert_persist(repository, current):
        repository.rows[current.state.id] = serialize_match_snapshot(current.state)

    monkeypatch.setattr(main, '_persist_active_match', inert_persist)

    def capture(current):
        state = current.state
        packet = serialize_match_snapshot(state)
        assert serialize_match_snapshot(deserialize_match_snapshot(packet)) == packet
        assert {k: v for k, v in vars(current).items() if k != 'state'} == configuration
        assert main.ACTIVE_MATCHES[state.id] is current
        if state.sideboard_facts:
            assert state.sideboard_facts['game_id'] == state.id
        raise PrefixCaptured

    def adopt(current, state):
        support.adopt_fixture_state(current, state, repo=repo)
        assert original.id not in main.ACTIVE_MATCHES if state.id != original.id else True
        assert repo.rows[state.id] == serialize_match_snapshot(state)
        capture(current)

    monkeypatch.setattr(module, 'persist', capture)
    # The candidate binds this existing helper explicitly; no project call is bypassed.
    monkeypatch.setattr(module, 'adopt_fixture_state', adopt, raising=False)
    return controller, repo


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Eject the Warp Core', 'Hypnotic Cloud'])
def test_kicker_native_setup_binding_before_any_http(monkeypatch, seat, name):
    controller, _ = protocol(monkeypatch, kicker)
    with pytest.raises(PrefixCaptured):
        kicker.test_http_canonical_payment_and_sqlite_restore((None, controller), seat, name, True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('entry', ['selection', 'bad_alias'])
def test_both_private_choice_http_prefixes_preserve_strict_state(monkeypatch, seat, family, entry):
    controller, _ = protocol(monkeypatch, boundary)
    with pytest.raises(PrefixCaptured):
        if entry == 'selection':
            boundary.test_raw_http_strict_action_wrong_actor_and_database_root(
                family, seat, False, (None, controller))
        else:
            boundary.test_raw_http_bad_alias_null_never_reaches_engine(
                family, seat, {'unknown': None}, (None, controller), monkeypatch)


@pytest.mark.parametrize('seat', [1, 2])
def test_archangel_shared_position_retains_native_capture(monkeypatch, seat):
    controller, _ = protocol(monkeypatch, archangel)
    with pytest.raises(PrefixCaptured):
        archangel.position(controller, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_corrupt_captured_id_rejects_before_real_adopt_mutates_any_binding(monkeypatch, seat):
    controller, repo = protocol(monkeypatch, archangel)
    original = controller.state
    state, _ = archangel.setup(seat)
    before = deepcopy(repo.rows)
    registry = dict(main.ACTIVE_MATCHES)
    state.id = original.id
    with pytest.raises(ValueError, match='Invalid private sideboard facts'):
        support.adopt_fixture_state(controller, state, repo=repo)
    assert controller.state is original
    assert main.ACTIVE_MATCHES == registry
    assert repo.rows == before and not repo.deleted


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_officer_board_is_unknown_from_birth_not_a_capture_failure(seat):
    state, _, _, _ = officer_position(seat)
    assert state.sideboard_facts == {}
    before_rng = state.rng.getstate()
    packet = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(packet)) == packet
    assert state.rng.getstate() == before_rng
