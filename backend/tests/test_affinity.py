"""Canonical affinity cost, action, layer and snapshot regressions."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.affinity import affinity_clauses, apply_affinity
from rules_engine.hooks import CostContext, apply_cost_modifiers
from rules_engine.costs import collect_cost_options, check_cost_option_available
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.move_generator import legal_moves
from tests.test_announced_spell_costs import add, ROWS as TAXES
from tests.test_graveyard_play_permissions import position

FILE = Path(__file__).parent / 'fixtures/affinity/canonical.json'
ROWS = {row['name']: row for row in json.loads(FILE.read_text())['data']}
PERMANENTS = {row['name']: row for row in json.loads(FILE.with_name('permanents.json').read_text())['data']}


def setup(seat, name):
    state = position(seat)
    for player in state.players.values():
        player.mana_pool = {}
    return state, add(state, name, seat, Zone.HAND, cards=ROWS)


def view(state, card, **extra):
    return apply_cost_modifiers(CostContext(player_id=card.controller, card_name=card.name,
        mana_cost=card.mana_cost, state=state, spell_types=set(card.types),
        oracle_text=card.oracle_text, source_card_id=card.id, **extra))


def test_canonical_fixture_provenance():
    for file in (FILE, FILE.with_name('permanents.json')):
        provenance = json.loads(Path(str(file)+'.provenance.json').read_text())
        assert hashlib.sha256(file.read_bytes()).hexdigest() == provenance['sha256']
    assert len(ROWS) == 21


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Frogmite', 'Myr Enforcer', "Sojourner's Companion", 'Thoughtcast'])
def test_artifacts_count_controlled_permanents_not_hand_or_enemy(seat, name):
    state, card = setup(seat, name)
    for zone, owner in [(Zone.BATTLEFIELD,seat),(Zone.BATTLEFIELD,seat),
                        (Zone.HAND,seat),(Zone.GRAVEYARD,seat),(Zone.BATTLEFIELD,3-seat)]:
        add(state, 'Frogmite', owner, zone, cards=ROWS)
    assert view(state, card).generic_reduction == 2
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert view(restored, restored.cards[card.id]).generic_reduction == 2
    assert card.mana_cost == ROWS[name]['mana_cost']


@pytest.mark.parametrize('seat', [1, 2])
def test_free_cast_and_ai_legal_move_use_same_cost(seat):
    state, card = setup(seat, 'Frogmite')
    for _ in range(4):
        add(state, 'Myr Enforcer', seat, cards=ROWS)
    option, = collect_cost_options(state,seat,card)
    assert check_cost_option_available(state,seat,card,option)
    assert any(move.get('card_id') == card.id and move['type']=='cast_spell'
               for move in legal_moves(state,seat))
    before = serialize_match_snapshot(state)
    result = checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':card.id})
    assert result.cards[card.id].zone == Zone.STACK
    assert result.stack[-1].payload['mana_spent'] == 0
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_discount_never_pays_colored_requirement(seat):
    state, card = setup(seat,'Thoughtcast')
    for _ in range(7):
        add(state,'Frogmite',seat,cards=ROWS)
    option,=collect_cost_options(state,seat,card)
    assert not check_cost_option_available(state,seat,card,option)
    with pytest.raises(ActionRejected):
        checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':card.id})
    state.players[seat].mana_pool={'U':1}
    result=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':card.id})
    assert result.stack[-1].payload['mana_spent']==1


@pytest.mark.parametrize('seat',[1,2])
def test_static_grant_stacks_with_intrinsic_affinity_and_is_not_an_activation(seat):
    state, card=setup(seat,'Frogmite')
    grant=add(state,'Mycosynth Golem',seat,cards=ROWS)
    assert view(state,card).generic_reduction==2
    assert view(state,card,is_spell=False).generic_reduction==0
    grant.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].battlefield.remove(grant.id)
    state.players[seat].graveyard.append(grant.id)
    assert view(state,card).generic_reduction==0


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name,subtype',[('Razor Golem','Plains'),('Spire Golem','Island'),
    ('Dross Golem','Swamp'),('Oxidda Golem','Mountain'),('Tangle Golem','Forest')])
def test_each_basic_land_affinity_counts_lands_not_distinct_types(seat,name,subtype):
    state,card=setup(seat,name)
    for _ in range(3):
        cid=state.players[seat].library.pop()
        land=state.cards[cid]
        land.types=['Land']; land.type_line='Basic Land - '+subtype
        land.move_to_zone(Zone.BATTLEFIELD)
        state.players[seat].battlefield.append(cid)
    assert view(state,card).generic_reduction==3
    # A subtype label on a nonland does not qualify.
    state.cards[cid].types=['Creature']
    assert view(state,card).generic_reduction==2


@pytest.mark.parametrize('seat',[1,2])
def test_taxes_apply_before_reductions_without_changing_printed_cost(seat):
    state,card=setup(seat,'Thoughtcast')
    add(state,'Goblin Electromancer',seat,cards=TAXES)
    for _ in range(3):
        add(state,'Frogmite',seat,cards=ROWS)
    state.players[seat].mana_pool={'U':1}
    option,=collect_cost_options(state,seat,card)
    assert check_cost_option_available(state,seat,card,option)
    add(state,'Grand Arbiter Augustin IV',3-seat,cards=TAXES)
    assert not check_cost_option_available(state,seat,card,option)
    assert card.mana_cost=='{4}{U}'


@pytest.mark.parametrize('text',[
    'Whenever this creature attacks, the next spell you cast has affinity for artifacts.',
    'Affinity for tapped artifacts', 'Spells you cast have affinity for cards in your graveyard.'])
def test_unmodeled_affinity_surfaces_are_visible_not_partially_parsed(text):
    from rules_engine.coverage import known_unsupported_mechanics
    assert affinity_clauses(text)[2]
    assert 'unsupported affinity clause' in known_unsupported_mechanics(text)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name,subject,expected',[
    ('Gingerbrute','foods',True),('Gingerbrute','creatures',True),
    ('Basilisk Gate','gates',True),('Basilisk Gate','islands',False),
    ('Snow-Covered Forest','snow lands',True),('Snow-Covered Forest','forests',True),
    ('Hallowed Fountain','islands',True),('Hallowed Fountain','plains',True),
    ('Universal Automaton','elves',True),('Universal Automaton','frogs',True),
    ('Universal Automaton','outlaws',True),('Universal Automaton','artifact creatures',True),
    ('Llanowar Elves','elves',True),('Llanowar Elves','outlaws',False),
    ('Llanowar Elves','artifacts',False),('Bitterblossom','enchantments',True),
    ('Bitterblossom','faeries',True),("Urza's Saga",'historic permanents',True),
    ('Darksteel Citadel','historic permanents',True),
    ('Urborg, Tomb of Yawgmoth','historic permanents',True)])
def test_affinity_subjects_follow_actual_types_and_changeling(seat,name,subject,expected):
    from rules_engine.affinity import _matches, supported_subject
    state,_=setup(seat,'Frogmite')
    card=add(state,name,seat,cards=PERMANENTS)
    assert supported_subject(subject)
    assert bool(_matches(state,card,subject)) == expected


@pytest.mark.parametrize('seat',[1,2])
def test_land_affinity_follows_type_replacement_and_addition(seat):
    state,spell=setup(seat,'Spire Golem')
    add(state,'Hallowed Fountain',seat,cards=PERMANENTS)
    assert view(state,spell).generic_reduction==1
    moon=add(state,'Blood Moon',3-seat,cards=PERMANENTS)
    assert view(state,spell).generic_reduction==0
    swamp=add(state,'Dross Golem',seat,Zone.HAND,cards=ROWS)
    add(state,'Urborg, Tomb of Yawgmoth',seat,cards=PERMANENTS)
    assert view(state,swamp).generic_reduction==0  # Moon suppresses Urborg first.
    state.players[3-seat].battlefield.remove(moon.id)
    state.players[3-seat].graveyard.append(moon.id)
    moon.move_to_zone(Zone.GRAVEYARD)
    assert view(state,swamp).generic_reduction==2


@pytest.mark.parametrize('seat',[1,2])
def test_ability_loss_suppresses_grant_not_artifact_characteristic(seat):
    state,spell=setup(seat,'Frogmite')
    add(state,'Mycosynth Golem',seat,cards=ROWS)
    assert view(state,spell).generic_reduction==2
    add(state,'Humility',3-seat,cards=PERMANENTS)
    assert view(state,spell).generic_reduction==1


@pytest.mark.parametrize('seat',[1,2])
def test_added_artifact_type_counts_until_removal(seat):
    from rules_engine.type_effects import add_type_effect, clear_type_effects
    state,spell=setup(seat,'Frogmite')
    creature=add(state,'Llanowar Elves',seat,cards=PERMANENTS)
    assert view(state,spell).generic_reduction==0
    add_type_effect(state,creature.id,['Artifact'],until_end_of_turn=True)
    assert view(state,spell).generic_reduction==1
    clear_type_effects(creature)
    assert view(state,spell).generic_reduction==0


@pytest.mark.parametrize('seat',[1,2])
def test_count_is_locked_before_sacrificing_a_mana_source(seat):
    state,spell=setup(seat,'Thoughtcast')
    star=add(state,'Chromatic Star',seat,cards=PERMANENTS)
    for _ in range(3):
        add(state,'Frogmite',seat,cards=ROWS)
    state.players[seat].mana_pool={'C':1}
    option,=collect_cost_options(state,seat,spell)
    assert view(state,spell).generic_reduction==4
    assert check_cost_option_available(state,seat,spell,option)
    result=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':spell.id})
    assert result.cards[spell.id].zone==Zone.STACK
    assert result.cards[star.id].zone==Zone.GRAVEYARD
    assert not any(result.players[seat].mana_pool.values())
    # The spell was paid at four artifacts, even though only three remain now.
    assert view(result,result.cards[spell.id]).generic_reduction==3


@pytest.mark.parametrize('seat',[1,2])
def test_copied_creature_tokens_count_as_tokens_and_artifacts(seat):
    from effects.handlers import create_token_copy
    state,spell=setup(seat,'Junk Winder')
    source=add(state,'Frogmite',seat,cards=ROWS)
    assert view(state,spell).generic_reduction==0
    create_token_copy(state,seat,{'target_card_id':source.id})
    assert view(state,spell).generic_reduction==1
    copy=state.cards[state.players[seat].battlefield[-1]]
    assert copy.is_token and copy.name=='Frogmite'
    restored=deserialize_match_snapshot(serialize_match_snapshot(state))
    assert view(restored,restored.cards[spell.id]).generic_reduction==1


@pytest.mark.parametrize('seat',[1,2])
def test_grants_follow_announced_spell_types_and_caster_control(seat):
    state,spell=setup(seat,'Thoughtcast')
    add(state,'Mycosynth Golem',seat,cards=ROWS)
    # A sorcery has its own artifact affinity, not the artifact-creature grant.
    assert view(state,spell).generic_reduction==1
    balancer=add(state,'Witherbloom, the Balancer',seat,cards=ROWS)
    # The two creatures now also supply affinity for creatures to the sorcery.
    assert view(state,spell).generic_reduction==3
    state.players[seat].battlefield.remove(balancer.id)
    state.players[3-seat].battlefield.append(balancer.id)
    balancer.controller=3-seat
    assert view(state,spell).generic_reduction==1
