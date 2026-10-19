"""Real paid costs are not resolution instructions; raw unknown bodies reject."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot as snapshot
from game_state.state import CardInstance, Zone
from rules_engine.ability_model import build_spell_spec, spell_resolution_gaps
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.card_types import printed_card_types
from rules_engine.costs import collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.spell_cost_clauses import spell_additional_costs
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_death_cycle_ordering_audit as audit

HERE = Path(__file__).parent
FIXTURES = HERE / 'fixtures'
ROWS = dict(audit.cards.ROWS)
for filename in ('spell_additional_costs.json', 'linked_discard.json', 'qualified_spell_costs.json'):
    ROWS.update({row['name']: row for row in json.loads((FIXTURES / filename).read_bytes())})
SEED = json.loads((HERE.parent / 'card_data/builtin_oracle_seed.json').read_bytes())['cards']
for name in ('March of Otherworldly Light', 'Thoughtseize'):
    ROWS[name] = SEED[name]


def add(state, name, seat, zone=Zone.HAND):
    raw = ROWS[name]
    cid = f'p{seat}-{len(state.cards) + 1:03d}'

    def number(key):
        value = raw.get(key)
        return int(value) if value is not None and str(value).lstrip('-').isdigit() else None

    card = CardInstance(cid, name, seat, seat, zone,
                        printed_card_types(raw['type_line']), mana_cost=raw.get('mana_cost', ''),
                        oracle_text=raw.get('oracle_text', ''), type_line=raw['type_line'],
                        power=number('power'), toughness=number('toughness'),
                        colors=raw.get('colors'), keywords=list(raw.get('keywords') or []),
                        layout=raw.get('layout', ''), summoning_sick=False)
    state.cards[cid] = card
    getattr(state.players[seat], zone.value).append(cid)
    return card


@contextmanager
def publications(monkeypatch, records):
    import rules_engine.engine as engine
    import rules_engine.events as events
    import rules_engine.stack_engine as stack
    import rules_engine.zone_actions as zones
    single, batch = events.emit_event, events.emit_event_batch

    def observe(state, event, payloads, call):
        records.append({'event': event, 'payloads': deepcopy(payloads),
                        'state_at_event': snapshot(state),
                        'stack_at_event': [asdict(item) for item in state.stack]})
        return call()

    with monkeypatch.context() as patch:
        patch.setattr(events, 'emit_event', lambda state, event, payload:
                      observe(state, event, [payload], lambda: single(state, event, payload)))
        patch.setattr(events, 'emit_event_batch', lambda state, event, payloads:
                      observe(state, event, payloads, lambda: batch(state, event, payloads)))
        patch.setattr(engine, 'emit_event', events.emit_event)
        patch.setattr(engine, 'emit_event_batch', events.emit_event_batch)
        patch.setattr(stack, 'emit_event', events.emit_event)
        patch.setattr(zones, 'emit_event_batch', events.emit_event_batch)
        yield


def entry(card, seat, origin, before_sequence, after_sequence):
    return {'card_id': card.id, 'owner': seat, 'from_zone': origin,
            'previous_controller': seat,
            'previous_reference': {'incarnation': 0, 'zone_change_sequence': before_sequence},
            'entry_reference': {'incarnation': 0, 'zone_change_sequence': after_sequence}}


def draw_position(name, seat, mode='none'):
    state = audit.cards.position(seat)
    spell = add(state, name, seat)
    count, draws = (1, 2) if name == 'Tormenting Voice' else (2, 3)
    costs = [add(state, name, seat) for name in ('Island', 'Swamp')[:count]]
    spare = add(state, 'Forest', seat)
    opposing = [add(state, name, 3-seat) for name in ('Swamp', 'Raging Goblin')]
    library = [add(state, name, seat, Zone.LIBRARY).id
               for name in ('Forest', 'Raging Goblin', 'Island')[:draws]]
    audit.replacement(state, seat, mode)
    state.players[seat].mana_pool = {'C': 1, 'R': 1}
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'cost_choice': {'id': 'base', 'discard_card_ids': [card.id for card in costs]}}
    return state, spell, costs, spare, opposing, library, action, draws


def test_canonical_draw_cost_fixture_is_pinned_without_printed_fact_changes():
    assert hashlib.sha256((FIXTURES / 'spell_additional_costs.json').read_bytes()).hexdigest() == (
        '713a82dbf8e001d697d781baf6e9fd2e023d408cbfe39497a06b0c52d52c0c4b')
    assert ROWS['Tormenting Voice']['oracle_id'] == 'f307b5b4-e949-4f69-8dc7-856e33a45a16'
    assert ROWS['Cathartic Reunion']['oracle_id'] == '0f3c3e5f-6af3-4af2-8703-4ccc8ed8f675'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Tormenting Voice', 'Cathartic Reunion'])
@pytest.mark.parametrize('mode', audit.MODES)
def test_real_paid_discard_draw_has_no_cost_resolver_and_complete_receipt_order(
        request, monkeypatch, seat, name, mode):
    state, spell, costs, spare, opposing, library, action, draws = draw_position(name, seat, mode)
    before = snapshot(state)
    assert spell_additional_costs(spell.oracle_text, spell.name) == [{'discard_cards': len(costs)}]
    option, = collect_cost_options(state, seat, spell)
    assert (option.id, option.mana_cost, option.discard_cards) == ('base', '{1}{R}', len(costs))
    preview = build_spell_spec(state, spell, seat, report_unsupported=False)
    records = []
    with publications(monkeypatch, records), audit.cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
        queued = snapshot(audit.restart(paid))
        paid = audit.restart(paid)
        assert resolve_top_of_stack(paid)
    audit.receipt(request, {'setup': before, 'action': action, 'publications': records,
                            'queued': queued, 'resolved': snapshot(audit.restart(paid))})
    assert (preview.effect.key, preview.effect.payload) == ('draw_cards', {'amount': draws})
    assert preview.unsupported_resolution == ()
    item, = queued['stack']
    assert item['effect_key'] == 'draw_cards'
    assert item['payload']['amount'] == draws and 'effects' not in item['payload']
    expected = audit.destination(mode, seat, seat)
    cost_events = ([('enters_graveyard', [entry(card, seat, 'hand', 0, 1) for card in costs])]
                   if expected == Zone.GRAVEYARD else [])
    cast_payload = {'amount': draws, '__announced_stack_kind': 'spell',
                    '__announced_targets': {}, '__announced_target_references': {'targets': {}, 'version': 1},
                    '__granted_target_capture': {'captured': True, 'receipts': [], 'status': 'captured',
                                                 'target_refs': []},
                    '__kicked': False, '__ward_trigger_specs': [], 'mana_spent': 2,
                    'snow_mana_colors': {}, 'snow_mana_spent': 0}
    assert [(row['event'], row['payloads']) for row in records] == cost_events + [
        ('discard', [{'card_id': card.id, 'controller': seat} for card in costs]),
        ('spell_cast', [{'source_card_id': spell.id, 'source_stack_id': item['id'],
                         'controller': seat, 'label': name, 'stack_payload': cast_payload}]),
        *[('draw_card', [{'player_id': seat, 'card_id': cid}]) for cid in library[::-1]],
        *([('enters_graveyard', [entry(spell, seat, 'stack', 1, 2)])]
          if expected == Zone.GRAVEYARD else [])]
    for row in records:
        for card in costs:
            public = row['state_at_event']
            assert public['cards'][card.id]['zone'] == expected.value
            assert public['cards'][card.id]['zone_change_sequence'] == 1
            assert public['cards'][card.id]['last_known_battlefield'] == {}
            assert card.id not in public['players'][str(seat)]['hand']
            assert public['players'][str(seat)][expected.value].count(card.id) == 1
    assert paid.players[seat].hand == [spare.id, *library[::-1]]
    assert paid.players[3-seat].hand == [card.id for card in opposing]
    assert all(paid.cards[card.id].zone == Zone.HAND for card in opposing)
    assert not paid.players[seat].library and paid.draws_this_turn == {1: draws if seat == 1 else 0,
                                                                   2: draws if seat == 2 else 0}
    assert paid.discards_this_turn == {1: len(costs) if seat == 1 else 0,
                                      2: len(costs) if seat == 2 else 0}
    assert all(paid.cards[card.id].zone == expected for card in [*costs, spell])
    assert not paid.stack and paid.pending_mechanic_choice is None
    assert sum(paid.players[seat].mana_pool.values()) == 0
    assert paid.players[seat].life == paid.players[3-seat].life == 20
    assert snapshot(state) == before


FAULTS = ['sentence', 'same-clause', 'parenthetical', 'unclosed-parenthetical',
          'prefix', 'unknown-count', 'quoted-cost', 'malformed-cost', 'wrong-reference',
          'extra-period', 'cost-parenthetical', 'missing-cost-period']


def malformed(text, fault):
    if fault == 'sentence':
        return text + '\nPerform an unrecognized procedure.'
    if fault == 'same-clause':
        return text.rstrip('.') + ' and perform an unrecognized procedure.'
    if fault == 'parenthetical':
        return text + ' (Perform an unrecognized procedure.)'
    if fault == 'unclosed-parenthetical':
        return text + ' (Perform an unrecognized procedure.'
    if fault == 'prefix':
        return 'Perform an unrecognized procedure.\n' + text
    if fault == 'unknown-count':
        return text.replace('Draw two', 'Draw an unspecified number of').replace(
            'Draw three', 'Draw an unspecified number of')
    if fault == 'quoted-cost':
        return text + ' "As an additional cost to cast this spell, discard a card."'
    if fault == 'malformed-cost':
        return text.replace('card.', 'card and perform an unrecognized procedure.').replace(
            'cards.', 'cards and perform an unrecognized procedure.', 1)
    if fault == 'extra-period':
        return text + '.'
    if fault == 'cost-parenthetical':
        return text.replace('.\nDraw', ' (Perform an unrecognized procedure.).\nDraw', 1)
    if fault == 'missing-cost-period':
        return text.replace('.\nDraw', '\nDraw', 1)
    return text.replace('cast this spell', 'cast another spell')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Tormenting Voice', 'Cathartic Reunion'])
@pytest.mark.parametrize('fault', FAULTS)
def test_raw_unknown_body_rejects_without_partial_reward_or_payment(
        request, monkeypatch, seat, name, fault):
    state, spell, costs, _, _, _, action, _ = draw_position(name, seat)
    spell.oracle_text = malformed(spell.oracle_text, fault)
    before = snapshot(state)
    if fault not in ('malformed-cost', 'wrong-reference', 'quoted-cost', 'missing-cost-period'):
        assert spell_additional_costs(spell.oracle_text, spell.name) == [{'discard_cards': len(costs)}]
        option, = collect_cost_options(state, seat, spell)
        assert option.discard_cards == len(costs)
    records, rejected, result = [], False, None
    with publications(monkeypatch, records):
        try:
            result = checked_action(state, RulesEngine(), seat, action)
        except ActionRejected:
            rejected = True
    audit.receipt(request, {'setup': before, 'action': action, 'fault': fault,
                            'publications': records, 'rejected': rejected,
                            'result': snapshot(result) if result is not None else None})
    assert rejected
    assert records == [] and snapshot(state) == before
    assert spell_resolution_gaps(spell)
    spec = build_spell_spec(state, spell, seat, report_unsupported=False)
    assert spec.effect.key == 'noop' and spec.unsupported_resolution
    assert spec.effect.payload['__unsupported_instruction'] == spell.oracle_text
    assert not any(move['type'] == 'cast_spell' and move.get('card_id') == spell.id
                   for move in RulesEngine().legal_moves(state, seat))
    with publications(monkeypatch, records), pytest.raises(ActionRejected):
        RulesEngine().take_action(state, seat, action, reject_invalid=True)
    assert records == [] and snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cost,parsed', [
    ('discard a card', [{'discard_cards': 1}]),
    ('discard two cards', [{'discard_cards': 2}]),
    ('sacrifice a creature', [{'sacrifice_creatures': 1, 'sacrifice_kind': 'creature'}]),
    ('pay 2 life', [{'pay_life': 2}]),
    ('discard a card and pay 2 life', [{'discard_cards': 1, 'pay_life': 2}]),
    ('discard a card or pay 2 life', [{'discard_cards': 1}, {'pay_life': 2}]),
])
def test_cost_role_is_grammar_not_card_name_or_payment_kind(seat, cost, parsed):
    state = audit.cards.position(seat)
    card = add(state, 'Tormenting Voice', seat)
    card.name = 'Independent grammar specimen'
    card.oracle_text = f'As an additional cost to cast {card.name}, {cost}.\nDraw three cards.'
    assert spell_additional_costs(card.oracle_text, card.name) == parsed
    before = snapshot(state)
    assert infer_effect_from_oracle(state, card, seat, report_unsupported=False) == (
        'draw_cards', {'amount': 3})
    assert spell_resolution_gaps(card) == () and snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Dangerous Wager', 'Tolarian Winds', 'Thoughtseize'])
def test_real_non_cost_discard_spell_keeps_recipient_and_resolution_order(
        request, monkeypatch, seat, name):
    state = audit.cards.position(seat)
    spell = add(state, name, seat)
    held = [add(state, name, seat).id for name in ('Island', 'Swamp')]
    opposing = [add(state, name, 3-seat).id for name in ('Raging Goblin', 'Island')]
    library = [add(state, name, seat, Zone.LIBRARY).id for name in ('Forest', 'Raging Goblin')]
    state.players[seat].mana_pool = ({'B': 1} if name == 'Thoughtseize' else
                                   {'C': 1, 'U' if name == 'Tolarian Winds' else 'R': 1})
    action = {'type': 'cast_spell', 'card_id': spell.id,
              **({'targets': {'target_player': 3-seat}} if name == 'Thoughtseize' else {})}
    before, records = snapshot(state), []
    assert spell_additional_costs(spell.oracle_text, spell.name) == [{}]
    with publications(monkeypatch, records), audit.cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
        queued = snapshot(audit.restart(paid))
        paid = audit.restart(paid)
        assert resolve_top_of_stack(paid)
    audit.receipt(request, {'setup': before, 'action': action, 'publications': records,
                            'queued': queued, 'resolved': snapshot(paid)})
    if name == 'Thoughtseize':
        assert paid.players[seat].hand == held and paid.players[seat].library == library
        assert paid.players[3-seat].hand == opposing[1:]
        assert paid.players[3-seat].graveyard == opposing[:1]
        assert paid.players[seat].life == 18 and paid.draws_this_turn[seat] == 0
        assert [row['event'] for row in records] == [
            'spell_cast', 'enters_graveyard', 'discard', 'enters_graveyard']
    else:
        assert paid.players[seat].hand == library[::-1] and not paid.players[seat].library
        assert paid.players[seat].graveyard == held + [spell.id]
        assert paid.players[3-seat].hand == opposing and paid.draws_this_turn[seat] == 2
        assert paid.players[seat].life == 20
        assert [row['event'] for row in records] == [
            'spell_cast', 'enters_graveyard', 'discard', 'draw_card', 'draw_card', 'enters_graveyard']
    assert not paid.stack and paid.pending_mechanic_choice is None
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Deadly Dispute', 'Crop Rotation', 'Goblin Grenade'])
def test_canonical_other_cost_families_keep_paid_resolution(request, seat, name):
    state = audit.cards.position(seat)
    spell = add(state, name, seat)
    fuel = add(state, 'Forest' if name == 'Crop Rotation' else 'Raging Goblin', seat, Zone.BATTLEFIELD)
    library = [add(state, name, seat, Zone.LIBRARY).id
               for name in (('Island',) if name == 'Crop Rotation' else ('Island', 'Swamp'))]
    state.players[seat].mana_pool = ({'B': 1, **({'C': 1} if name == 'Deadly Dispute' else {})}
                                   if name in ('Village Rites', 'Deadly Dispute') else
                                   {'G' if name == 'Crop Rotation' else 'R': 1})
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'cost_choice': {'id': 'base', 'sacrifice_card_ids': [fuel.id]},
              **({'targets': {'target_player': 3-seat}} if name == 'Goblin Grenade' else {})}
    before = snapshot(state)
    option, = collect_cost_options(state, seat, spell)
    assert option.sacrifice_creatures == 1 and option.discard_cards == 0
    assert spell_resolution_gaps(spell) == ()
    with audit.cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    queued = snapshot(audit.restart(paid))
    assert paid.cards[fuel.id].zone == Zone.GRAVEYARD and not paid.players[seat].battlefield
    paid = audit.restart(paid)
    assert resolve_top_of_stack(paid)
    audit.receipt(request, {'setup': before, 'action': action, 'queued': queued, 'resolved': snapshot(paid)})
    if name in ('Village Rites', 'Deadly Dispute'):
        assert paid.players[seat].hand == library[::-1] and paid.draws_this_turn[seat] == 2
        if name == 'Deadly Dispute':
            token, = audit.tokens(paid, seat)
            assert token.name == 'Treasure' and token.types == ['Artifact']
        else:
            assert paid.players[seat].battlefield == []
    elif name == 'Crop Rotation':
        assert paid.players[seat].battlefield == library and not paid.players[seat].library
        assert paid.draws_this_turn[seat] == 0
    else:
        assert paid.players[3-seat].life == 15 and paid.draws_this_turn[seat] == 0
    assert paid.players[seat].graveyard == [fuel.id, spell.id]
    assert not paid.stack and paid.pending_mechanic_choice is None
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_complete_hand_exile_body_still_uses_real_paid_discount(request, seat):
    state = audit.cards.position(seat)
    spell = add(state, 'March of Otherworldly Light', seat)
    white = add(state, 'Rest in Peace', seat)
    target = add(state, 'Raging Goblin', 3-seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'W': 1, 'C': 1}
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'cost_choice': {'id': 'base', 'exile_card_ids': [white.id]},
              'targets': {'x_value': 1, 'target_card_id': target.id}}
    before = snapshot(state)
    assert spell_resolution_gaps(spell) == ()
    with audit.cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    queued = snapshot(audit.restart(paid))
    assert paid.cards[white.id].zone == Zone.EXILE
    assert paid.players[seat].mana_pool['W'] == 0 and paid.players[seat].mana_pool['C'] == 1
    assert paid.stack[0].effect_key == 'exile'
    paid = audit.restart(paid)
    assert resolve_top_of_stack(paid)
    audit.receipt(request, {'setup': before, 'action': action, 'queued': queued, 'resolved': snapshot(paid)})
    assert paid.cards[target.id].zone == Zone.EXILE and paid.cards[spell.id].zone == Zone.GRAVEYARD
    assert not paid.stack and snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_sacrifice_power_body_preserves_paid_context_not_a_draw_family(seat):
    state = audit.cards.position(seat)
    card = add(state, 'Village Rites', seat)
    card.name = 'Independent sacrifice specimen'
    card.oracle_text = ('As an additional cost to cast this spell, sacrifice a creature.\n'
                        f'{card.name} deals damage equal to the sacrificed creature\'s power to any target.')
    card.paid_cost_context = {'sacrificed_creatures': [{'power': 6}]}
    before = snapshot(state)
    assert infer_effect_from_oracle(state, card, seat, {'target_player': 3-seat},
                                    report_unsupported=False) == (
        'deal_damage', {'target_player': 3-seat, 'amount': 6})
    assert spell_resolution_gaps(card) == () and snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_multiple_cost_declarations_do_not_enter_ordered_draw_sequence(seat):
    state = audit.cards.position(seat)
    card = add(state, 'Tormenting Voice', seat)
    card.oracle_text = ('As an additional cost to cast this spell, discard a card.\n'
                        'As an additional cost to cast this spell, pay 2 life.\n'
                        'Draw a card. Draw three cards.')
    assert spell_additional_costs(card.oracle_text, card.name) == [{'discard_cards': 1, 'pay_life': 2}]
    before = snapshot(state)
    assert infer_effect_from_oracle(state, card, seat, report_unsupported=False) == (
        'effect_sequence', {'effects': [
            {'effect_key': 'draw_cards', 'payload': {'amount': 1}},
            {'effect_key': 'draw_cards', 'payload': {'amount': 3}}]})
    assert spell_resolution_gaps(card) == () and snapshot(state) == before
