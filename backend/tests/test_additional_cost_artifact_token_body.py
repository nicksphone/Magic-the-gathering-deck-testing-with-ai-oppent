"""Closed cost/draw/token bodies use real ordered effects, including resume."""
from contextlib import contextmanager
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot as snapshot
from game_state.state import CardInstance, Zone
from rules_engine.ability_model import build_spell_spec, spell_resolution_gaps
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.spell_cost_clauses import spell_additional_costs
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_additional_cost_draw_body as controls
from tests import test_death_cycle_ordering_audit as audit


ABILITIES = {
    'Treasure': '{T}, Sacrifice this token: Add one mana of any color.',
    'Blood': '{1}, {T}, Discard a card, Sacrifice this token: Draw a card.',
    'Food': '{2}, {T}, Sacrifice this token: You gain 3 life.',
}


def token_payload(name='Treasure', amount=1):
    return {'name': name, 'amount': amount, 'types': ['Artifact'],
            'type_line': 'Token Artifact \u2014 ' + name, 'oracle_text': ABILITIES[name],
            'power': None, 'toughness': None}


def sequence(name='Treasure', amount=1):
    return {'effects': [
        {'effect_key': 'draw_cards', 'payload': {'amount': 2}},
        {'effect_key': 'create_token', 'payload': token_payload(name, amount)}]}


def position(seat, fuel_name='Raging Goblin', mode='none', pause=False):
    state = audit.cards.position(seat)
    spell = controls.add(state, 'Deadly Dispute', seat)
    fuel = controls.add(state, fuel_name, seat, Zone.BATTLEFIELD)
    library = [controls.add(state, name, seat, Zone.LIBRARY).id for name in ('Island', 'Swamp')]
    witness = None
    if pause:
        # Explicit grammar witness, not a fabricated canonical card record.
        witness = CardInstance('dredge-control', 'Dredge witness', seat, seat,
                               Zone.GRAVEYARD, ['Creature'], oracle_text='Dredge 1')
        state.cards[witness.id] = witness
        state.players[seat].graveyard.append(witness.id)
    audit.replacement(state, seat, mode)
    state.players[seat].mana_pool = {'B': 1, 'C': 1}
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'cost_choice': {'id': 'base', 'sacrifice_card_ids': [fuel.id]}}
    return state, spell, fuel, library, action, witness


@contextmanager
def native_calls(monkeypatch, calls):
    import effects.handlers as handlers
    import effects.registry as registry
    import rules_engine.events as events
    import rules_engine.stack_engine as stack
    real = registry.resolve_effect

    def forward(state, controller, key, payload):
        calls.append({'effect_key': key, 'controller': controller,
                      'payload': deepcopy(payload), 'state_before': snapshot(state)})
        return real(state, controller, key, payload)

    with monkeypatch.context() as patch:
        patch.setattr(registry, 'resolve_effect', forward)
        patch.setattr(stack, 'resolve_effect', forward)
        patch.setattr(handlers, 'emit_event', events.emit_event)
        patch.setattr(handlers, 'emit_event_batch', events.emit_event_batch)
        yield


def assert_token(token, seat, name='Treasure'):
    assert (token.name, token.owner, token.controller, token.zone, token.is_token) == (
        name, seat, seat, Zone.BATTLEFIELD, True)
    assert token.types == ['Artifact'] and token.type_line == 'Token Artifact \u2014 ' + name
    assert token.oracle_text == ABILITIES[name]
    assert token.power is token.toughness is token.printed_power is token.printed_toughness is None
    assert token.colors == [] and token.keywords == [] and token.counters == {}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fuel_name', ['Raging Goblin', 'Sol Ring'])
@pytest.mark.parametrize('mode', audit.MODES)
def test_canonical_selected_cost_draws_before_native_treasure_with_full_publication_order(
        request, monkeypatch, seat, fuel_name, mode):
    state, spell, fuel, library, action, _ = position(seat, fuel_name, mode)
    before, records, calls = snapshot(state), [], []
    assert spell.oracle_text == controls.ROWS['Deadly Dispute']['oracle_text']
    assert spell_additional_costs(spell.oracle_text, spell.name) == [
        {'sacrifice_creatures': 1, 'sacrifice_kind': 'artifact_or_creature'}]
    option, = collect_cost_options(state, seat, spell)
    assert (option.id, option.mana_cost, option.sacrifice_creatures, option.discard_cards) == (
        'base', '{1}{B}', 1, 0)
    with controls.publications(monkeypatch, records), native_calls(monkeypatch, calls):
        paid = audit.restart(checked_action(state, RulesEngine(), seat, action))
        queued = snapshot(paid)
        assert resolve_top_of_stack(paid)
    audit.receipt(request, {'setup': before, 'action': action, 'queued': queued,
                            'publications': records, 'native_effect_calls': calls,
                            'resolved': snapshot(audit.restart(paid))})
    token, = audit.tokens(paid, seat)
    assert_token(token, seat)
    item, = queued['stack']
    assert item['effect_key'] == 'effect_sequence'
    assert {key: item['payload'][key] for key in ['effects']} == sequence()
    assert [call['effect_key'] for call in calls] == [
        'effect_sequence', 'draw_cards', 'create_token', 'create_token']
    assert all(call['controller'] == seat and call['payload']['__source_card_id'] == spell.id
               for call in calls)
    assert calls[2]['state_before']['players'][str(seat)]['hand'] == library[::-1]
    assert calls[2]['state_before']['draws_this_turn'][str(seat)] == 2
    assert '__entry_candidates' not in calls[2]['payload']
    assert [card['id'] for card in calls[3]['payload']['__entry_candidates']] == [token.id]
    assert calls[3]['payload']['__token_creation_modified'] is True
    expected = audit.destination(mode, seat, seat)
    cast_payload = {**sequence(), '__announced_stack_kind': 'spell',
                    '__announced_targets': {}, '__announced_target_references': {'targets': {}, 'version': 1},
                    '__granted_target_capture': {'captured': True, 'receipts': [], 'status': 'captured',
                                                 'target_refs': []},
                    '__kicked': False, '__ward_trigger_specs': [], 'mana_spent': 2,
                    'snow_mana_colors': {}, 'snow_mana_spent': 0}
    assert [(row['event'], row['payloads']) for row in records] == [
        ('leaves_battlefield', [{'card_id': fuel.id, 'controller': seat}]),
        *([('enters_graveyard', [controls.entry(fuel, seat, 'battlefield', 0, 1)])]
          if expected == Zone.GRAVEYARD else []),
        ('sacrifice', [{'card_id': fuel.id, 'controller': seat}]),
        ('permanent_dies', [{'card_id': fuel.id, 'controller': seat}]
         if expected == Zone.GRAVEYARD else []),
        ('creature_dies', [{'card_id': fuel.id, 'controller': seat}]
         if expected == Zone.GRAVEYARD and fuel_name == 'Raging Goblin' else []),
        ('spell_cast', [{'source_card_id': spell.id, 'source_stack_id': item['id'],
                         'controller': seat, 'label': 'Deadly Dispute', 'stack_payload': cast_payload}]),
        *[('draw_card', [{'player_id': seat, 'card_id': cid}]) for cid in library[::-1]],
        ('enters_battlefield', [{'card_id': token.id, 'controller': seat}]),
        *([('enters_graveyard', [controls.entry(spell, seat, 'stack', 1, 2)])]
          if expected == Zone.GRAVEYARD else [])]
    for row in records:
        public = row['state_at_event']
        if row['event'] == 'leaves_battlefield':
            assert public['cards'][fuel.id]['zone'] == 'battlefield'
            assert public['cards'][fuel.id]['zone_change_sequence'] == 0
            assert public['cards'][fuel.id]['last_known_battlefield'] == {}
            assert fuel.id in public['players'][str(seat)]['battlefield']
            assert fuel.id not in public['players'][str(seat)][expected.value]
        else:
            assert public['cards'][fuel.id]['zone'] == expected.value
            assert public['cards'][fuel.id]['zone_change_sequence'] == 1
            assert fuel.id not in public['players'][str(seat)]['battlefield']
            assert public['players'][str(seat)][expected.value].count(fuel.id) == 1
            assert public['cards'][fuel.id]['last_known_battlefield'] == paid.cards[fuel.id].last_known_battlefield
        if row['event'] == 'enters_battlefield':
            assert public['cards'][token.id]['zone'] == 'battlefield'
            assert public['players'][str(seat)]['hand'] == library[::-1]
            assert public['cards'][spell.id]['zone'] == 'stack'
    assert paid.cards[fuel.id].last_known_battlefield['name'] == fuel_name
    assert paid.cards[fuel.id].last_known_battlefield['types'] == (
        ['Creature'] if fuel_name == 'Raging Goblin' else ['Artifact'])
    assert paid.players[seat].hand == library[::-1] and paid.players[seat].library == []
    assert paid.players[seat].battlefield == [
        *[cid for cid in before['players'][str(seat)]['battlefield'] if cid != fuel.id], token.id]
    assert paid.players[seat].graveyard == ([fuel.id, spell.id] if expected == Zone.GRAVEYARD else [])
    assert paid.players[seat].exile == ([fuel.id, spell.id] if expected == Zone.EXILE else [])
    assert paid.draws_this_turn == {1: 2 if seat == 1 else 0, 2: 2 if seat == 2 else 0}
    assert paid.discards_this_turn == {1: 0, 2: 0}
    assert paid.players[seat].mana_pool == {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
    assert paid.players[seat].life == paid.players[3-seat].life == 20
    assert not paid.stack and paid.pending_mechanic_choice is None
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_treasure_waits_for_both_real_draw_choices_and_survives_resume_once(
        request, monkeypatch, seat):
    state, spell, fuel, library, action, witness = position(seat, pause=True)
    before, records, calls, pauses = snapshot(state), [], [], []
    with controls.publications(monkeypatch, records), native_calls(monkeypatch, calls):
        paid = audit.restart(checked_action(state, RulesEngine(), seat, action))
        queued = snapshot(paid)
        assert not resolve_top_of_stack(paid)
        for drawn in (0, 1):
            paid = audit.restart(paid)
            pauses.append(snapshot(paid))
            audit.receipt(request, {'setup': before, 'action': action, 'queued': queued,
                                    'pauses': pauses, 'publications': records,
                                    'native_effect_calls': calls, 'incomplete_resolution': True})
            pending = paid.pending_mechanic_choice
            assert pending['kind'] == 'draw' and pending['options'] == ['draw', witness.id]
            assert pending['player_id'] == seat and pending['continuation_controller'] == seat
            assert pending['resolving_item'] == queued['stack'][0]
            assert pending['draw_payload']['__source_card_id'] == spell.id
            assert pending['continuation_effects'] == [
                {'effect_key': 'create_token', 'payload': {**token_payload(), '__source_card_id': spell.id}}]
            assert paid.players[seat].hand == library[::-1][:drawn]
            assert paid.draws_this_turn[seat] == drawn and audit.tokens(paid, seat) == []
            assert paid.cards[spell.id].zone == Zone.STACK and not paid.stack
            paid = checked_action(paid, RulesEngine(), seat,
                                  {'type': 'choose_mechanic', 'choice_id': 'draw'})
    audit.receipt(request, {'setup': before, 'action': action, 'queued': queued, 'pauses': pauses,
                            'publications': records, 'native_effect_calls': calls,
                            'resolved': snapshot(audit.restart(paid))})
    token, = audit.tokens(paid, seat)
    assert_token(token, seat)
    cast_payload = {**sequence(), '__announced_stack_kind': 'spell',
                    '__announced_targets': {}, '__announced_target_references': {'targets': {}, 'version': 1},
                    '__granted_target_capture': {'captured': True, 'receipts': [], 'status': 'captured',
                                                 'target_refs': []},
                    '__kicked': False, '__ward_trigger_specs': [], 'mana_spent': 2,
                    'snow_mana_colors': {}, 'snow_mana_spent': 0}
    assert [(row['event'], row['payloads']) for row in records] == [
        ('leaves_battlefield', [{'card_id': fuel.id, 'controller': seat}]),
        ('enters_graveyard', [controls.entry(fuel, seat, 'battlefield', 0, 1)]),
        ('sacrifice', [{'card_id': fuel.id, 'controller': seat}]),
        ('permanent_dies', [{'card_id': fuel.id, 'controller': seat}]),
        ('creature_dies', [{'card_id': fuel.id, 'controller': seat}]),
        ('spell_cast', [{'source_card_id': spell.id, 'source_stack_id': queued['stack'][0]['id'],
                         'controller': seat, 'label': 'Deadly Dispute', 'stack_payload': cast_payload}]),
        *[('draw_card', [{'player_id': seat, 'card_id': cid}]) for cid in library[::-1]],
        ('enters_battlefield', [{'card_id': token.id, 'controller': seat}]),
        ('enters_graveyard', [controls.entry(spell, seat, 'stack', 1, 2)])]
    assert [call['effect_key'] for call in calls] == [
        'effect_sequence', 'draw_cards', 'effect_sequence', 'create_token', 'create_token']
    assert calls[0]['payload']['__source_card_id'] == spell.id
    assert calls[1]['payload']['__source_card_id'] == spell.id
    assert calls[-1]['controller'] == seat and calls[-1]['payload']['__source_card_id'] == spell.id
    assert paid.players[seat].hand == library[::-1] and not paid.players[seat].library
    assert paid.players[seat].graveyard == [witness.id, fuel.id, spell.id]
    assert paid.draws_this_turn[seat] == 2 and paid.discards_this_turn[seat] == 0
    assert paid.players[seat].mana_pool == {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
    assert not paid.stack and paid.pending_mechanic_choice is None
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Blood', 'Food', 'Treasure'])
@pytest.mark.parametrize('count,amount,reminder', [('a', 1, False), ('a', 1, True), ('two', 2, False), ('3', 3, False)])
def test_generic_template_body_not_card_name_compiles_and_resolves_complete_instructions(
        request, seat, name, count, amount, reminder):
    state, spell, fuel, library, action, _ = position(seat)
    spell.name = 'Generic artifact draw control'
    spell.oracle_text = ('As an additional cost to cast this spell, sacrifice an artifact or creature.\n'
                         f'Draw two cards and create {count} {name} token' + ('s' if amount > 1 else '') + '.')
    if reminder:
        spell.oracle_text += ' (It\'s an artifact with "' + ABILITIES[name] + '")'
    before = snapshot(state)
    preview = build_spell_spec(state, spell, seat, report_unsupported=False)
    assert (preview.effect.key, preview.effect.payload) == ('effect_sequence', sequence(name, amount))
    assert preview.unsupported_resolution == () and spell_resolution_gaps(spell) == ()
    paid = audit.restart(checked_action(state, RulesEngine(), seat, action))
    assert resolve_top_of_stack(paid)
    audit.receipt(request, {'setup': before, 'action': action, 'resolved': snapshot(audit.restart(paid))})
    tokens = audit.tokens(paid, seat)
    assert len(tokens) == amount and len({token.id for token in tokens}) == amount
    for token in tokens:
        assert_token(token, seat, name)
    assert paid.players[seat].hand == library[::-1] and paid.players[seat].graveyard == [fuel.id, spell.id]
    assert paid.draws_this_turn[seat] == 2 and paid.discards_this_turn[seat] == 0
    assert not paid.stack and paid.pending_mechanic_choice is None
    assert snapshot(state) == before


FAULTS = ['tail', 'same-clause', 'parenthetical', 'reminder-tail', 'unclosed',
          'nested', 'false-reminder', 'unknown-token', 'unknown-count', 'cost-tail',
          'leading', 'extra-period', 'quoted-instruction', 'plural-false-reminder']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', FAULTS)
def test_unknown_raw_body_rejects_atomically_without_cost_or_partial_reward(monkeypatch, seat, fault):
    state, spell, _, _, action, _ = position(seat)
    raw = spell.oracle_text
    variants = {
        'tail': raw + '\nPerform an unrecognized procedure.',
        'same-clause': raw.replace('Treasure token.', 'Treasure token and perform an unrecognized procedure.'),
        'parenthetical': raw + ' (Perform an unrecognized procedure.)',
        'reminder-tail': raw[:-1] + ' Perform an unrecognized procedure.)',
        'unclosed': raw[:-1],
        'nested': raw[:-1] + ' (Draw ten cards.))',
        'false-reminder': raw.replace('one mana of any color', 'ten mana of any color'),
        'unknown-token': raw.replace('Treasure token', 'Mystery token'),
        'unknown-count': raw.replace('a Treasure', 'several Treasure'),
        'cost-tail': raw.replace('artifact or creature.', 'artifact or creature and perform an unrecognized procedure.'),
        'leading': 'Perform an unrecognized procedure.\n' + raw,
        'extra-period': raw + '.',
        'quoted-instruction': raw.replace('Draw two cards', '"Draw two cards"'),
        'plural-false-reminder': raw.replace('a Treasure token.', 'two Treasure tokens.'),
    }
    spell.oracle_text = variants[fault]
    before, records, calls = snapshot(state), [], []
    key, payload = infer_effect_from_oracle(state, spell, seat, report_unsupported=False)
    assert key == 'noop' and payload.get('__unsupported_instruction')
    assert spell_resolution_gaps(spell)
    with controls.publications(monkeypatch, records), native_calls(monkeypatch, calls):
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, action)
    assert records == [] and calls == [] and snapshot(state) == before
