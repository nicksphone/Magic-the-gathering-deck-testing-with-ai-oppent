"""Full canonical human legend selection; no fabricated pending event or stack."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.extra_sequence_support import position
from tests.test_combat_graveyard_caller_audit import Episode, receipts, client, base_client, repo
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import snap, restart
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts

FIXTURE = Path(__file__).parent / 'fixtures/legend_keeper_audit/canonical.jsonl'
ROWS = {r['name']: r for r in map(json.loads, FIXTURE.read_text().splitlines())}
KOZILEK = 'Kozilek, Butcher of Truth'
ISAMARU = 'Isamaru, Hound of Konda'
FAMILIES = [ISAMARU, 'Progenitus']


class Legend(Episode):
    def __init__(self, seat, name, foreign=False, replacement=False, client=None, repo=None):
        super().__init__(seat, 'ordinary', False, client, repo)
        match_id = self.state.id
        # Explicit canonical retained initial position, before any paid action.
        self.state = position(3-seat if foreign else seat)
        self.state.id = match_id
        self.state.mechanic_choice_players = {1, 2}
        self.state.priority_stops = {pid: set(Step) for pid in (1, 2)}
        self.state.replacement_choice_required = True
        self.state.replacement_choice_players = {1, 2}
        self.name, self.foreign, self.replacement = name, foreign, replacement
        self.old = raw_card(self.state, ROWS[name], 3-seat if foreign else seat, Zone.HAND).id
        self.new = raw_card(self.state, ROWS[name], seat, Zone.HAND).id
        self.theft = raw_card(self.state, ROWS['Act of Treason'], seat, Zone.HAND).id if foreign else None
        self.rip = raw_card(self.state, ROWS['Rest in Peace'], seat, Zone.HAND).id if replacement else None
        if repo:
            for row in ROWS.values():
                repo.upsert_card(normalize(row))
        self.trace = []
        self.persist()

    def pay_cast(self, cid, targets=None):
        actor = self.state.cards[cid].controller
        before_hand = len(self.state.players[actor].hand)
        self.state.players[actor].mana_pool = {c: 10 for c in 'WUBRGC'}
        self.persist()
        self.act(actor, {'type': 'cast_spell', 'card_id': cid, 'targets': targets or {}})
        assert sum(self.state.players[actor].mana_pool.values()) < 60
        assert any(item.source_card_id == cid for item in self.state.stack)
        for _ in range(50):
            if not self.state.stack or self.state.pending_mechanic_choice or self.state.pending_replacement_choice:
                break
            assert not self.state.pending_trigger_order
            self.act(self.state.priority_player, {'type': 'pass_priority'})
        else:
            pytest.fail('Paid canonical stack did not resolve/pause in50 actions')
        if self.state.cards[cid].name == KOZILEK:
            assert len(self.state.players[actor].hand) == before_hand - 1 + 4, 'Full real cast trigger draws exactly4'

    def first(self):
        self.pay_cast(self.old)
        assert self.state.cards[self.old].zone == Zone.BATTLEFIELD
        assert not self.state.pending_mechanic_choice and not self.state.pending_replacement_choice
        if self.foreign:
            assert self.name == ISAMARU  # Do not illegally target protected Progenitus.
            self.main(self.seat)
            self.pay_cast(self.theft, {'target_card_id': self.old})
            assert self.state.cards[self.old].owner == 3-self.seat
            assert self.state.cards[self.old].controller == self.seat
        if self.rip:
            self.pay_cast(self.rip)
        self.before_second = snap(self.state)

    def save(self, tmp_path, receipts):
        (tmp_path / 'actual-episode.json').write_text(json.dumps({
            'seat': self.seat, 'name': self.name, 'foreign': self.foreign, 'replacement': self.replacement,
            'old': self.old, 'new': self.new, 'before_second': self.before_second, 'after': snap(self.state),
            'actions': self.trace, 'events': receipts}, default=str, indent=2))


def episode(seat, name, receipts, tmp_path, *, foreign=False, replacement=False, client=None, repo=None):
    h = Legend(seat, name, foreign, replacement, client, repo)
    h.first()
    h.state = restart(h.state, tmp_path, 'before-second-paid-cast')
    h.persist()
    receipts.clear()
    h.pay_cast(h.new)
    h.save(tmp_path, receipts)
    return h


def require_keeper(h):
    pending = h.state.pending_mechanic_choice or {}
    # Sole desired RED assertion: no literal new kind/schema contract assumed.
    assert (pending.get('player_id'), pending.get('count'), set(pending.get('options', [])),
            [h.state.cards[cid].zone for cid in [h.old, h.new]], bool(h.state.pending_replacement_choice)) == (
                h.seat, 1, {h.old, h.new}, [Zone.BATTLEFIELD, Zone.BATTLEFIELD], False), (
                'Human must choose a keeper before any legend departure/replacement; not fixed first policy')


def reject_without_mutation(h, actor, action):
    before = snap(h.state)
    if h.client:
        import main
        controls, sql = deepcopy(main._controller_snapshot(h.controller)), sql_facts(h.repo)
        result = h.client.post('/matches/' + h.state.id + '/action', json={'player_id': actor, 'action': action})
        assert result.status_code == 422, result.text
        assert (snap(h.controller.state), main._controller_snapshot(h.controller), sql_facts(h.repo)) == (before, controls, sql)
    else:
        with pytest.raises(ActionRejected):
            checked_action(h.state, RulesEngine(), actor, action)
        assert snap(h.state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('keep', ['older', 'newer'])
def test_human_deliberately_keeps_either_paid_legend(seat, name, keep, receipts, tmp_path):
    h = episode(seat, name, receipts, tmp_path)
    require_keeper(h)
    # Continuation acceptance contract below is NOT reached/qualified on baseline.
    keeper, loser = (h.old, h.new) if keep == 'older' else (h.new, h.old)
    h.state = restart(h.state, tmp_path, 'real-pending-keeper')
    reject_without_mutation(h, 3-seat, {'type': 'choose_mechanic', 'card_ids': [keeper]})
    reject_without_mutation(h, seat, {'type': 'choose_mechanic', 'card_ids': [keeper, keeper]})
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [keeper]})
    assert h.state.cards[keeper].zone == Zone.BATTLEFIELD
    assert h.state.cards[loser].zone != Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keep', ['older', 'newer'])
@pytest.mark.parametrize('destination', ['library', 'exile'])
def test_progenitus_destination_only_after_keeper_choice(seat, keep, destination, receipts, tmp_path):
    h = episode(seat, 'Progenitus', receipts, tmp_path, replacement=True)
    require_keeper(h)
    keeper, loser = (h.old, h.new) if keep == 'older' else (h.new, h.old)
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [keeper]})
    pending = h.state.pending_replacement_choice or {}
    assert pending.get('player_id') == seat
    assert h.state.cards[loser].zone == Zone.BATTLEFIELD
    assert {option['source_id'] for option in pending.get('options', [])} == {loser, h.rip}
    h.state = restart(h.state, tmp_path, 'actual-postkeeper-replacement')
    source = loser if destination == 'library' else h.rip
    reject_without_mutation(h, 3-seat, {'type': 'choose_replacement', 'replacement_source_id': source})
    h.act(seat, {'type': 'choose_replacement', 'replacement_source_id': source})
    assert h.state.cards[keeper].zone == Zone.BATTLEFIELD
    assert h.state.cards[loser].zone == (Zone.LIBRARY if destination == 'library' else Zone.EXILE)
    assert loser in getattr(h.state.players[h.state.cards[loser].owner], destination)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keep', ['older', 'newer'])
def test_actual_theft_legend_loser_routes_to_its_owner(seat, keep, receipts, tmp_path):
    h = episode(seat, ISAMARU, receipts, tmp_path, foreign=True)
    require_keeper(h)
    keeper, loser = (h.old, h.new) if keep == 'older' else (h.new, h.old)
    owner = h.state.cards[loser].owner
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [keeper]})
    assert h.state.cards[keeper].zone == Zone.BATTLEFIELD
    assert h.state.cards[loser].zone != Zone.BATTLEFIELD
    assert loser in (h.state.players[owner].graveyard + h.state.players[owner].library
                     + h.state.players[owner].exile)
    assert loser not in h.state.players[3-owner].graveyard + h.state.players[3-owner].library


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('keep', ['older', 'newer'])
def test_actual_http_pending_keeper_cold_private_atomic(repo, client, seat, name, keep, receipts, tmp_path):
    import main
    h = episode(seat, name, receipts, tmp_path, client=client, repo=repo)
    require_keeper(h)
    keeper = h.old if keep == 'older' else h.new
    expected = snap(h.state)
    main.ACTIVE_MATCHES.pop(h.state.id)
    assert client.get('/matches/' + h.state.id).status_code == 200
    h.controller = main.ACTIVE_MATCHES[h.state.id]
    h.state = h.controller.state
    assert snap(h.state) == expected
    h.state = restart(h.state, tmp_path, 'http-real-pending-keeper')
    h.persist()
    view, _ = decision_view(h.state, seat, [])
    assert all(is_unknown(view.cards[cid]) for cid in h.state.players[3-seat].library + h.state.players[3-seat].hand)
    reject_without_mutation(h, 3-seat, {'type': 'choose_mechanic', 'card_ids': [keeper]})
    reject_without_mutation(h, seat, {'type': 'choose_mechanic', 'card_ids': [keeper, keeper]})
    h.act(seat, {'type': 'choose_mechanic', 'card_ids': [keeper]})
    assert h.state.cards[keeper].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_single_real_paid_legend_has_no_keeper_prompt_and_correct_cast_body(seat, name, receipts, tmp_path):
    h = Legend(seat, name)
    h.first()
    h.state = restart(h.state, tmp_path, 'single-legend')
    assert h.state.cards[h.old].oracle_text == ROWS[name]['oracle_text']
    assert h.old in h.state.players[seat].battlefield
    assert not h.state.pending_mechanic_choice and not h.state.pending_replacement_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_act_of_treason_foreign_owner_control_is_real_without_duplicate(seat, receipts):
    h = Legend(seat, ISAMARU, foreign=True)
    h.first()
    assert h.state.cards[h.old].owner == 3-seat and h.state.cards[h.old].controller == seat
    assert h.state.cards[h.theft].zone == Zone.GRAVEYARD
    assert h.old in h.state.players[seat].battlefield
    assert not h.state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_progenitus_cannot_be_targeted_to_fabricate_foreign_control(seat, receipts):
    h = Legend(seat, 'Progenitus')
    h.first()
    theft = raw_card(h.state, ROWS['Act of Treason'], seat, Zone.HAND)
    h.state.players[seat].mana_pool = {'R': 1, 'C': 2}
    reject_without_mutation(h, seat, {'type': 'cast_spell', 'card_id': theft.id,
                                   'targets': {'target_card_id': h.old}})


def test_full_official_payload_integrity():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == '78fa7c5b27d788caaffaa9e3c7276c871aaca1901eab812f10df1596a0b02318'
    assert len(ROWS) == 6 and all(r['id'] and r['oracle_id'] for r in ROWS.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_separate_full_canonical_kozilek_cast_trigger_draws_four(seat, receipts, tmp_path):
    h = Legend(seat, KOZILEK)
    before = snap(h.state)
    hand_count = len(h.state.players[seat].hand)
    h.state.players[seat].mana_pool = {'C': 10}
    receipts.clear()
    h.act(seat, {'type': 'cast_spell', 'card_id': h.old, 'targets': {}})
    h.until(lambda: not h.state.stack)
    h.before_second = before
    h.save(tmp_path, receipts)
    assert h.state.cards[h.old].zone == Zone.BATTLEFIELD
    assert len(h.state.players[seat].hand) == hand_count - 1 + 4, 'Full canonical cast instruction is not an optional partial fixture'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_http_single_legend_invalid_actor_private_cold_controls(repo, client, seat, name, receipts, tmp_path):
    import main
    h = Legend(seat, name, client=client, repo=repo)
    h.first()
    h.state = restart(h.state, tmp_path, 'single-paid-public-http')
    h.persist()
    reject_without_mutation(h, 3-seat, {'type': 'cast_spell', 'card_id': h.new, 'targets': {}})
    reject_without_mutation(h, seat, {'type': 'choose_mechanic', 'card_ids': [h.old, h.old]})
    expected = snap(h.state)
    main.ACTIVE_MATCHES.pop(h.state.id)
    assert client.get('/matches/' + h.state.id).status_code == 200
    assert snap(main.ACTIVE_MATCHES[h.state.id].state) == expected
    view, _ = decision_view(main.ACTIVE_MATCHES[h.state.id].state, seat, [])
    assert all(is_unknown(view.cards[cid]) for cid in h.state.players[3-seat].library + h.state.players[3-seat].hand)
