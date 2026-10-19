"""Selected-card callback ABI and canonical hand-exile wire views, not paid-rule proof."""
import json
from pathlib import Path
import pytest
from game_state.state import MatchFactory, Step
from game_state.serializers import serialize_match_snapshot
from rules_engine.card_faces import select_cast_face
from rules_engine.costs import CostOption, collect_cost_options
from rules_engine import casting_resources, cast_choice, kicker, move_generator
from tests.modal_contract_support import canonical_fixture

@pytest.mark.parametrize('face_kind', ['', 'adventure'])
@pytest.mark.parametrize('boundary', ['resources', 'kicker', 'x_hints'])
def test_selected_card_callback_protocol(face_kind, boundary, monkeypatch):
    state = canonical_fixture(face_kind)
    source = state.cards[state.players[2].hand[0]]
    face = select_cast_face(source, 1)
    before = serialize_match_snapshot(state)
    seen = []
    option = CostOption('base', 'Base Cost', '{X}' if boundary == 'x_hints' else face.mana_cost)
    if boundary == 'resources':
        marker = {'delve': [], 'convoke': [], 'improvise': []}
        def keywords(card):
            seen.append(('keywords', card))
            return frozenset({'convoke'})
        def candidates(game, player, card):
            assert game is state and player == 2
            seen.append(('candidates', card))
            return marker
        monkeypatch.setattr(casting_resources, 'resource_keywords', keywords)
        monkeypatch.setattr(casting_resources, 'resource_candidates', candidates)
    else:
        marker = {'action_has_target_text': False}
        def surfaces(text):
            seen.append(('surfaces', text))
            return boundary == 'kicker'
        def hints(game, card, player, selected):
            assert game is state and player == 2 and selected is option
            seen.append(('hints', card))
            return marker
        monkeypatch.setattr(kicker, 'kicker_surfaces', surfaces)
        monkeypatch.setattr(cast_choice, 'build_cost_cast_hints', hints)
    view = move_generator._cost_option_view(option, state, 2, source.id, cast_card=face)
    assert view['mana_cost'] == option.mana_cost
    if boundary == 'resources':
        assert view['resource_payment_candidates'] is marker
        assert seen == [('keywords', face), ('candidates', face)]
    else:
        assert view['target_hints'] is marker
        assert seen == [('surfaces', face.oracle_text), ('hints', face)]
    assert state.cards[source.id] is source and source is not face
    assert serialize_match_snapshot(state) == before

def test_default_cost_view_still_uses_original_card(monkeypatch):
    state = canonical_fixture()
    source = state.cards[state.players[2].hand[0]]
    seen = []
    def keywords(card):
        seen.append(card)
        return frozenset()
    monkeypatch.setattr(casting_resources, 'resource_keywords', keywords)
    move_generator._cost_option_view(CostOption('base', 'Base Cost', source.mana_cost), state, 2, source.id)
    assert seen == [source]

@pytest.mark.parametrize('seat', [1, 2])
def test_active_canonical_hand_exile_view_excludes_physical_spell(seat):
    rows = json.loads((Path(__file__).resolve().parents[1] / 'card_data/builtin_oracle_seed.json').read_bytes())['cards']
    row = rows['March of Otherworldly Light']
    deck = [{'quantity': 60, 'card_name': row.get('name') or row['card_name'], **row}]
    state = MatchFactory.from_decks(deck, deck, seed=9)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    spell = state.cards[state.players[seat].hand[0]]
    option = next(o for o in collect_cost_options(state, seat, spell, without_mana=True) if o.hand_exile_color)
    before = serialize_match_snapshot(state)
    view = move_generator._cost_option_view(option, state, seat, spell.id, cast_card=spell)
    assert view['hand_exile_color'] == 'W'
    assert view['hand_exile_generic_reduction'] == 2
    assert view['exile_card_ids']
    assert spell.id not in view['exile_card_ids']
    assert set(view['exile_card_ids']) == set(state.players[seat].hand) - {spell.id}
    assert serialize_match_snapshot(state) == before
