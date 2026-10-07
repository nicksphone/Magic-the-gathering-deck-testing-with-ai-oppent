"""Pure canonical production-body parity, not ASGI/live database acceptance."""
import ast
import json
import os
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from api_contracts import DeckPairInput
from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.sync import ScryfallSyncService
from fastapi import HTTPException
from game_state.state import Zone
from rules_engine.coverage import deck_pair_coverage, known_unsupported_mechanics
from rules_engine.oracle_effects import _infer_closed_damage_instruction, inspect_target_hints
from tests import test_soulscar_protection_boundaries as boundary

base, prior = boundary.base, boundary.prior


def record(label, **data):
    path = os.environ.get('MTG_PREFLIGHT_PARITY_RECEIPTS')
    if path:
        with open(path, 'a') as stream:
            stream.write(json.dumps({'label': label, **data}, sort_keys=True)+'\n')


class CanonicalReadAdapter:
    """Public committed cache records only, no database or fabricated card facts."""
    def __init__(self):
        self.reads = []
        self.rows = {}
        for name in ('Soul-Scar Mage', 'Healing Salve'):
            raw = base.CARDS[name]
            if raw.get('object') == 'card':
                data = ScryfallSyncService._normalize_payload(raw,
                    ScryfallSyncService._extract_remote_image_uri(raw))
            else:
                data = {**raw, 'colors': ','.join(raw['colors']), 'card_faces_json': '[]'}
            self.rows[name.casefold()] = SimpleNamespace(**deepcopy(data))

    def get_cached_cards_by_names(self, names):
        self.reads.append(list(names))
        return {name.casefold(): self.rows[name.casefold()] for name in names if name.casefold() in self.rows}

    def get_card_knowledge_by_names(self, names):
        return {}


def production_bodies():
    # Execute unchanged route/helper bodies without importing main or starting lifespan.
    source = Path(__file__).parents[1] / 'main.py'
    tree = ast.parse(source.read_text())
    wanted = {'_hydrate_deck_cards', '_validated_deck_cards', 'simulate_batch_preflight'}
    nodes = [deepcopy(node) for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    assert {node.name for node in nodes} == wanted
    for node in nodes:
        original = next(item for item in tree.body if getattr(item, 'name', None) == node.name)
        node.decorator_list = []
        assert ast.dump(ast.Module(body=node.body, type_ignores=[])) == ast.dump(
            ast.Module(body=original.body, type_ignores=[]))
    namespace = {'DeckPairInput': DeckPairInput, 'DeckEntry': object, 'Repository': object,
        'Depends': lambda provider: None, 'get_repo': None, 'HTTPException': HTTPException,
        'deck_pair_coverage': deck_pair_coverage}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 str(source), 'exec'), namespace)
    return namespace


def hydrated(name):
    repo = CanonicalReadAdapter()
    entries = [{'card_name': name, 'quantity': 1}]
    before = deepcopy(entries)
    result = hydrate_deck_cards(repo, entries)
    assert entries == before and repo.reads == [[name]]
    row = result[0]
    raw = base.CARDS[name]
    assert ready_for_match(row)
    for key in ('oracle_text', 'mana_cost', 'type_line'):
        assert row[key] == raw[key]
    return row


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Soul-Scar Mage', 'Healing Salve'])
def test_hydration_and_exact_preflight_body_are_canonical_root_pure(seat, name):
    repo = CanonicalReadAdapter()
    control = 'Healing Salve' if name == 'Soul-Scar Mage' else 'Soul-Scar Mage'
    decks = {'deck_a': [{'card_name': name, 'quantity': 1}],
             'deck_b': [{'card_name': control, 'quantity': 1}]}
    if seat == 2:
        decks['deck_a'], decks['deck_b'] = decks['deck_b'], decks['deck_a']
    payload = DeckPairInput.model_validate({**decks, 'sandbox': True})
    before = payload.model_dump()
    report = production_bodies()['simulate_batch_preflight'](payload, repo)
    assert payload.model_dump() == before
    row = hydrated(name)
    other = hydrated(control)
    expected = deck_pair_coverage([row] if seat == 1 else [other], [row] if seat == 2 else [other])
    assert report == expected and report['status'] == 'exploratory'
    record('production-preflight', seat=seat, name=name, response=report)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('damage_name,amount', [('Lightning Bolt', 3), ('Unholy Heat', 2)])
@pytest.mark.parametrize('first', ['conversion', 'prevention'])
def test_hydrated_paid_mage_salve_damage_orders_are_real_and_restorable(
        seat, damage_name, amount, first, monkeypatch):
    for name in ('Soul-Scar Mage', 'Healing Salve'):
        monkeypatch.setitem(base.CARDS, name, hydrated(name))
    state = base.position(seat)
    state = prior.paid_spell(state, 'Soul-Scar Mage', seat)
    mage = next(cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Soul-Scar Mage')
    target = base.add(state, 'Torrential Gearhulk', 3-seat)
    state = boundary.paid_prevention(state, seat, target, 'salve')
    assert len(state.numeric_prevention_shields) == 1
    receipt = state.numeric_prevention_shields[0]
    assert receipt.source_controller == 3-seat and receipt.remaining == 3
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    events = prior.observe_damage(monkeypatch)
    state, spell = base.cast(state, damage_name, seat, target)
    state = base.finish(prior.reload_exact(state))
    pending = state.pending_replacement_choice
    assert pending and pending['player_id'] == 3-seat
    offered = {row['source_id'] for row in pending['options']}
    other = 'numeric-prevention:' + receipt.receipt_id
    assert {mage, other} <= offered
    state = prior.choose(state, 3-seat, mage if first == 'conversion' else other)
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert not state.stack and not state.pending_replacement_choice
    assert state.cards[target].counters.get('-1/-1', 0) == (amount if first == 'conversion' else 0)
    assert state.numeric_prevention_shields[0].remaining == (3 if first == 'conversion' else 3-amount)
    assert not state.cards[target].counters.get('__damage_marked') and not events
    assert state.players[1].life == state.players[2].life == 20
    prior.reload_exact(state)
    report = deck_pair_coverage([hydrated('Soul-Scar Mage')], [hydrated('Healing Salve')])
    record('paid-engine-parity', seat=seat, damage=damage_name, first=first,
           response=report, pending_options=sorted(offered))


@pytest.mark.parametrize('seat', [1, 2])
def test_desired_mage_warning_does_not_claim_unsupported_counter_modifier(seat):
    row = hydrated('Soul-Scar Mage')
    gaps = known_unsupported_mechanics(row['oracle_text'], card_name=row['card_name'], canonical_context=row)
    record('mage-classification', seat=seat, gaps=gaps)
    assert 'unsupported counter replacement clause' not in gaps, (
        'Dedicated supported damage conversion must not be mislabeled as an unsupported counter modifier')


@pytest.mark.parametrize('family', ['prevention', 'conversion'])
@pytest.mark.parametrize('tail', [' Draw a card.', ' unless you control an Island.'])
def test_unknown_instruction_body_diagnostics_stay_honest(family, tail):
    # Fault-injection grammar inputs, NOT invented card Oracle/runtime episodes.
    raw = base.CARDS['Healing Salve' if family == 'prevention' else 'Soul-Scar Mage']['oracle_text']
    text = (raw.splitlines()[2].lstrip('\u2022 ') if family == 'prevention' else raw.splitlines()[1]) + tail
    gaps = known_unsupported_mechanics(text)
    if family == 'prevention':
        key, payload = _infer_closed_damage_instruction(text, 'Healing Salve', {'target_player': 2})
        assert key == 'noop' and '__unsupported_instruction' in payload
        record('unsupported-prevention-diagnostic', gaps=gaps, unsupported_payload=payload)
        assert gaps, 'Rejected closed-body suffix is invisible to preflight warning inventory'
    else:
        assert 'unsupported counter replacement clause' in gaps


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_salve_paid_gainlife_mode_preserved(seat, monkeypatch):
    monkeypatch.setitem(base.CARDS, 'Healing Salve', hydrated('Healing Salve'))
    state = base.position(seat)
    source = base.add(state, 'Healing Salve', seat, Zone.HAND)
    mode = next(mode for mode in inspect_target_hints(state, state.cards[source], seat)['modes']
                if mode.startswith('Target player gains'))
    state = prior.act(state, seat, {'type': 'cast_spell', 'card_id': source,
        'targets': {'mode_text': mode, 'target_player': 3-seat}})
    state = base.finish(prior.reload_exact(state))
    assert state.players[3-seat].life == 23 and state.players[seat].life == 20
    prior.reload_exact(state)
