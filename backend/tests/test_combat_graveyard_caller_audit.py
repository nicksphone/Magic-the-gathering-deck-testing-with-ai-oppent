"""Canonical paid setup and checked combat; no manufactured lethal marks."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone
from game_state.serializers import deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.continuous import has_keyword
from rules_engine import events
from tests.extra_sequence_support import position
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import snap, restart
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts

FIXTURE = Path(__file__).parent / 'fixtures/combat_graveyard_caller/canonical.jsonl'
ROWS = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}
MODES = ['ordinary', 'rip', 'humility']


@pytest.fixture
def client(base_client, repo, monkeypatch):
    import main
    monkeypatch.setattr(main, 'engine', repo.session.get_bind())
    return base_client


@pytest.fixture
def receipts(monkeypatch):
    result = []
    original = events._collect_triggers
    def observe(state, event, payload):
        triggers = original(state, event, payload)
        card = state.cards.get(payload.get('card_id'))
        result.append({'event': event, 'payload': deepcopy(payload),
                       'zone': card.zone.value if card else None,
                       'sequence': card.zone_change_sequence if card else None,
                       'lki': deepcopy(card.last_known_battlefield) if card else None,
                       'triggers': deepcopy(triggers)})
        return triggers
    monkeypatch.setattr(events, '_collect_triggers', observe)
    return result


class Episode:
    def __init__(self, seat, mode, foreign, client=None, repo=None):
        self.seat, self.mode, self.foreign = seat, mode, foreign
        self.client, self.repo = client, repo
        self.trace = []
        self.state = position(3-seat)
        self.traveler = raw_card(self.state, ROWS['Doomed Traveler'],
                                 3-seat if foreign else seat, Zone.HAND).id
        self.bear = raw_card(self.state, ROWS['Grizzly Bears'], 3-seat, Zone.HAND).id
        self.enchantment = (raw_card(self.state, ROWS['Rest in Peace' if mode == 'rip' else 'Humility'],
                                    seat, Zone.HAND).id if mode != 'ordinary' else None)
        self.theft = raw_card(self.state, ROWS['Act of Treason'], seat, Zone.HAND).id if foreign else None
        if client:
            import main
            for raw in ROWS.values():
                repo.upsert_card(normalize(raw))
            deck = [{'card_name': 'Island', 'quantity': 60}]
            response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                                   'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7214})
            assert response.status_code == 200, response.text
            self.controller = main.ACTIVE_MATCHES[response.json()['id']]
            self.state.id = self.controller.state.id
            self.persist()

    def persist(self):
        if self.client:
            import main
            self.controller.state = self.state
            main._persist_active_match(self.repo, self.controller)

    def act(self, actor, action):
        before = snap(self.state)
        if self.client:
            response = self.client.post('/matches/' + self.state.id + '/action',
                                        json={'player_id': actor, 'action': action})
            assert response.status_code == 200, response.text
            self.state = self.controller.state
        else:
            result = checked_action(self.state, RulesEngine(), actor, action)
            assert snap(self.state) == before, 'Checked action mutated the caller root'
            self.state = result
        self.trace.append({'actor': actor, 'action': deepcopy(action), 'turn': self.state.turn,
                           'step': self.state.step.value, 'stack': [vars(item) for item in self.state.stack]})

    def until(self, predicate):
        # A bounded harness, not a gameplay search cutoff.
        for _ in range(160):
            if predicate():
                return
            assert not self.state.pending_mechanic_choice and not self.state.pending_trigger_order
            assert self.state.winner is None
            self.act(self.state.priority_player, {'type': 'pass_priority'})
        pytest.fail('Checked progression did not reach the declared episode boundary')

    def main(self, seat, after_turn=None):
        self.until(lambda: self.state.active_player == seat and self.state.step == Step.PRECOMBAT_MAIN
                   and (after_turn is None or self.state.turn > after_turn) and not self.state.stack)

    def cast(self, cid, targets=None):
        seat = self.state.cards[cid].controller
        # Explicit funded fixture: no claim that mana was naturally accumulated.
        self.state.players[seat].mana_pool = {color: 10 for color in 'WUBRGC'}
        self.persist()
        self.act(seat, {'type': 'cast_spell', 'card_id': cid, 'targets': targets or {}})
        assert any(item.source_card_id == cid for item in self.state.stack)
        assert sum(self.state.players[seat].mana_pool.values()) < 60
        self.until(lambda: not self.state.stack)
        assert self.state.cards[cid].zone in {Zone.BATTLEFIELD, Zone.GRAVEYARD, Zone.EXILE}

    def setup(self):
        self.cast(self.bear)
        if self.foreign:
            self.cast(self.traveler)
        self.main(self.seat)
        if not self.foreign:
            self.cast(self.traveler)
        if self.enchantment:
            self.cast(self.enchantment)
        if self.foreign:
            self.cast(self.theft, {'target_card_id': self.traveler})
        else:
            turn = self.state.turn
            self.main(self.seat, turn)
        self.until(lambda: self.state.step == Step.DECLARE_ATTACKERS)
        assert self.state.cards[self.traveler].owner == (3-self.seat if self.foreign else self.seat)
        assert self.state.cards[self.traveler].controller == self.seat
        assert not self.state.cards[self.traveler].summoning_sick or self.foreign
        assert self.state.cards[self.traveler].counters.get('__damage_marked', 0) == 0
        self.before_combat = snap(self.state)

    def combat(self):
        self.act(self.seat, {'type': 'attack', 'attackers': [self.traveler],
                             'attack_targets': {self.traveler: 'player:' + str(3-self.seat)}})
        self.until(lambda: self.state.step == Step.DECLARE_BLOCKERS)
        self.act(3-self.seat, {'type': 'block', 'blocks': {self.traveler: [self.bear]}})
        assert self.state.blocks == {self.traveler: [self.bear]}
        self.until(lambda: self.state.step == Step.COMBAT_DAMAGE)
        assert self.state.cards[self.traveler].zone != Zone.BATTLEFIELD

    def save(self, path, receipts):
        data = {'seat': self.seat, 'mode': self.mode, 'foreign': self.foreign,
                'before_combat': self.before_combat, 'after_damage': snap(self.state),
                'checked_actions': self.trace, 'events': receipts}
        path.write_text(json.dumps(data, default=str, indent=2))


def run(seat, mode, foreign, receipts, tmp_path, client=None, repo=None):
    episode = Episode(seat, mode, foreign, client, repo)
    episode.setup()
    episode.state = restart(episode.state, tmp_path, 'before-combat')
    episode.persist()
    receipts.clear()
    episode.combat()
    episode.save(tmp_path / 'episode.json', receipts)
    episode.state = restart(episode.state, tmp_path, 'after-damage')
    return episode


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('metric', ['sequence', 'entry', 'dies_lki'])
def test_checked_combat_death_receipts(seat, mode, foreign, metric, receipts, tmp_path):
    episode = run(seat, mode, foreign, receipts, tmp_path)
    card = episode.state.cards[episode.traveler]
    previous = episode.before_combat['cards'][episode.traveler]['zone_change_sequence']
    own_events = [row for row in receipts if row['payload'].get('card_id') == card.id]
    assert card.zone == (Zone.EXILE if mode == 'rip' else Zone.GRAVEYARD)
    assert card.id in getattr(episode.state.players[card.owner], card.zone.value)
    assert card.id not in episode.state.players[episode.seat].battlefield
    if metric == 'sequence':
        assert card.zone_change_sequence == previous + 1, 'Actual combat death must use a proper zone transition'
    elif metric == 'entry':
        entries = [row for row in own_events if row['event'] == 'enters_graveyard']
        assert len(entries) == (0 if mode == 'rip' else 1), 'Only actual graveyard entry emits a receipt'
        if entries:
            assert entries[0]['payload']['owner'] == card.owner
            assert entries[0]['payload']['previous_controller'] == episode.seat
            assert entries[0]['payload']['entry_reference']['zone_change_sequence'] == previous + 1
    else:
        deaths = [row for row in own_events if row['event'] == 'creature_dies']
        assert len(deaths) == (0 if mode == 'rip' else 1)
        if deaths:
            assert deaths[0]['lki']['controller'] == episode.seat
            assert deaths[0]['lki']['printed_abilities_suppressed'] == (mode == 'humility')
        own_stack = [item for item in episode.state.stack if item.source_card_id == card.id]
        assert len(own_stack) == (1 if mode == 'ordinary' else 0)
        episode.until(lambda: not episode.state.stack)
        spirits = [episode.state.cards[cid] for cid in episode.state.players[episode.seat].battlefield
                   if episode.state.cards[cid].name == 'Spirit']
        assert len(spirits) == (1 if mode == 'ordinary' else 0)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', MODES)
def test_actual_http_combat_cold_resume_and_private_atomicity(repo, client, seat, mode, receipts, tmp_path):
    import main
    episode = Episode(seat, mode, True, client, repo)
    episode.setup()
    before = snap(episode.state), deepcopy(main._controller_snapshot(episode.controller)), sql_facts(repo)
    rejected = client.post('/matches/' + episode.state.id + '/action', json={
        'player_id': 3-seat, 'action': {'type': 'attack', 'attackers': [episode.traveler]}})
    assert rejected.status_code == 422, rejected.text
    assert (snap(episode.controller.state), main._controller_snapshot(episode.controller), sql_facts(repo)) == before
    expected = snap(episode.state)
    main.ACTIVE_MATCHES.pop(episode.state.id)
    response = client.get('/matches/' + episode.state.id)
    assert response.status_code == 200, response.text
    episode.controller = main.ACTIVE_MATCHES[episode.state.id]
    episode.state = episode.controller.state
    assert snap(episode.state) == expected
    view, _ = decision_view(episode.state, seat, [])
    for cid in episode.state.players[3-seat].library + episode.state.players[3-seat].hand:
        assert is_unknown(view.cards[cid])
    receipts.clear()
    episode.combat()
    episode.save(tmp_path / 'http-episode.json', receipts)
    expected = snap(episode.state)
    main.ACTIVE_MATCHES.pop(episode.state.id)
    assert client.get('/matches/' + episode.state.id).status_code == 200
    loaded = main.ACTIVE_MATCHES[episode.state.id]
    assert snap(loaded.state) == expected
    loaded.state = restart(loaded.state, tmp_path, 'persisted-combat')
    prior = episode.before_combat['cards'][episode.traveler]['zone_change_sequence']
    assert loaded.state.cards[episode.traveler].zone_change_sequence == prior + 1


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_shadowspear_deathtouch_combat_owner_replacement(seat, tmp_path, receipts):
    episode = Episode(seat, 'ordinary', False)
    spear = raw_card(episode.state, ROWS['Shadowspear'], 3-seat, Zone.HAND)
    episode.traveler = raw_card(episode.state, ROWS['Darksteel Colossus'], seat, Zone.HAND).id
    episode.bear = raw_card(episode.state, ROWS['Deadly Recluse'], 3-seat, Zone.HAND).id
    episode.cast(episode.bear)
    episode.cast(spear.id)
    episode.main(seat)
    episode.cast(episode.traveler)
    episode.main(seat, episode.state.turn)
    episode.until(lambda: episode.state.step == Step.BEGIN_COMBAT)
    assert has_keyword(episode.state, episode.traveler, 'indestructible')
    episode.act(seat, {'type': 'pass_priority'})
    episode.state.players[3-seat].mana_pool = {'C': 1}
    episode.act(3-seat, {'type': 'activate_ability', 'card_id': spear.id,
                         'ability_index': 0, 'targets': {}})
    assert episode.state.players[3-seat].mana_pool['C'] == 0
    episode.until(lambda: not episode.state.stack)
    assert not has_keyword(episode.state, episode.traveler, 'indestructible')
    assert has_keyword(episode.state, episode.bear, 'deathtouch')
    episode.until(lambda: episode.state.step == Step.DECLARE_ATTACKERS)
    episode.before_combat = snap(episode.state)
    episode.state = restart(episode.state, tmp_path, 'shadowspear-resolved')
    assert not has_keyword(episode.state, episode.traveler, 'indestructible')
    receipts.clear()
    episode.combat()
    episode.save(tmp_path / 'colossus-paid-combat.json', receipts)
    card = episode.state.cards[episode.traveler]
    assert card.oracle_text == ROWS['Darksteel Colossus']['oracle_text']
    assert card.zone == Zone.LIBRARY, 'Actual supported keyword removal must preserve printed self replacement'
    assert card.id in episode.state.players[seat].library
    assert not any(row['event'] in {'creature_dies', 'enters_graveyard'}
                   and row['payload'].get('card_id') == card.id for row in receipts)


def test_canonical_payload_integrity():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == '27ce324c7811574f1334776ccdf561aeaaf87a410019c55a856315409ed0cc6e'
    assert len(ROWS) == 10
    assert all(row['id'] and row['oracle_id'] for row in ROWS.values())
