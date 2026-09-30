import json
from pathlib import Path
from types import SimpleNamespace

from ai.agent import AIAgent
from card_data.tactical import canonical_tactical_tags


SEED = json.loads((Path(__file__).resolve().parents[1] / "card_data" / "builtin_oracle_seed.json").read_text())["cards"]


def _card(name):
    raw = SEED[name]
    return SimpleNamespace(name=name, oracle_text=raw["oracle_text"], type_line=raw["type_line"], types=raw["type_line"].split(" — ")[0].split())


def test_tactical_tags_follow_oracle_and_type_not_card_name():
    ai = AIAgent()
    bolt = _card("Lightning Bolt")
    assert {"burn", "removal"} <= ai._spell_tags(bolt)
    bolt.name = "Unrelated Name"
    assert {"burn", "removal"} <= ai._spell_tags(bolt)
    bolt.oracle_text = ""
    assert "burn" not in ai._spell_tags(bolt)
    bolt.name = "Lightning Bolt"
    assert "burn" not in ai._spell_tags(bolt)


def test_canonical_tactical_roles_without_name_shortcuts():
    ai = AIAgent()
    assert "ramp" in ai._spell_tags(_card("Cultivate"))
    assert "ramp" in ai._spell_tags(_card("Llanowar Elves"))
    assert "ramp" in ai._spell_tags(_card("Nissa, Who Shakes the World"))
    assert "draw" in ai._spell_tags(_card("Memory Deluge"))
    assert "sweeper" in ai._spell_tags(_card("Supreme Verdict"))
    assert "counter" not in ai._spell_tags(_card("Supreme Verdict"))
    assert "enchantment" not in ai._spell_tags(_card("Cultivate"))
    verdict = _card("Supreme Verdict")
    verdict.oracle_text = ""
    assert "sweeper" not in ai._spell_tags(verdict)


def test_seed_corpus_tactical_tags_are_deterministic_and_face_aware():
    for raw in SEED.values():
        profile = canonical_tactical_tags(raw)
        assert profile["tactical_tags"] == sorted(set(profile["tactical_tags"]))
        if raw.get("card_faces"):
            assert len(profile["face_tactical_tags"]) == len(raw["card_faces"])
    assert "burn" in canonical_tactical_tags(SEED["Lightning Bolt"])["tactical_tags"]
    assert "sweeper" in canonical_tactical_tags(SEED["Supreme Verdict"])["tactical_tags"]
    assert "burn" not in canonical_tactical_tags(SEED["Forest"])["tactical_tags"]
    assert "removal" in canonical_tactical_tags(SEED["Brutal Cathar"])["face_tactical_tags"][0]
