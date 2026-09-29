from rules_engine.coverage import known_unsupported_mechanics, deck_pair_coverage


def test_known_unsupported_mechanics_are_conservative_and_deduplicated() -> None:
    assert known_unsupported_mechanics("Morph {2}. Manifest dread. Suspend 3—{U}.") == [
        "morph", "manifest", "suspend"
    ]
    assert known_unsupported_mechanics("Mutate {1}{G}. Craft with an artifact {2}.") == ["mutate", "craft"]
    assert known_unsupported_mechanics("Discover 4. Discover 4.") == ["discover"]
    assert known_unsupported_mechanics("Banding", [{"oracle_text": "bands with other Dinosaurs"}]) == ["bands with other"]
    assert known_unsupported_mechanics("Draw a card. Banding. Counter target spell.") == []
    assert known_unsupported_mechanics("", [{"oracle_text": "Morph {2}"}, {"oracle_text": "Morph {3}"}]) == ["morph"]


def test_known_unsupported_otj_mechanics_are_reported_from_root_and_faces() -> None:
    assert known_unsupported_mechanics(
        "Domain — Create a Beast for each basic land type. Incubate X.",
        [{"oracle_text": "Kicker {B} and/or {R}."}],
    ) == ["kicker", "domain", "incubate"]
    assert known_unsupported_mechanics("Multikicker {1}. Incubated tokens transform.") == ["multikicker", "incubate"]
    assert known_unsupported_mechanics("Draw a card.") == []
    assert known_unsupported_mechanics("", [{"oracle_text": "Choose a creature card exiled with this creature. This creature becomes a copy of that card."}]) == ["copy-layer fidelity"]
    assert known_unsupported_mechanics("{X}: Crypt Rats deals X damage to each creature and each player. Spend only black mana on X.") == []


def test_deck_pair_coverage_reports_faces_before_simulation() -> None:
    deck_a = [{"card_name": "Willbender", "oracle_text": "", "card_faces": [{"oracle_text": "Morph {1}{U}"}]}]
    deck_b = [{"card_name": "Island", "oracle_text": "{T}: Add {U}."}]
    assert deck_pair_coverage(deck_a, deck_b) == {
        "status": "exploratory",
        "known_unsupported_cards": [{"deck": "A", "card_name": "Willbender", "mechanics": ["morph"]}],
    }
