"""Real entry producers plus explicitly noncanonical clause-boundary controls."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine.events import _entry_observer_clause
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import locate, place, raw_card


EIDOLON = 'Eidolon of Blossoms'
HERE = Path(__file__).parent / 'fixtures/creature_observer_fix'
HUMILITY_SHA = 'eb68a098b4bd6de1d3c02afe60e37461a5c8268108132b0d3351119a50de8b49'


def canonical(name):
    if name != 'Humility':
        return raw_card(name)
    data = (HERE / 'humility.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == HUMILITY_SHA
    receipt = next(row for row in json.loads((HERE / 'provenance.json').read_bytes())['cards']
                   if row['name'] == name)
    assert receipt['sha256'] == HUMILITY_SHA and receipt['complete_raw_response_preserved']
    row = json.loads(data)
    assert row['name'] == name and row['object'] == 'card'
    return row


def board(first, second, active):
    def deck(names):
        counts = Counter(names)
        counts['Island'] += 60 - sum(counts.values())
        return [{**canonical(name), 'card_name': name, 'quantity': quantity}
                for name, quantity in counts.items() if quantity]

    state = MatchFactory.from_decks(deck(first), deck(second), seed=719)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = active
    state.step = Step.PRECOMBAT_MAIN
    return state


def cast(state, name, actor):
    cid = place(state, name, Zone.HAND, actor)
    state.players[actor].mana_pool.update(C=12, G=4, W=4, U=4)
    state = checked_action(state, RulesEngine(), actor,
                           {'type': 'cast_spell', 'card_id': cid})
    return state, cid


def enter(state, name, actor):
    state, cid = cast(state, name, actor)
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    return state, cid


def referred(state, source):
    return [item for item in state.stack if item.source_card_id == source]


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_canonical_self_entry_draws_once_from_the_real_spell(seat):
    state = board((EIDOLON,), (EIDOLON,), seat)
    state, cid = enter(state, EIDOLON, seat)
    assert state.cards[cid].oracle_text == canonical(EIDOLON)['oracle_text']
    assert len(referred(state, cid)) == 1
    assert referred(state, cid)[0].effect_key == 'draw_cards'
    before = len(state.players[seat].hand)
    assert resolve_top_of_stack(state)
    assert len(state.players[seat].hand) == before + 1 and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opposing_entry', [False, True])
@pytest.mark.parametrize('name', ['Oath of Nissa', 'Sol Ring', 'Grizzly Bears'])
def test_actual_other_entry_obeys_controller_and_printed_type(seat, opposing_entry, name):
    actor = 3 - seat if opposing_entry else seat
    state = board((EIDOLON, name), (EIDOLON, name), actor)
    source = place(state, EIDOLON, Zone.BATTLEFIELD, seat)
    state, entering = enter(state, name, actor)
    assert entering != source
    expected = int(name == 'Oath of Nissa' and actor == seat)
    assert len(referred(state, source)) == expected
    assert all(item.controller == seat for item in referred(state, source))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('self_entry', [False, True])
def test_full_humility_suppresses_the_creature_observer_at_real_entry(seat, self_entry):
    names = (EIDOLON, 'Humility', 'Oath of Nissa')
    state = board(names, names, seat)
    place(state, 'Humility', Zone.BATTLEFIELD, seat)
    source = (locate(state, EIDOLON, seat) if self_entry
              else place(state, EIDOLON, Zone.BATTLEFIELD, seat))
    state, _ = enter(state, EIDOLON if self_entry else 'Oath of Nissa', seat)
    assert printed_abilities_suppressed(state, source)
    assert referred(state, source) == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reference', ['this creature', EIDOLON])
@pytest.mark.parametrize('prefix', ['', 'Constellation \u2014 ', 'Renewal - '])
def test_explicit_selector_protocol_keeps_generic_prefix_and_exact_source_identity(
        seat, reference, prefix):
    state = board((EIDOLON, 'Oath of Nissa'), (EIDOLON, 'Oath of Nissa'), seat)
    source = place(state, EIDOLON, Zone.BATTLEFIELD, seat)
    # Deliberate parser vector, not a claim that this altered text is Oracle.
    state.cards[source].oracle_text = (
        prefix + 'Whenever ' + reference
        + ' or another enchantment you control enters, draw a card.')
    state, _ = enter(state, 'Oath of Nissa', seat)
    assert len(referred(state, source)) == 1
    assert referred(state, source)[0].effect_key == 'draw_cards'


@pytest.mark.parametrize('seat', [1, 2])
def test_wrong_named_source_reference_cannot_bind_to_this_observer(seat):
    state = board((EIDOLON, 'Oath of Nissa'), (EIDOLON, 'Oath of Nissa'), seat)
    source = place(state, EIDOLON, Zone.BATTLEFIELD, seat)
    state.cards[source].oracle_text = (
        'Whenever A Different Source or another enchantment you control enters, draw a card.')
    state, _ = enter(state, 'Oath of Nissa', seat)
    assert referred(state, source) == []


@pytest.mark.parametrize('seat', [1, 2])
def test_nontoken_protocol_excludes_an_actual_shark_but_accepts_real_creature_entry(seat):
    names = (EIDOLON, 'Shark Typhoon', 'Sol Ring', 'Grizzly Bears')
    state = board(names, names, seat)
    source = place(state, EIDOLON, Zone.BATTLEFIELD, seat)
    state.cards[source].oracle_text = (
        'Whenever this creature or another nontoken creature you control enters, draw a card.')
    shark = place(state, 'Shark Typhoon', Zone.BATTLEFIELD, seat)
    state, _ = cast(state, 'Sol Ring', seat)
    assert state.stack[-1].source_card_id == shark
    assert resolve_top_of_stack(state)
    assert any(card.is_token and card.controller == seat and card.zone == Zone.BATTLEFIELD
               for card in state.cards.values())
    assert referred(state, source) == []
    assert resolve_top_of_stack(state)
    state, _ = enter(state, 'Grizzly Bears', seat)
    assert len(referred(state, source)) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('body', [
    'draw a card. You gain 2 life.',
    'draw a card, then discard a card.',
    'if you control a Forest, draw a card.',
    'draw a card. If you control a Forest, gain 2 life.',
    'draw a card. (You lose the game.)',
    'you may draw a card.',
    'draw a card. This ability triggers only once each turn.',
])
def test_unknown_complete_bodies_never_execute_a_partial_draw(seat, body):
    state = board((EIDOLON, 'Oath of Nissa'), (EIDOLON, 'Oath of Nissa'), seat)
    source = place(state, EIDOLON, Zone.BATTLEFIELD, seat)
    state.cards[source].oracle_text = (
        'Constellation \u2014 Whenever this creature or another enchantment you control enters, ' + body)
    state, _ = enter(state, 'Oath of Nissa', seat)
    frames = referred(state, source)
    assert len(frames) == 1
    assert frames[0].effect_key == 'noop'
    assert frames[0].payload['__unsupported_trigger_instruction'] == body
    assert frames[0].payload['__trigger_full_clause'] == state.cards[source].oracle_text


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('body,key', [
    ('draw two cards.', 'draw_cards'),
    ('you gain 2 life.', 'gain_life'),
    ('each opponent mills a card.', 'mill_cards'),
])
def test_complete_instruction_protocol_uses_existing_native_compiler(seat, body, key):
    state = board((EIDOLON, 'Oath of Nissa'), (EIDOLON, 'Oath of Nissa'), seat)
    source = place(state, EIDOLON, Zone.BATTLEFIELD, seat)
    state.cards[source].oracle_text = (
        'Whenever this creature or another enchantment you control enters, ' + body)
    state, _ = enter(state, 'Oath of Nissa', seat)
    frames = referred(state, source)
    assert len(frames) == 1
    assert frames[0].effect_key == key
    assert '__unsupported_trigger_instruction' not in frames[0].payload


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('body', [
    'draw a card. (You lose the game.)',
    'you may draw a card.',
    'draw a card, then discard a card.',
])
def test_new_prefix_only_protocol_cannot_bypass_complete_body_guard(seat, body):
    state = board((EIDOLON, 'Oath of Nissa'), (EIDOLON, 'Oath of Nissa'), seat)
    source = place(state, EIDOLON, Zone.BATTLEFIELD, seat)
    state.cards[source].oracle_text = (
        'Constellation \u2014 Whenever an enchantment you control enters, ' + body)
    state, _ = enter(state, 'Oath of Nissa', seat)
    frames = referred(state, source)
    assert len(frames) == 1 and frames[0].effect_key == 'noop'
    assert frames[0].payload['__unsupported_trigger_instruction'] == body


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('adjacent', [False, True])
def test_unknown_raw_selector_parentheses_cannot_become_unconditional_reward(seat, adjacent):
    state = board((EIDOLON, 'Oath of Nissa'), (EIDOLON, 'Oath of Nissa'), seat)
    source = place(state, EIDOLON, Zone.BATTLEFIELD, seat)
    state.cards[source].oracle_text = (
        'Constellation \u2014 Whenever this creature' + ('' if adjacent else ' ')
        + '(only if you control a Forest) '
        'or another enchantment you control enters, draw a card.')
    state, _ = enter(state, 'Oath of Nissa', seat)
    frames = referred(state, source)
    assert len(frames) <= 1 and all(frame.effect_key == 'noop' for frame in frames)
    assert all(frame.payload['__unsupported_trigger_instruction'] == state.cards[source].oracle_text
               for frame in frames)


@pytest.mark.parametrize('text,groups', [
    ('Whenever a creature enters, draw a card.',
     ('a', 'creature', None, None, 'draw a card.')),
    ('Whenever another nontoken creature you control enters, draw a card.',
     ('another', 'nontoken creature', ' you control', None, 'draw a card.')),
    ('Whenever an artifact enters the battlefield under your control, you gain 2 life.',
     ('an', 'artifact', None, ' under your control', 'you gain 2 life.')),
])
def test_existing_clause_five_group_abi_is_exact(text, groups):
    clause = _entry_observer_clause(text)
    assert clause is not None and clause.groups() == groups and clause[5] == groups[4]
