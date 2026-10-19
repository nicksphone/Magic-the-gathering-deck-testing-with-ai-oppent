"""Paid native copy provenance and complete counter/animation compatibility."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import StackItem, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.closed_loyalty import compile_body, compile_instruction
from rules_engine.continuous import effective_keywords, effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.targeting import stack_object_kind
from tests.extra_sequence_support import position
from tests.test_builtin_metadata_refresh import repo
from tests.test_canonical_jace_loyalty import JaceEpisode
from tests.test_combat_graveyard_caller_audit import Episode
from tests.test_counter_prohibitions import source as ban
from tests.test_counter_replacements import source as modifier
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import snap


FIX = Path(__file__).parent / 'fixtures'
ROWS = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_text())['cards']
for filename in ['permanent_spell_context.json', 'noncreature_sba_caller/canonical.jsonl']:
    text = (FIX / filename).read_text()
    records = list(map(json.loads, text.splitlines())) if filename.endswith('.jsonl') else json.loads(text)
    if isinstance(records, dict):
        records = records.values()
    ROWS.update({row['name']: row for row in records})
for filename in ['coupled_targets/twincast.json', 'archangel_pair/lithoform-engine.json']:
    row = json.loads((FIX / filename).read_text())
    ROWS[row['name']] = row


class PaidEpisode(Episode):
    restore_owned = JaceEpisode.restore_owned

    def __init__(self, seat):
        self.seat, self.client, self.repo, self.trace = seat, None, None, []
        self.state = position(seat)

    def add(self, name, zone=Zone.HAND):
        card = raw_card(self.state, ROWS[name], self.seat, zone)
        assert card.oracle_text == ROWS[name]['oracle_text']
        return card.id

    def paid(self, cid, pool, targets=None, *, activation=None):
        self.state.players[self.seat].mana_pool = dict(pool)
        action = {'type': 'cast_spell', 'card_id': cid, 'targets': targets or {}}
        if activation is not None:
            action.update(type='activate_ability', ability_index=activation)
        self.act(self.seat, action)
        assert not any(self.state.players[self.seat].mana_pool.values())
        frame = self.state.stack[-1]
        assert frame.source_card_id == cid
        assert stack_object_kind(self.state, frame) == ('spell' if activation is None else 'activated')
        assert frame.payload['__announced_targets'] == (targets or {})
        assert frame.payload['__announced_target_references']['version'] == 1
        if activation is None:
            assert frame.payload['mana_spent'] == sum(pool.values())
        else:
            assert self.state.cards[cid].tapped
            assert frame.payload['__activation_source_origin'] == 'battlefield'
            assert frame.payload['__activation_source_reference']['zone_change_sequence'] >= 1
        return frame.id

    def copied(self, copier_frame):
        for _ in range(16):
            if self.state.pending_mechanic_choice:
                choice = self.state.pending_mechanic_choice
                assert choice['kind'] == 'copy_target' and 'keep' in choice['options']
                self.act(choice['player_id'], {'type': 'choose_mechanic', 'card_ids': ['keep']})
            elif not any(item.id == copier_frame for item in self.state.stack):
                return self.state.stack[-1]
            else:
                self.act(self.state.priority_player, {'type': 'pass_priority'})
        pytest.fail('Paid copier did not finish its native publication')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['spell', 'permanent', 'activated', 'triggered'])
def test_checked_paid_copy_native_kind_references_and_sql_child_restore(seat, kind, repo, tmp_path):
    h = PaidEpisode(seat)
    engine = None
    if kind != 'spell':
        engine = h.add('Lithoform Engine')
        h.paid(engine, {'C': 4})
        h.until(lambda: not h.state.stack)
    if kind == 'spell':
        source = h.add('Lightning Bolt')
        original = h.paid(source, {'R': 1}, {'target_player': 3-seat})
        copier = h.add('Twincast')
        copier_pool, copier_index, expected_kind = {'U': 2}, None, 'spell'
    elif kind == 'permanent':
        source = h.add('Grizzly Bears')
        original = h.paid(source, {'G': 2})
        copier, copier_pool, copier_index, expected_kind = engine, {'C': 4}, 2, 'spell'
    elif kind == 'activated':
        source = h.add('Prodigal Pyromancer')
        h.paid(source, {'R': 3})
        h.until(lambda: not h.state.stack)
        h.main(seat, h.state.turn)
        original = h.paid(source, {}, {'target_player': 3-seat}, activation=0)
        copier, copier_pool, copier_index, expected_kind = engine, {'C': 2}, 0, 'activated'
    else:
        source = h.add('Soul Warden')
        h.paid(source, {'W': 1})
        h.until(lambda: not h.state.stack)
        bear = h.add('Grizzly Bears')
        h.paid(bear, {'G': 2})
        h.until(lambda: any(item.source_card_id == source for item in h.state.stack))
        frame = h.state.stack[-1]
        assert frame.payload['__trigger_event'] == 'enters_battlefield'
        assert h.state.cards[bear].zone == Zone.BATTLEFIELD
        original = frame.id
        copier, copier_pool, copier_index, expected_kind = engine, {'C': 2}, 0, 'triggered'
    original_payload = deepcopy(h.state.stack[-1].payload)
    assert stack_object_kind(h.state, h.state.stack[-1]) == expected_kind
    h.restore_owned(repo, tmp_path, 'paid-original')
    copier_frame = h.paid(copier, copier_pool, {'target_stack_id': original}, activation=copier_index)
    h.restore_owned(repo, tmp_path, 'paid-copier')
    copied = h.copied(copier_frame)
    assert copied.payload['__stack_copy_kind'] == expected_kind
    assert copied.payload['__copied_from_stack_id'] == original
    assert copied.source_card_id == source and copied.controller == seat
    assert next(item.payload for item in h.state.stack if item.id == original) == original_payload
    copied_id = copied.id
    h.restore_owned(repo, tmp_path, 'copied-frame')
    h.until(lambda: not any(item.id == copied_id for item in h.state.stack))
    if kind in {'spell', 'activated'}:
        amount = 3 if kind == 'spell' else 1
        assert h.state.players[3-seat].life == 20-amount
    elif kind == 'triggered':
        assert h.state.players[seat].life == 21
    else:
        tokens = [card for card in h.state.cards.values()
                  if card.name == 'Grizzly Bears' and card.is_token and card.zone == Zone.BATTLEFIELD]
        assert len(tokens) == 1 and tokens[0].power == tokens[0].toughness == 2
        assert h.state.cards[source].zone == Zone.STACK
    h.until(lambda: not h.state.stack)
    if kind in {'spell', 'activated'}:
        assert h.state.players[3-seat].life == 20-2*amount
    elif kind == 'triggered':
        assert h.state.players[seat].life == 22
    else:
        assert h.state.cards[source].zone == Zone.BATTLEFIELD and not h.state.cards[source].is_token
    assert h.state.cards[source].oracle_text == ROWS[h.state.cards[source].name]['oracle_text']
    assert not any(h.state.players[seat].mana_pool.values())
    h.restore_owned(repo, tmp_path, 'resolved-copies')
    (tmp_path / 'episode.json').write_text(json.dumps({'kind': kind, 'seat': seat,
        'actions': h.trace, 'after': snap(h.state)}, default=str))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', ['ordinary', 'counter-order', 'counter-ban'])
def test_complete_paid_nissa_native_counter_animation_resume(seat, variant, repo, tmp_path):
    h = PaidEpisode(seat)
    source = h.add('Nissa, Who Shakes the World')
    land = h.add('Forest', Zone.BATTLEFIELD)
    h.state.cards[land].tapped = True
    assert compile_body(h.state.cards[source].oracle_text, h.state.cards[source].name) is not None
    h.paid(source, {'G': 5})
    h.until(lambda: not h.state.stack)
    assert h.state.cards[source].loyalty == 5
    if variant == 'counter-order':
        # Declared canonical starting modifiers, not claims of paid modifier casts.
        modifier(h.state, 'Doubling Season', seat)
        modifier(h.state, 'Kami of Whispered Hopes', seat)
    elif variant == 'counter-ban':
        ban(h.state, 'Solemnity', seat)
    h.act(seat, {'type': 'activate_loyalty', 'card_id': source, 'ability_index': 0,
                 'targets': {'target_card_id': land}})
    assert h.state.stack[-1].effect_key == 'add_counters'
    assert h.state.stack[-1].payload['animate_land']
    assert h.state.stack[-1].payload['animate_untap']
    assert set(h.state.stack[-1].payload['animate_keywords']) == {'vigilance', 'haste'}
    h.restore_owned(repo, tmp_path, 'paid-nissa')
    choices = 0
    for _ in range(16):
        pending = h.state.pending_replacement_choice
        if pending:
            assert pending['event'] == 'counter_placement'
            assert pending['counter_effect'] == 'add_counters'
            assert pending['counter_payload']['target_card_id'] == land
            assert pending['counter_payload']['animate_land']
            assert h.state.cards[land].tapped and not h.state.cards[land].counters
            assert 'Creature' not in h.state.cards[land].types
            h.restore_owned(repo, tmp_path, 'counter-choice')
            option = next((option for option in pending['options'] if option['operation'] == 'double'),
                          pending['options'][0])
            h.act(pending['player_id'], {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
            choices += 1
        elif not h.state.stack:
            break
        else:
            h.act(h.state.priority_player, {'type': 'pass_priority'})
    assert not h.state.stack and not h.state.pending_replacement_choice
    assert choices == (1 if variant == 'counter-order' else 0)
    target = h.state.cards[land]
    if variant == 'counter-ban':
        assert target.zone == Zone.GRAVEYARD and target.counters.get('+1/+1', 0) == 0
        assert {'Land', 'Creature'}.issubset(target.last_known_battlefield['types'])
    else:
        amount = 7 if variant == 'counter-order' else 3
        assert target.counters['+1/+1'] == amount
        assert effective_power(h.state, land) == effective_toughness(h.state, land) == amount
        assert {'Land', 'Creature', 'Elemental'}.issubset(target.types)
        assert {'vigilance', 'haste'}.issubset(effective_keywords(h.state, land))
        assert not target.tapped
    assert h.state.cards[source].loyalty == 6
    assert h.state.cards[source].oracle_text == ROWS['Nissa, Who Shakes the World']['oracle_text']
    h.restore_owned(repo, tmp_path, 'resolved-nissa')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zone', [Zone.HAND, Zone.STACK, Zone.BATTLEFIELD])
def test_unknown_copy_frame_never_guesses_kind_from_source_zone(seat, zone):
    h = PaidEpisode(seat)
    source = h.add('Lightning Bolt', Zone.HAND if zone == Zone.STACK else zone)
    if zone == Zone.STACK:
        h.state.players[seat].hand.remove(source)
        h.state.cards[source].move_to_zone(Zone.STACK)
    h.state.stack.append(StackItem('legacy', source, seat, 'Unproven frame', 'deal_damage', {'amount': 3}))
    copier = h.add('Twincast')
    h.state.players[seat].mana_pool = {'U': 2}
    before = snap(h.state)
    assert stack_object_kind(h.state, h.state.stack[-1]) == 'legacy_unknown'
    assert inspect_target_hints(h.state, h.state.cards[copier], seat)['stack_targets'] == []
    with pytest.raises(ActionRejected):
        checked_action(h.state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': copier,
                       'targets': {'target_stack_id': 'legacy'}})
    assert snap(h.state) == before


@pytest.mark.parametrize('replacement', ['1/1 Elemental', '0/0 Treefolk',
                                       '0/0 Elemental creature with flying'])
def test_other_animation_parameters_keep_the_extended_executor(replacement):
    instruction = ROWS['Nissa, Who Shakes the World']['oracle_text'].splitlines()[1].split(': ', 1)[1]
    if 'creature with' in replacement:
        instruction = instruction.replace('0/0 Elemental creature with vigilance and haste', replacement)
    else:
        instruction = instruction.replace('0/0 Elemental', replacement)
    steps = compile_instruction(instruction, 'Unrelated Walker')
    assert [step['effect_key'] for step in steps] == ['loyalty_counter', 'loyalty_animate']


def test_counter_count_outside_native_grammar_keeps_extended_executor():
    instruction = ROWS['Nissa, Who Shakes the World']['oracle_text'].splitlines()[1].split(': ', 1)[1]
    steps = compile_instruction(instruction.replace('Put three', 'Put six'), 'Unrelated Walker')
    assert [step['effect_key'] for step in steps] == ['loyalty_counter', 'loyalty_animate']
    assert steps[0]['data']['amount'] == 6


def test_native_counter_animation_lowering_is_not_a_named_card_recipe():
    instruction = ROWS['Nissa, Who Shakes the World']['oracle_text'].splitlines()[1].split(': ', 1)[1]
    instruction = instruction.replace('Put three', 'Put two')
    assert compile_instruction(instruction, 'Unrelated Walker') == [
        {'effect_key': 'add_counters', 'instruction': instruction[:-1]}]


@pytest.mark.parametrize('suffix', [' Unknown instruction.', ' and draw a card.', ' (Unknown instruction.)'])
def test_complete_nissa_unknown_tail_is_atomic_before_payment(suffix):
    h = PaidEpisode(1)
    source = h.add('Nissa, Who Shakes the World')
    h.state.cards[source].oracle_text += suffix
    h.state.players[1].mana_pool = {'G': 5}
    before = snap(h.state)
    assert compile_body(h.state.cards[source].oracle_text, h.state.cards[source].name) is None
    with pytest.raises(ActionRejected, match='Unsupported spell resolution'):
        checked_action(h.state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source})
    assert snap(h.state) == before
