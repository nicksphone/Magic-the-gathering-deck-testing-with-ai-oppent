from rules_engine.coverage import known_unsupported_mechanics


def test_known_unsupported_mechanics_are_conservative_and_deduplicated() -> None:
    assert known_unsupported_mechanics("Morph {2}. Manifest dread. Suspend 3—{U}.") == [
        "morph", "manifest", "suspend"
    ]
    assert known_unsupported_mechanics("Mutate {1}{G}. Craft with an artifact {2}.") == ["mutate", "craft"]
    assert known_unsupported_mechanics("Discover 4. Discover 4.") == ["discover"]
    assert known_unsupported_mechanics("Banding", [{"oracle_text": "bands with other Dinosaurs"}]) == ["bands with other"]
    assert known_unsupported_mechanics("Draw a card. Banding. Counter target spell.") == []
    assert known_unsupported_mechanics("", [{"oracle_text": "Morph {2}"}, {"oracle_text": "Morph {3}"}]) == ["morph"]
