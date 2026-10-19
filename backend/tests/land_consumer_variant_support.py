"""Full unchanged canonical fixtures for exactly two land consumer families."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

from api_contracts import LandAction
from game_state.state import MatchState, PlayerState, Step, Zone
from rules_engine.engine import RulesEngine
from tests.test_linked_damage_targets import raw_card
from tests.test_private_choice_intent_boundary import environment

ENGINE = RulesEngine()
VARIANTS = ('shock_tapped', 'shock_pay', 'crucible', 'ramunap')
FIXTURES = Path(__file__).parent / 'fixtures'


def rows():
    path = FIXTURES / 'contextual_cost_prohibitions/sacred-foundry.json'
    provenance = next(x for x in json.loads((path.parent / 'provenance.json').read_text()) if x['name'] == 'Sacred Foundry')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance['sha256']
    shock = json.loads(path.read_text())
    path = FIXTURES / 'graveyard_permissions/canonical.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == json.loads((path.parent / 'provenance.json').read_text())['sha256']
    data = {x['name']: x for x in json.loads(path.read_text())['data']}
    selected = {name: data[name] for name in ('Forest', 'Crucible of Worlds', 'Ramunap Excavator')}
    selected['Sacred Foundry'] = shock
    for row in selected.values():
        assert row['oracle_id'] and row['uri'].startswith('https://api.scryfall.com/cards/') and row['oracle_text']
    return selected


def setup(variant, seat, life=20):
    assert variant in VARIANTS and seat in (1, 2)
    raw = rows()
    state = MatchState(id='canonical-land-consumer', cards={}, stack=[], players={
        pid: PlayerState(id=pid, name=f'P{pid}') for pid in (1, 2)})
    state.rng = random.Random(813)
    state.pregame_pending = False; state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat; state.step = Step.PRECOMBAT_MAIN
    state.players[seat].life = life
    foreign = raw_card(state, raw['Forest'], 3-seat, Zone.HAND).id
    unseen = [raw_card(state, raw['Forest'], seat, Zone.LIBRARY).id for _ in range(2)]
    for _ in range(2):
        raw_card(state, raw['Forest'], 3-seat, Zone.LIBRARY)
    source = None
    if variant.startswith('shock'):
        first = raw_card(state, raw['Sacred Foundry'], seat, Zone.HAND)
        land = raw_card(state, raw['Sacred Foundry'], seat, Zone.HAND)
        choice = 'pay_two_life' if variant == 'shock_pay' else 'tapped'
        action = {'type': 'play_land', 'card_id': land.id, 'from_exile': False,
                  'from_graveyard': False, 'entry_choice': choice}
    else:
        name = 'Crucible of Worlds' if variant == 'crucible' else 'Ramunap Excavator'
        source = raw_card(state, raw[name], seat, Zone.BATTLEFIELD).id
        first = raw_card(state, raw['Forest'], seat, Zone.GRAVEYARD)
        land = raw_card(state, raw['Forest'], seat, Zone.GRAVEYARD)
        action = {'type': 'play_land', 'card_id': land.id, 'from_exile': False,
                  'from_graveyard': True}
    available = [m for m in ENGINE.legal_moves(deepcopy(state), seat)
                 if m['type'] == 'play_land' and m['card_id'] == land.id]
    hint = next((m for m in available if m.get('entry_choice') == action.get('entry_choice')), None)
    if hint:
        assert LandAction.model_validate({k: v for k, v in hint.items() if k in LandAction.model_fields}).model_dump(exclude_none=True) == action
    return environment(state), action, hint, {'first': first.id, 'land': land.id, 'grant': source,
                                             'foreign_hand': foreign, 'unseen': unseen}
