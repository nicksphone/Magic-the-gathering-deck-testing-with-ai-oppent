from __future__ import annotations

from decks.parser import DeckParser


class FakeRepo:
    def list_cards(self):
        class Card:
            def __init__(self, name):
                self.name = name

        return [Card("Lightning Bolt"), Card("Island"), Card("Counterspell")]


def test_parse_minimum_deck_and_suggestions() -> None:
    parser = DeckParser(FakeRepo())
    text = "\n".join(["4 Lightning Bolt", "20 Island", "36 Counterspell"])
    parsed = parser.parse(text)
    assert not parsed.errors
    assert len(parsed.mainboard) == 3


def test_parse_unknown_card_suggests() -> None:
    parser = DeckParser(FakeRepo())
    text = "4 Lightnign Bolt\n56 Island"
    parsed = parser.parse(text)
    assert parsed.suggestions


def test_front_face_name_resolves_to_canonical_multiface_card() -> None:
    class FaceRepo(FakeRepo):
        def list_card_knowledge_names(self):
            return ["Imodane's Recruiter // Train Troops"]

    parsed = DeckParser(FaceRepo()).parse("1 Imodane's Recruiter\n59 Island")
    assert not parsed.errors
    assert not parsed.suggestions
    assert parsed.mainboard[0]["card_name"] == "Imodane's Recruiter // Train Troops"
