"""Paid zero-loyalty and invalid-Aura SBA, no manufactured illegal permanent."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Zone
from rules_engine.continuous import effective_types
from tests.extra_sequence_support import position
from tests.test_combat_graveyard_caller_audit import Episode, receipts, client, base_client, repo
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import snap, restart
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts

FIXTURE = Path(__file__).parent / 'fixtures/noncreature_sba_caller/canonical.jsonl'
ROWS = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}


class Harness(Episode):
    def __init__(self, seat, family, replacement, client=None, repo=None):
        self.seat, self.family, self.replacement = seat, family, replacement
        self.client, self.repo, self.trace = client, repo, []
        self.state = position(seat)
        if client:
            import main
            for raw in [*ROWS.values()]:
                repo.upsert_card(normalize(raw))
            # The existing canonical initial-position helper supplies actual Islands.
            from tests.extra_sequence_support import RAW
            repo.upsert_card(normalize(RAW['Island']))
            deck = [{'card_name': 'Island', 'quantity': 60}]
            response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                                   'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7214})
            assert response.status_code == 200, response.text
            self.controller = main.ACTIVE_MATCHES[response.json()['id']]
            self.state.id = self.controller.state.id
        self.target = raw_card(self.state, ROWS['Jace Beleren' if family == 'walker' else 'Pacifism'], seat, Zone.HAND).id
        self.artist = raw_card(self.state, ROWS['Blood Artist'], seat, Zone.HAND).id
        self.rip = raw_card(self.state, ROWS['Rest in Peace'], seat, Zone.HAND).id if replacement else None
        self.bear = raw_card(self.state, ROWS['Grizzly Bears'], seat, Zone.HAND).id if family == 'aura' else None
        self.bounce = raw_card(self.state, ROWS['Unsummon'], seat, Zone.HAND).id if family == 'aura' else None
        self.persist()

    def setup(self):
        self.cast(self.artist)
        if self.rip:
            self.cast(self.rip)
        if self.bear:
            self.cast(self.bear)
        self.cast(self.target, {'target_card_id': self.bear} if self.bear else {})
        if self.family == 'walker':
            assert self.state.cards[self.target].loyalty == 3
            for _ in range(2):
                turn = self.state.turn
                self.act(self.seat, {'type': 'activate_loyalty', 'card_id': self.target,
                                    'ability_index': 1, 'targets': {'target_player': self.seat}})
                self.until(lambda: not self.state.stack)
                self.main(self.seat, turn)
            assert self.state.cards[self.target].loyalty == 1
            self.final_action = {'type': 'activate_loyalty', 'card_id': self.target,
                                 'ability_index': 1, 'targets': {'target_player': self.seat}}
        else:
            assert self.state.cards[self.target].attached_to == self.bear
            self.state.players[self.seat].mana_pool = {'U': 1}
            self.persist()
            self.final_action = {'type': 'cast_spell', 'card_id': self.bounce,
                                 'targets': {'target_card_id': self.bear}}
        self.before = snap(self.state)

    def depart(self):
        hand_count = len(self.state.players[self.seat].hand)
        self.act(self.seat, self.final_action)
        self.until(lambda: not self.state.stack)
        if self.family == 'walker':
            assert len(self.state.players[self.seat].hand) == hand_count + 1
        else:
            assert self.state.cards[self.bear].zone == Zone.HAND
        assert self.state.cards[self.artist].zone == Zone.BATTLEFIELD


def execute(seat, family, replacement, receipts, tmp_path, client=None, repo=None):
    h = Harness(seat, family, replacement, client, repo)
    h.setup()
    h.state = restart(h.state, tmp_path, 'before-departure')
    h.persist()
    receipts.clear()
    h.depart()
    (tmp_path / 'episode.json').write_text(json.dumps({
        'seat': seat, 'family': family, 'replacement': replacement, 'target': h.target,
        'before': h.before, 'after': snap(h.state), 'events': receipts,
        'actions': h.trace}, default=str, indent=2))
    h.state = restart(h.state, tmp_path, 'after-departure')
    return h


def assert_metric(h, receipts, metric):
    card = h.state.cards[h.target]
    assert card.zone == (Zone.EXILE if h.replacement else Zone.GRAVEYARD)
    assert h.target in getattr(h.state.players[card.owner], card.zone.value)
    assert h.target not in h.state.players[h.seat].battlefield
    own = [row for row in receipts if row['payload'].get('card_id') == h.target]
    previous = h.before['cards'][h.target]['zone_change_sequence']
    if metric == 'identity':
        assert card.zone_change_sequence == previous + 1
    elif metric == 'entry':
        rows = [row for row in own if row['event'] == 'enters_graveyard']
        assert len(rows) == (0 if h.replacement else 1)
        if rows:
            payload = rows[0]['payload']
            assert payload['from_zone'] == 'battlefield' and payload['owner'] == card.owner
            assert payload['previous_controller'] == h.seat
            assert payload['entry_reference']['zone_change_sequence'] == previous + 1
            assert payload['previous_reference']['zone_change_sequence'] == previous
    elif metric == 'lbf_lki':
        rows = [row for row in own if row['event'] == 'leaves_battlefield']
        assert len(rows) == 1, 'Unlawful Aura departure still needs real LBF/LKI capture'
        assert rows[0]['zone'] == 'battlefield'
        assert rows[0]['lki']['controller'] == h.seat
        assert rows[0]['lki']['name'] == card.name
        assert 'Creature' not in rows[0]['lki']['types']
    else:
        assert 'Creature' not in effective_types(h.state, card)
        assert not any(row['event'] == 'creature_dies' for row in own)
        assert not any(row['triggers'] for row in own if row['event'] in {'creature_dies', 'permanent_dies'})
        assert not any(item.source_card_id == h.artist for item in h.state.stack)
        assert all(player.life == 20 for player in h.state.players.values())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['walker', 'aura'])
@pytest.mark.parametrize('replacement', [False, True])
@pytest.mark.parametrize('metric', ['identity', 'entry', 'lbf_lki', 'creature_status'])
def test_actual_paid_noncreature_sba(seat, family, replacement, metric, receipts, tmp_path):
    h = execute(seat, family, replacement, receipts, tmp_path)
    assert_metric(h, receipts, metric)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['walker', 'aura'])
@pytest.mark.parametrize('replacement', [False, True])
def test_actual_http_noncreature_sba_cold_private_atomic(repo, client, seat, family, replacement, receipts, tmp_path):
    import main
    h = Harness(seat, family, replacement, client, repo)
    h.setup()
    before = snap(h.state), deepcopy(main._controller_snapshot(h.controller)), sql_facts(repo)
    response = client.post('/matches/' + h.state.id + '/action', json={
        'player_id': 3-seat, 'action': h.final_action})
    assert response.status_code == 422, response.text
    assert (snap(h.controller.state), main._controller_snapshot(h.controller), sql_facts(repo)) == before
    main.ACTIVE_MATCHES.pop(h.state.id)
    assert client.get('/matches/' + h.state.id).status_code == 200
    h.controller = main.ACTIVE_MATCHES[h.state.id]
    h.state = h.controller.state
    assert snap(h.state) == before[0]
    view, _ = decision_view(h.state, seat, [])
    assert all(is_unknown(view.cards[cid]) for cid in h.state.players[3-seat].library + h.state.players[3-seat].hand)
    receipts.clear()
    h.depart()
    expected = snap(h.state)
    (tmp_path / 'http-episode.json').write_text(json.dumps({
        'seat': seat, 'family': family, 'replacement': replacement, 'target': h.target,
        'before': h.before, 'after': expected, 'events': receipts, 'actions': h.trace}, default=str, indent=2))
    main.ACTIVE_MATCHES.pop(h.state.id)
    assert client.get('/matches/' + h.state.id).status_code == 200
    h.state = main.ACTIVE_MATCHES[h.state.id].state
    assert snap(h.state) == expected
    h.state = restart(h.state, tmp_path, 'http-restored')
    for metric in ['identity', 'entry', 'creature_status', 'lbf_lki']:
        assert_metric(h, receipts, metric)


def test_full_official_payload_integrity():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == '40c282d4e3cd1477814a46aaccd4510cb743a649f0cb550fe757ac94576af47d'
    assert len(ROWS) == 6 and all(row['id'] and row['oracle_id'] for row in ROWS.values())
