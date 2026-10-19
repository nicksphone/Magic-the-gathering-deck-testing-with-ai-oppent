"""Explicit desired ordinary RED; kept outside the default project and release patch."""
import pytest
from card_data.hydration import hydrate_deck_cards
from tests.face_metadata_parity_support import FAMILIES,raw_card,board,projection

@pytest.mark.parametrize('family',FAMILIES)
@pytest.mark.parametrize('seat',[1,2])
def test_ready_seed_live_face_color_must_equal_unchanged_canonical(family,seat):
    raw=raw_card(family)
    facts=hydrate_deck_cards(None,board(family))
    actual=projection(facts,family,seat)
    assert actual[1]['colors']==raw['card_faces'][1]['colors']
