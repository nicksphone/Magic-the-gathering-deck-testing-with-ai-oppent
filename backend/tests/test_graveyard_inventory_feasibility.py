"""Lower-bound queries are NOT an exhaustive graveyard-inertness certificate."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.alternative_casts import escape_cost, flashback_cost
from rules_engine.costs import collect_cost_options
from rules_engine.flashback_grants import granted_cost, resolve_grant
from rules_engine.graveyard_inventory import public_graveyard_inventory
from rules_engine.graveyard_permissions import (
    _clauses, _self_permission, ordinary_graveyard_cast, permission_gaps)
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.replacement import graveyard_entry_plans
from rules_engine.zone_actions import execute_graveyard_entry
from tests.test_empty_hand_attack_witness import ROWS, position, finish_combat
from tests.test_linked_damage_targets import raw_card
from tests.test_public_combat_boundary_audit import response_window


FIXTURES = Path(__file__).parent/'fixtures/graveyard_inventory_audit'
CARDS = {}
PROVENANCE = json.loads((FIXTURES/'provenance.json').read_text())
for entry in PROVENANCE['cards']:
    data = (FIXTURES/entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['id'] == entry['id']
    assert raw['oracle_id'] == entry['oracle_id'] and raw['name'] == entry['name']
    CARDS[raw['name']] = raw


def record(label, value):
    root = Path(os.environ['MTG_GY_INVENTORY_EVIDENCE'])
    root.mkdir(parents=True, exist_ok=True)
    with (root/(label+'.json')).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def queries(state, pid, card):
    """Record current query witnesses, never infer 'inert' from their emptiness."""
    return {'reference': {'id': card.id, 'owner': card.owner,
                         'zone': card.zone.value, 'incarnation': object_incarnation(card),
                         'zone_change_sequence': card.zone_change_sequence},
            'flashback': flashback_cost(card), 'escape': escape_cost(card),
            'ordinary_permission': ordinary_graveyard_cast(state, pid, card.id),
            'granted_flashback': granted_cost(state, card, pid),
            'cost_options': [option.id for option in collect_cost_options(state, pid, card)],
            'activated': extract_activated_abilities(card),
            'permission_gaps': permission_gaps(card.oracle_text, card.name)}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
def test_ordinary_spell_current_queries_do_not_yet_supply_inert_certificate(seat, family):
    state, source = position(seat, family, counter=True)
    grave = raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    agent = AIAgent(difficulty='master', archetype='Control')
    legal = agent.engine.legal_moves(state, seat)
    actor, visible = decision_view(state, seat, legal)
    observed = queries(actor, 3-seat, actor.cards[grave.id])
    assert not observed['cost_options'] and not observed['ordinary_permission']
    assert not observed['flashback'] and not observed['escape']
    assert not observed['activated'] and not observed['permission_gaps']
    for cid in actor.players[3-seat].library:
        assert not actor.cards[cid].name and not actor.cards[cid].oracle_text
    announced, _, responses = response_window(state, seat, source)
    public_announced, _ = decision_view(announced, seat, [])
    assert public_graveyard_inventory(public_announced, seat)['status'] == 'inert'
    assert agent._complete_strategic_combat_leaf(announced, seat) is not None
    attack = finish_combat(announced)
    assert attack.players[3-seat].life == 20-int(ROWS[family]['power'])
    assert attack.players[seat].hand == state.players[seat].hand
    decision = agent.choose_action(state, legal, seat)
    chosen = finish_combat(checked_action(state, agent.engine, seat, decision.action))
    assert serialize_match_snapshot(state) == before
    record(f'ordinary-{seat}-{family}', {'scope': 'funded retained canonical state; NOT natural/HTTP',
        'seed': 1972639901, 'snapshot': before, 'actor': serialize_match_snapshot(actor),
        'legal': legal, 'actor_legal': visible, 'queries': observed, 'responses': responses,
        'decision': decision.action, 'reasoning': decision.reasoning,
        'actual_attack': serialize_match_snapshot(attack), 'actual_chosen': serialize_match_snapshot(chosen),
        'classification': 'candidate stack-only clause; exhaustive positive inventory MISSING'})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('affordable', [False, True])
def test_printed_flashback_survives_price_veto_and_actual_paid_branch(seat, affordable):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, ROWS['Memory Deluge'], 3-seat, Zone.GRAVEYARD)
    for _ in range(2):
        raw_card(state, ROWS['Island'], 3-seat, Zone.BATTLEFIELD)
    if not affordable:
        for cid in state.players[3-seat].battlefield:
            state.cards[cid].tapped = True
    before = serialize_match_snapshot(state)
    announced, reply, legal = response_window(state, seat, source)
    observed = queries(reply, 3-seat, reply.cards[card.id])
    assert observed['flashback'] == '{5}{U}{U}'
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is None
    casts = [move for move in legal if move['type'] == 'cast_spell' and move['card_id'] == card.id]
    paid = None
    if affordable:
        action = AIAgent()._materialize_action(reply, casts[0], 3-seat)
        paid = checked_action(reply, AIAgent().engine, 3-seat, action)
        assert paid.cards[card.id].zone == Zone.STACK and paid.stack
        assert sum(paid.cards[cid].tapped for cid in paid.players[3-seat].battlefield) == 7
    else:
        assert not casts  # Price veto does not negate the positive printed hazard witness.
    assert serialize_match_snapshot(state) == before
    record(f'flashback-{seat}-{affordable}', {'snapshot': before, 'queries': observed,
        'legal': legal, 'paid': serialize_match_snapshot(paid) if paid else None,
        'classification': 'interactive printed permission regardless of current affordability'})


@pytest.mark.parametrize('seat', [1, 2])
def test_escape_is_a_hazard_even_outside_its_cast_timing(seat):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, CARDS['Woe Strider'], 3-seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    observed = queries(state, 3-seat, card)
    assert observed['escape'] == ('{3}{B}{B}', 4)
    announced, _, legal = response_window(state, seat, source)
    assert not any(move['type'] == 'cast_spell' and move['card_id'] == card.id for move in legal)
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is None
    assert serialize_match_snapshot(state) == before
    record(f'escape-{seat}', {'snapshot': before, 'queries': observed, 'legal': legal,
        'classification': 'positive printed hazard; no present creature-cast timing/fuel'})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zombie', [False, True])
def test_conditional_self_cast_permission_is_not_absent_when_condition_false(seat, zombie):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, CARDS['Gravecrawler'], 3-seat, Zone.GRAVEYARD)
    if zombie:
        raw_card(state, CARDS['Diregraf Ghoul'], 3-seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    assert any(_self_permission(clause, card.name) for clause in _clauses(card))
    observed = queries(state, 3-seat, card)
    assert observed['ordinary_permission'] == zombie
    assert serialize_match_snapshot(state) == before
    record(f'conditional-{seat}-{zombie}', {'snapshot': before, 'queries': observed,
        'classification': 'conditional printed permission; false condition is NOT missing ability'})


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_external_flashback_grant_then_real_checked_cast(seat):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    announced, reply, _ = response_window(state, seat, source)
    card = reply.cards[card.id]
    # Trusted existing resolved grant helper, NOT a claimed causal paid Snapcaster ETB.
    assert 'gains flashback until end of turn' in CARDS['Snapcaster Mage']['oracle_text']
    resolve_grant(reply, 3-seat, {'target_card_id': card.id, '__graveyard_reference': {
        'incarnation': object_incarnation(card), 'zone_sequence': card.zone_change_sequence}})
    before = serialize_match_snapshot(reply)
    observed = queries(reply, 3-seat, card)
    assert observed['granted_flashback'] == '{R}' and not observed['flashback']
    paid = checked_action(reply, AIAgent().engine, 3-seat, {'type': 'cast_spell',
        'card_id': card.id, 'from_graveyard': True, 'cost_choice': {'id': 'flashback'},
        'targets': {'target_card_id': source}})
    assert paid.cards[card.id].zone == Zone.STACK and paid.stack
    assert serialize_match_snapshot(reply) == before
    restarted = deserialize_match_snapshot(before)
    assert granted_cost(restarted, restarted.cards[card.id], 3-seat) == '{R}'
    restarted.turn += 1
    assert granted_cost(restarted, restarted.cards[card.id], 3-seat) is None
    public_announced, _ = decision_view(announced, seat, [])
    public_reply, _ = decision_view(reply, seat, [])
    assert public_graveyard_inventory(public_announced, seat)['status'] == 'inert'
    granted_inventory = public_graveyard_inventory(public_reply, seat)
    assert granted_inventory['status'] == 'unknown'
    assert granted_inventory['reason'] == 'uncovered source modification/metadata'
    assert granted_cost(public_reply, public_reply.cards[card.id], 3-seat) == '{R}'
    assert AIAgent()._complete_strategic_combat_leaf(announced, seat) is not None
    assert AIAgent()._complete_strategic_combat_leaf(reply, seat) is None
    assert serialize_match_snapshot(reply) == before
    record(f'external-{seat}', {'scope': 'trusted grant + actual paid Bolt, not causal Snapcaster episode',
        'snapshot': before, 'queries': observed, 'paid': serialize_match_snapshot(paid),
        'classification': 'object/turn-bound external grant; printed Bolt alone misses it'})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Darksteel Colossus', 'Kozilek, Butcher of Truth'])
def test_real_zone_executor_distinguishes_replacement_from_entry_trigger(seat, family):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, CARDS[family], 3-seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    plans = graveyard_entry_plans(state, card.id)
    assert len(plans) == 1 and serialize_match_snapshot(state) == before
    # Trusted core departure, not a paid discard/destroy episode or fabricated event.
    execute_graveyard_entry(state, plans[0])
    if family == 'Darksteel Colossus':
        assert card.zone == Zone.LIBRARY and card.id not in state.players[3-seat].graveyard
        assert not any(item.source_card_id == card.id for item in state.stack)
    else:
        assert card.zone == Zone.GRAVEYARD
        assert any(item.source_card_id == card.id and item.effect_key == 'shuffle_graveyard_into_library'
                   for item in state.stack)
    restarted = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_match_snapshot(restarted) == serialize_match_snapshot(state)
    record(f'entry-{seat}-{family}', {'scope': 'trusted shared executor; actual emitted receipt only',
        'before': before, 'after': serialize_match_snapshot(state),
        'classification': 'replacement prevents residence vs actual GR entry leaves pending trigger'})


@pytest.mark.parametrize('seat', [1, 2])
def test_desired_graveyard_activation_zone_is_not_battlefield(seat):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, CARDS['Reassembling Skeleton'], 3-seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    observed = queries(state, 3-seat, card)
    record(f'activation-{seat}', {'snapshot': before, 'queries': observed,
        'classification': 'canonical explicit GR-return activation; inventory MUST NOT certify inert'})
    assert serialize_match_snapshot(state) == before
    assert observed['activated'] and observed['activated'][0]['activation_zone'] == 'graveyard'


@pytest.mark.parametrize('seat', [1, 2])
def test_uncovered_trigger_and_external_grant_text_cannot_be_certified_by_cast_queries(seat):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    observations = {}
    for family in ['Nether Traitor', 'Past in Flames']:
        card = raw_card(state, CARDS[family], 3-seat, Zone.GRAVEYARD)
        before = serialize_match_snapshot(state)
        observations[family] = queries(state, 3-seat, card)
        assert serialize_match_snapshot(state) == before
    assert 'return this card from your graveyard' in CARDS['Nether Traitor']['oracle_text']
    assert 'gains flashback until end of turn' in CARDS['Past in Flames']['oracle_text']
    record(f'uncovered-{seat}', {'observations': observations,
        'classification': 'uncovered GR trigger / external all-card grant remain UNKNOWN; no negative certificate'})
