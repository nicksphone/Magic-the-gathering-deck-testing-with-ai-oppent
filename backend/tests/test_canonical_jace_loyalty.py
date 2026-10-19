"""Complete canonical loyalty body, real paid costs, and owned persistence."""
from copy import copy
import json

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.ability_model import build_ability_spec, spell_resolution_gaps
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.closed_loyalty import compile_body, compile_instruction
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_loyalty_abilities
from tests.extra_sequence_support import position
from tests.test_builtin_metadata_refresh import repo
from tests.test_combat_graveyard_caller_audit import Episode
from tests.test_linked_damage_targets import raw_card
from tests.test_noncreature_sba_caller_audit import ROWS
from tests.test_self_graveyard_replacement_audit import restart, snap


RAW = ROWS['Jace Beleren']
BODIES = ['Each player draws a card.', 'Target player draws a card.',
          'Target player mills twenty cards.']


class JaceEpisode(Episode):
    def __init__(self, seat):
        self.seat, self.client, self.repo, self.trace = seat, None, None, []
        self.state = position(seat)
        self.source = raw_card(self.state, RAW, seat, Zone.HAND).id
        assert self.state.cards[self.source].oracle_text == RAW['oracle_text']

    def paid_cast(self):
        self.state.players[self.seat].mana_pool = {'U': 2, 'C': 1}
        self.act(self.seat, {'type': 'cast_spell', 'card_id': self.source})
        assert not any(self.state.players[self.seat].mana_pool.values())
        frame = self.state.stack[-1]
        assert frame.source_card_id == self.source and frame.payload['mana_spent'] == 3
        assert self.state.cards[self.source].zone == Zone.STACK

    def activate(self, index, targets=None):
        self.act(self.seat, {'type': 'activate_loyalty', 'card_id': self.source,
                            'ability_index': index, 'targets': targets or {}})

    def charge_ultimate(self):
        for _ in range(4):
            turn = self.state.turn
            self.activate(0)
            self.until(lambda: not self.state.stack)
            self.main(self.seat, turn)
        assert self.state.cards[self.source].loyalty == 11

    def restore_owned(self, repo, tmp_path, label):
        before = snap(self.state)
        repo.save_active_match(self.state.id, json.dumps(before), '{}')
        repo.session.expire_all()
        saved = repo.get_active_match(self.state.id)
        assert json.loads(saved.state_json) == before
        self.state = restart(deserialize_match_snapshot(json.loads(saved.state_json)),
                             tmp_path, label)
        assert snap(self.state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('index,recipient', [(0, 'each'), (1, 'own'), (1, 'opponent'),
                                           (2, 'own'), (2, 'opponent')])
def test_paid_complete_body_all_recipients_across_sql_and_child_restore(
        seat, index, recipient, repo, tmp_path):
    h = JaceEpisode(seat)
    before = snap(h.state)
    assert spell_resolution_gaps(h.state.cards[h.source]) == ()
    assert [ability['text'] for ability in extract_loyalty_abilities(h.state.cards[h.source])] == BODIES
    assert snap(h.state) == before
    h.paid_cast()
    h.restore_owned(repo, tmp_path, 'paid-cast')
    h.until(lambda: not h.state.stack)
    assert h.state.cards[h.source].loyalty == 3
    assert h.state.cards[h.source].zone == Zone.BATTLEFIELD
    h.restore_owned(repo, tmp_path, 'resolved-cast')
    if index == 2:
        h.charge_ultimate()
    target = seat if recipient == 'own' else 3-seat
    libraries = {pid: list(player.library) for pid, player in h.state.players.items()}
    hands = {pid: list(player.hand) for pid, player in h.state.players.items()}
    graves = {pid: list(player.graveyard) for pid, player in h.state.players.items()}
    loyalty = h.state.cards[h.source].loyalty
    sequences = {cid: h.state.cards[cid].zone_change_sequence
                 for player in h.state.players.values() for cid in player.library}
    h.activate(index, {} if index == 0 else {'target_player': target})
    assert h.state.cards[h.source].loyalty == loyalty + [2, -1, -10][index]
    assert h.source in h.state.loyalty_activated_this_turn
    assert {pid: player.library for pid, player in h.state.players.items()} == libraries
    frame = h.state.stack[-1]
    assert frame.source_card_id == h.source and frame.controller == seat
    if index == 0:
        assert frame.effect_key == 'effect_sequence'
        assert frame.payload['effects'] == [
            {'effect_key': 'draw_cards', 'payload': {'target_player': seat, 'amount': 1}},
            {'effect_key': 'draw_cards', 'payload': {'target_player': 3-seat, 'amount': 1}},
        ]
    else:
        assert frame.effect_key == ('draw_cards' if index == 1 else 'mill_cards')
        assert frame.payload['target_player'] == target
        assert frame.payload['amount'] == (1 if index == 1 else 20)
        assert frame.payload['__announced_targets'] == {'target_player': target}
    h.restore_owned(repo, tmp_path, 'paid-loyalty')
    before = snap(h.state)
    with pytest.raises(ActionRejected):
        checked_action(h.state, RulesEngine(), seat, {
            'type': 'activate_loyalty', 'card_id': h.source, 'ability_index': 0})
    assert snap(h.state) == before
    h.until(lambda: not h.state.stack)
    for pid, player in h.state.players.items():
        affected = index == 0 or pid == target
        amount = (20 if index == 2 else 1) if affected else 0
        moved = list(reversed(libraries[pid][-amount:])) if amount else []
        assert player.library == (libraries[pid][:-amount] if amount else libraries[pid])
        assert player.hand == hands[pid] + (moved if index != 2 else [])
        assert player.graveyard == graves[pid] + (moved if index == 2 else [])
        for cid in moved:
            assert h.state.cards[cid].zone == (Zone.GRAVEYARD if index == 2 else Zone.HAND)
            assert h.state.cards[cid].zone_change_sequence == sequences[cid] + 1
    assert h.state.winner is None and not h.state.failed_draw_players
    assert h.state.cards[h.source].oracle_text == RAW['oracle_text']
    h.restore_owned(repo, tmp_path, 'resolved-loyalty')
    (tmp_path / 'episode.json').write_text(json.dumps({'seat': seat, 'index': index,
        'recipient': recipient, 'actions': h.trace, 'after': snap(h.state)}, default=str))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('index', [1, 2])
def test_paid_targeted_loyalty_requires_announcement_before_any_cost(seat, index):
    h = JaceEpisode(seat)
    h.paid_cast()
    h.until(lambda: not h.state.stack)
    if index == 2:
        h.charge_ultimate()
    proxy = copy(h.state.cards[h.source])
    proxy.types = []
    proxy.oracle_text = BODIES[index]
    before = snap(h.state)
    preview = build_ability_spec(h.state, proxy, seat, report_unsupported=False)
    assert preview.target_hints['player_targets']
    if index == 2:
        assert preview.effect.key == 'mill_cards'
        assert preview.effect.payload == {'target_player': None, 'amount': 20}
    assert snap(h.state) == before
    for targets in ({}, {'target_player': None}, {'target_player': 0},
                    {'target_player': 3}, {'target_card_id': h.source}):
        with pytest.raises(ActionRejected):
            checked_action(h.state, RulesEngine(), seat, {
                'type': 'activate_loyalty', 'card_id': h.source,
                'ability_index': index, 'targets': targets})
        assert snap(h.state) == before


@pytest.mark.parametrize('index', [0, 1, 2])
@pytest.mark.parametrize('suffix', [' Unknown instruction.', ' and draw a card.',
    ' (Unknown instruction.)', '; draw a card.',
    ' Target player draws a card. Target player mills twenty cards.'])
def test_unknown_suffix_or_compound_rejects_entire_body_before_paid_cast(index, suffix):
    h = JaceEpisode(1)
    lines = RAW['oracle_text'].splitlines()
    lines[index] += suffix
    card = h.state.cards[h.source]
    card.oracle_text = '\n'.join(lines)
    h.state.players[1].mana_pool = {'U': 2, 'C': 1}
    before = snap(h.state)
    assert compile_instruction(lines[index].split(': ', 1)[1], card.name) is None
    assert compile_body(card.oracle_text, card.name) is None
    assert extract_loyalty_abilities(card) == []
    assert spell_resolution_gaps(card)
    with pytest.raises(ActionRejected, match='Unsupported spell resolution'):
        checked_action(h.state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': card.id})
    assert snap(h.state) == before


def test_full_body_grammar_is_not_named_or_fixed_to_printed_costs():
    h = JaceEpisode(1)
    source = h.state.cards[h.source]
    source.name = 'Independent loyalty specimen'
    source.oracle_text = '+4: Each player draws a card.\n-3: Target player draws a card.\n-7: Target player mills 20 cards.'
    abilities = extract_loyalty_abilities(source)
    assert [ability['delta'] for ability in abilities] == [4, -3, -7]
    assert [ability['text'] for ability in abilities] == [*BODIES[:2], 'Target player mills 20 cards.']
