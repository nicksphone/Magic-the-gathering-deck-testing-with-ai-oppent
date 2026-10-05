import copy
import hashlib
import json
from pathlib import Path

import pytest

from card_data.tactical import canonical_tactical_tags, tactical_tags
from knowledge.mechanic_metadata import FAMILIES, mechanic_metadata


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "card_data/builtin_oracle_seed.json").read_text())["cards"]


def fixture(path, name=None):
    raw = json.loads((ROOT / "tests/fixtures" / path).read_text())
    if name is None:
        return raw
    return next(card for card in (raw if isinstance(raw, list) else raw["data"]) if card["name"] == name)


def entries(raw, family):
    return [entry for entry in mechanic_metadata(raw)["evidence"] if entry["family"] == family]


def test_existing_canonical_fixture_provenance_is_intact():
    directory = ROOT / "tests/fixtures/cast_resources"
    provenance = json.loads((directory / "provenance.json").read_text())
    assert hashlib.sha256((directory / "canonical.json").read_bytes()).hexdigest() == provenance["sha256"]
    for entry in json.loads((ROOT / "tests/fixtures/life_restriction_layers/provenance.json").read_text()):
        path = ROOT / "tests/fixtures/life_restriction_layers" / (entry["name"].lower().replace(",", "").replace(" ", "-") + ".json")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_both_faces_are_described_without_changing_legacy_availability():
    raw = SEED["Wedding Announcement"]
    result = canonical_tactical_tags(raw)
    assert {"draw", "token", "enchantment"} <= set(result["tactical_tags"])
    assert "anthem" not in result["tactical_tags"]  # Legacy top-level surface stays unchanged.
    assert "anthem" not in result["face_tactical_tags"][0]
    assert "anthem" in result["face_tactical_tags"][1]
    anthem = entries(raw, "role_anthem")
    assert {e["face_index"] for e in anthem} == {1}
    assert {e["context"] for e in anthem} == {"static_or_keyword"}
    assert result["mechanic_metadata"]["coverage"]["role_anthem"]["execution_support"] == "unknown"


def test_static_restriction_is_not_activated_gain_and_cost_is_separate():
    raw = fixture("life_restriction_layers/erebos-god-of-the-dead.json")
    assert not entries(raw, "role_gain")
    assert {e["context"] for e in entries(raw, "life_gain_restriction")} == {"static_or_keyword"}
    draw = entries(raw, "role_draw")
    assert len(draw) == 1 and draw[0]["context"] == "activated" and draw[0]["region"] == "effect"


def test_activation_trigger_and_loyalty_have_distinct_contexts():
    assert entries(SEED["Llanowar Elves"], "role_ramp")[0]["context"] == "activated"
    assert entries(SEED["Blood Artist"], "role_death")[0]["region"] == "condition"
    assert entries(SEED["Blood Artist"], "role_drain")[0]["region"] == "effect"
    loyalty = entries(SEED["Nissa, Who Shakes the World"], "activated")
    assert len(loyalty) == 2
    assert all(e["confidence"] == "surface_pattern" for e in loyalty)


def test_replacement_and_conditional_multi_sentence_scope_remains_unresolved():
    doubling = fixture("counter_replacements.json", "Doubling Season")
    assert len(entries(doubling, "replacement")) == 2
    assert entries(doubling, "counter_modification")
    assert entries(doubling, "token_modification")
    rest = fixture("landfall/rest-for-the-weary.json")
    assert {"gain"} <= tactical_tags(rest["oracle_text"])
    assert any("conditional_or_choice_not_evaluated" in u.get("reasons", []) for u in mechanic_metadata(rest)["unknown"])
    wedding = mechanic_metadata(SEED["Wedding Announcement"])
    effects = [e for e in wedding["evidence"] if e["face_index"] == 0 and e["family"] in {"role_draw", "role_token"}]
    assert len(effects) == 2 and all(e["context"] == "triggered" for e in effects)
    assert all(e["semantics"] == "not_evaluated" for e in effects)


@pytest.mark.parametrize("name,family", [
    ("Dig Through Time", "cost_payment"), ("Siege Wurm", "cost_payment"),
    ("Metallic Rebuke", "cost_payment"), ("Hogaak, Arisen Necropolis", "cast_permission"),
])
def test_canonical_cost_and_permission_detection(name, family):
    raw = fixture("cast_resources/canonical.json", name)
    assert entries(raw, family)
    assert mechanic_metadata(raw)["coverage"][family]["scope"] == "surface_detection_only"


def test_flashback_additional_cost_and_sacrifice_cost_are_not_effects():
    assert entries(SEED["Memory Deluge"], "graveyard_cast_cost")
    spite = fixture("variable_spell_costs.json", "Kaervek's Spite")
    assert entries(spite, "additional_cost")
    assert entries(spite, "role_sacrifice")[0]["region"] == "cost"
    assert entries(spite, "role_discard")[0]["region"] == "cost"
    petal = fixture("variable_spell_costs.json", "Lotus Petal")
    assert entries(petal, "role_sacrifice")[0]["region"] == "cost"
    assert entries(petal, "role_ramp")[0]["region"] == "effect"


def test_source_backed_alternative_cost_and_conditional_keyword_cost():
    borderpost = fixture("qualified_spell_costs.json", "Mistvein Borderpost")
    cost = entries(borderpost, "alternative_cost")
    assert len(cost) == 1 and cost[0]["context"] == "alternative_cost"
    assert cost[0]["semantics"] == "not_evaluated"
    bestow = fixture("bestow.json", "Leafcrown Dryad")
    assert entries(bestow, "alternative_cost")[0]["confidence"] == "explicit_keyword"
    kicker = fixture("kicker.json", "Into the Roil")
    assert entries(kicker, "additional_cost")
    assert entries(kicker, "role_draw")
    assert any("conditional_or_choice_not_evaluated" in u.get("reasons", []) for u in mechanic_metadata(kicker)["unknown"])


def test_keyword_payment_is_not_a_cast_permission_or_effect_from_reminder():
    raw = fixture("cast_resources/canonical.json", "Dig Through Time")
    assert not entries(raw, "role_recursion")
    assert not entries(raw, "role_removal")
    assert not entries(raw, "cast_permission")
    assert entries(raw, "role_draw")


def test_quoted_ability_is_not_attributed_to_source_permanent():
    raw = SEED["Nissa, Who Shakes the World"]
    assert any("quoted_ability_not_attributed" in u.get("reasons", []) for u in mechanic_metadata(raw)["unknown"])
    assert not entries(raw, "role_anthem")
    assert not entries(fixture("counter_replacements.json", "Hardened Scales"), "role_anthem")


def test_facts_are_deterministic_json_safe_nonmutating_and_not_scores():
    for raw in SEED.values():
        before = copy.deepcopy(raw)
        result = mechanic_metadata(raw)
        assert result == mechanic_metadata(raw) == json.loads(json.dumps(result))
        assert raw == before
        assert set(result["coverage"]) == set(FAMILIES)
        assert result["learned_quality"] == {"status": "not_assessed"}
        assert "oracle_execution" in result["unsupported_semantics"]
        assert "learned_quality" in result["unsupported_semantics"]
        for e in result["evidence"]:
            if "start" not in e:
                continue
            source = raw if e["face_index"] is None else raw["card_faces"][e["face_index"]]
            assert source["oracle_text"][e["start"]:e["end"]] == e["text"]
            assert 0 <= e["start"] < e["end"] <= len(source["oracle_text"])


def test_name_is_not_a_feature_and_provenance_is_not_verification():
    raw = copy.deepcopy(SEED["Lightning Bolt"])
    before = mechanic_metadata(raw)
    raw["name"] = ""
    after = mechanic_metadata(raw)
    assert after["evidence"] == before["evidence"]
    assert after["coverage"] == before["coverage"]
    assert after["provenance"]["input_sha256"] != before["provenance"]["input_sha256"]
    assert before["provenance"]["verification"] == "not_performed"
    assert before["provenance"]["scryfall_id"] == raw["scryfall_id"]


def test_missing_text_faces_and_types_do_not_become_known_negatives():
    raw = {"card_faces": [None, {}]}
    metadata = mechanic_metadata(raw)
    assert any(u.get("reason") == "invalid_face" for u in metadata["unknown"])
    assert any(u.get("reason") == "missing_or_empty_text_not_absence_of_abilities" for u in metadata["unknown"])
    assert all(c["status"] == "not_detected" and c["execution_support"] == "unknown" for c in metadata["coverage"].values())


def test_card_types_are_primary_types_not_subtypes_or_supertypes():
    raw = fixture("cast_resources/canonical.json", "Dryad Arbor")
    assert mechanic_metadata(raw)["surfaces"][0]["card_types"] == ["creature", "land"]
    assert any(u.get("reason") == "reminder_or_quoted_text_not_interpreted" for u in mechanic_metadata(raw)["unknown"])
    assert mechanic_metadata(SEED["Nissa, Who Shakes the World"])["surfaces"][0]["card_types"] == ["planeswalker"]


@pytest.mark.parametrize("name", ["Thalia, Guardian of Thraben", "Supreme Verdict", "Forest"])
def test_existing_static_and_spell_fixtures_do_not_invent_roles(name):
    assert "counter" not in canonical_tactical_tags(SEED[name])["tactical_tags"]


def test_unrelated_clauses_do_not_pair_into_roles():
    # Boundary probes compose real fixture clauses, not invented canonical cards.
    death = SEED["Blood Artist"]["oracle_text"].split(",", 1)[1].strip()
    loss, gain = death.split(" and ")
    assert "drain" in tactical_tags(death)
    raw = {"oracle_text": loss + ".\n" + gain, "type_line": "Instant"}
    assert not entries(raw, "role_drain")
    assert "drain" in tactical_tags(raw["oracle_text"])  # Compatibility bag, not coupling evidence.
    create = SEED["Wedding Announcement"]["oracle_text"].split("Otherwise, ")[1].split(". Then")[0] + "."
    assert "token" in tactical_tags(create)
    assert not entries({"oracle_text": create.split("token")[0] + ".\nToken"}, "role_token")


def test_metadata_version_and_input_hash_have_separate_namespace():
    raw = SEED["Lightning Bolt"]
    result = canonical_tactical_tags(raw)
    assert "schema_version" not in result  # Do not overwrite ingest schema_version.
    metadata = result["mechanic_metadata"]
    assert metadata["schema_version"] == 1
    assert metadata["extractor_version"] == "canonical-tactical-surface-v1"
    encoded = json.dumps(raw, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    assert metadata["provenance"]["input_sha256"] == hashlib.sha256(encoded).hexdigest()
