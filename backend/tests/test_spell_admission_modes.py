"""Actual canonical modes: selected misses cannot hide behind another mode."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pickle

import pytest
from game_state.state import MatchFactory, Zone
from rules_engine.ability_model import build_spell_spec
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.spell_admission_safety_support import position, add, resume

FIXTURE = Path(__file__).parent / 'fixtures/spell_admission_modes'
RAW = json.loads((FIXTURE / 'canonical.json').read_text())
GAIN, TOP, SHUFFLE, SEARCH = [line.removeprefix(chr(8226) + ' ').rstrip('.')
                             for line in RAW['oracle_text'].splitlines()[1:]]


def source(state, seat):
    sample = MatchFactory.from_decks([{**RAW, 'card_name': RAW['name'], 'quantity': 1}], [], seed=7214)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.HAND)
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    return card


def test_independent_full_modal_intake():
    proof = json.loads((FIXTURE / 'provenance.json').read_text())
    assert not proof['facts_modified'] and proof['intake_before_its_tests']
    assert proof['id'] == RAW['id'] and proof['oracle_id'] == RAW['oracle_id']
    assert proof['raw_sha256'] == hashlib.sha256(json.dumps(RAW,sort_keys=True,separators=(',',':')).encode()).hexdigest()


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('bad_mode',[TOP,SHUFFLE])
def test_selected_unrecognized_mode_rejects_whole_spell_before_any_payment(seat,bad_mode):
    state=position(seat)
    state.players[seat].mana_pool={'G':20,'C':20}
    card=source(state,seat)
    target=add(state,'Island',3-seat,Zone.BATTLEFIELD)
    targets={'mode_texts':[GAIN,bad_mode],'mode_targets':{
        GAIN:{'target_player':seat},
        bad_mode:({'target_card_id':target.id} if bad_mode==TOP else {'target_player':seat})}}
    before=pickle.dumps(state)
    with pytest.raises(ActionRejected,match='Unsupported spell resolution: unrecognized selected-mode resolution'):
        checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':card.id,'targets':targets})
    assert pickle.dumps(state)==before
    spec=build_spell_spec(resume(state),resume(state).cards[card.id],seat,targets,report_unsupported=False)
    assert spec.effect.key=='effect_sequence'
    assert 'unrecognized selected-mode resolution' in spec.unsupported_resolution
    # The direct strict entry point must also preserve the actual log and RNG.
    with pytest.raises(ActionRejected,match='Unsupported spell resolution: unrecognized selected-mode resolution'):
        RulesEngine().take_action(state,seat,{'type':'cast_spell','card_id':card.id,'targets':targets},reject_invalid=True)
    assert pickle.dumps(state)==before


@pytest.mark.parametrize('seat',[1,2])
def test_other_supported_modes_are_not_blanket_rejected(seat):
    state=position(seat)
    state.players[seat].mana_pool={'G':20,'C':20}
    card=source(state,seat)
    targets={'mode_texts':[GAIN,SEARCH],'mode_targets':{GAIN:{'target_player':seat},SEARCH:{}}}
    before=pickle.dumps(state)
    candidate=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':card.id,'targets':targets})
    assert pickle.dumps(state)==before
    assert not build_spell_spec(candidate,candidate.cards[card.id],seat,targets,report_unsupported=False).unsupported_resolution
    candidate=resume(candidate)
    resolve_top_of_stack(candidate)
    assert candidate.players[seat].life==27
    assert candidate.cards[card.id].zone==Zone.GRAVEYARD
    assert not candidate.pending_mechanic_choice
