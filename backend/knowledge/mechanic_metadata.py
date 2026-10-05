from __future__ import annotations

import hashlib
import json
import re
from typing import Literal, NotRequired, TypedDict

from card_data.tactical import _effect_tags, _rules_surface, printed_card_types, tactical_clauses


SCHEMA_VERSION = 1
EXTRACTOR_VERSION = "canonical-tactical-surface-v1"


class MechanicEvidence(TypedDict):
    family: str
    source: str
    face_index: int | None
    text: str
    context: str
    region: str
    confidence: Literal["surface_pattern", "explicit_text", "type_context", "explicit_keyword", "explicit_field"]
    semantics: Literal["not_evaluated"]
    start: NotRequired[int]
    end: NotRequired[int]


class FamilyCoverage(TypedDict):
    status: Literal["detected", "not_detected"]
    scope: Literal["surface_detection_only"]
    execution_support: Literal["unknown"]


class MechanicProvenance(TypedDict):
    input: Literal["caller_supplied_card_data"]
    verification: Literal["not_performed"]
    oracle_id: str | None
    scryfall_id: str | None
    input_sha256: str
    hash_encoding: str


class MechanicMetadata(TypedDict):
    schema_version: int
    extractor_version: str
    provenance: MechanicProvenance
    surfaces: list[dict]
    evidence: list[MechanicEvidence]
    coverage: dict[str, FamilyCoverage]
    unknown: list[dict]
    unsupported_semantics: list[str]
    learned_quality: dict[str, str]
ROLE_FAMILIES = (
    "counter", "sweeper", "draw", "gain", "removal", "burn", "ramp", "token",
    "attack", "block", "creature_deploy_topdeck", "anthem", "reanimate",
    "recursion", "discard", "mill", "sacrifice", "death", "drain",
)
# Only detection is covered. These labels do not certify implementation or quality.
COST_KEYWORDS = {
    "flashback": "graveyard_cast_cost", "escape": "graveyard_cast_cost",
    "delve": "cost_payment", "convoke": "cost_payment", "improvise": "cost_payment",
    "kicker": "additional_cost", "multikicker": "additional_cost",
    "evoke": "alternative_cost", "madness": "alternative_cost",
    "overload": "alternative_cost", "bestow": "alternative_cost",
    "foretell": "alternative_cost", "dash": "alternative_cost",
    "spectacle": "alternative_cost", "blitz": "alternative_cost",
}
TEXT_FAMILIES = {
    "additional_cost": r"\bas an additional cost to cast\b",
    "alternative_cost": r"\brather than pay\b",
    "cost_modification": r"\bcosts?\b[^.\n]*\b(?:more|less) to cast\b",
    "cast_permission": r"\byou may (?:cast|play)\b",
    "life_gain_restriction": r"\b(?:can't|cannot) gain life\b",
    "counter_modification": r"\b(?:put|puts|get|gets)\b[^.\n]*\bcounters?\b[^.\n]*\binstead\b|\bcounters?\b[^.\n]*\bput\b[^.\n]*\binstead\b",
    "token_modification": r"\btokens?\b[^.\n]*\binstead\b",
}
FAMILIES = tuple(sorted(
    {"role_" + role for role in ROLE_FAMILIES}
    | set(TEXT_FAMILIES) | set(COST_KEYWORDS.values())
    | {"activated", "triggered", "replacement", "static_or_keyword", "spell_effect", "keyword"}
))
UNSUPPORTED = (
    "oracle_execution", "target_legality", "timing_legality", "condition_evaluation",
    "cost_payability", "replacement_ordering", "continuous_layers", "learned_quality",
)


def mechanic_metadata(raw: dict) -> MechanicMetadata:
    """Extract deterministic source-backed features; never certify canonicality.

    Caller supplies canonical card_data. IDs and spans record provenance, not
    verification. Confidence is categorical evidence strength, not probability.
    Unknown/not-detected features must not be encoded as known negative facts.
    """
    evidence: list[MechanicEvidence] = []
    surfaces: list[dict] = []
    unknown: list[dict] = []

    def inspect(card: dict, prefix: str, face_index: int | None) -> None:
        text = card.get("oracle_text")
        type_line = card.get("type_line")
        types = sorted(printed_card_types(type_line, card.get("types")))
        surface = {
            "source": prefix or "$", "face_index": face_index,
            "card_types": types, "type_line": type_line,
            "oracle_text_status": "present" if isinstance(text, str) and text.strip() else "missing_or_empty",
        }
        surfaces.append(surface)
        if not types:
            unknown.append({"source": prefix + "type_line", "reason": "missing_or_unrecognized_card_types"})
        if not isinstance(text, str) or not text.strip():
            unknown.append({"source": prefix + "oracle_text", "reason": "missing_or_empty_text_not_absence_of_abilities"})
            text = ""
        if text and not _rules_surface(text).strip():
            unknown.append({"source": prefix + "oracle_text", "reason": "reminder_or_quoted_text_not_interpreted"})

        def add(family: str, clause: dict, region: str = "paragraph", confidence: str = "surface_pattern") -> None:
            evidence.append({
                "family": family, "source": prefix + "oracle_text",
                "face_index": face_index, "start": clause["start"], "end": clause["end"],
                "text": clause["text"], "context": clause["kind"], "region": region,
                "confidence": confidence, "semantics": "not_evaluated",
            })

        for clause in tactical_clauses(text, type_line, card.get("types")):
            if clause["kind"] in FAMILIES:
                add(clause["kind"], clause, confidence=clause["confidence"])
            local_families = set()
            for region in ("effect", "condition", "cost"):
                for role in sorted(_effect_tags(clause[region])):
                    add("role_" + role, clause, region)
                    local_families.add("role_" + role)
            visible = _rules_surface(clause["text"]).lower()
            for family, pattern in TEXT_FAMILIES.items():
                if re.search(pattern, visible):
                    if family != clause["kind"]:
                        add(family, clause)
                    local_families.add(family)
            # Keyword lists start paragraphs; mentions/grants in prose are not keywords.
            leading = visible.strip().split("\u2014", 1)[0]
            for keyword, family in COST_KEYWORDS.items():
                if re.search(r"(?:^|,\s*)" + keyword + r"\b", leading):
                    add(family, clause, "keyword", "explicit_keyword")
                    local_families.add(family)
            reasons = ["paragraph_semantics_unparsed"]
            if re.search(r"\b(?:if|unless|otherwise|only|instead|may)\b", visible):
                reasons.append("conditional_or_choice_not_evaluated")
            if '"' in clause["text"] or "\u201c" in clause["text"]:
                reasons.append("quoted_ability_not_attributed")
            unknown.append({
                "source": prefix + "oracle_text", "start": clause["start"], "end": clause["end"],
                "reasons": reasons, "detected_families": sorted(local_families),
            })

        keywords = card.get("keywords")
        if isinstance(keywords, list):
            for index, keyword in enumerate(keywords):
                if not isinstance(keyword, str):
                    unknown.append({"source": prefix + f"keywords[{index}]", "reason": "invalid_keyword"})
                    continue
                for family in sorted({"keyword"} | ({COST_KEYWORDS[keyword.lower()]} if keyword.lower() in COST_KEYWORDS else set())):
                    evidence.append({
                        "family": family, "source": prefix + f"keywords[{index}]",
                        "face_index": face_index, "text": keyword, "context": "declared_keyword",
                        "region": "keyword", "confidence": "explicit_field", "semantics": "not_evaluated",
                    })

    inspect(raw, "", None)
    faces = raw.get("card_faces")
    if faces is not None and not isinstance(faces, list):
        unknown.append({"source": "card_faces", "reason": "invalid_faces"})
    if isinstance(faces, list):
        for index, face in enumerate(faces):
            prefix = f"card_faces[{index}]."
            if isinstance(face, dict):
                inspect(face, prefix, index)
            else:
                unknown.append({"source": prefix.rstrip("."), "reason": "invalid_face"})
    coverage: dict[str, FamilyCoverage] = {
        family: {
            "status": "detected" if any(e["family"] == family for e in evidence) else "not_detected",
            "scope": "surface_detection_only", "execution_support": "unknown",
        }
        for family in FAMILIES
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "provenance": {
            "input": "caller_supplied_card_data", "verification": "not_performed",
            "oracle_id": raw.get("oracle_id"), "scryfall_id": raw.get("id") or raw.get("scryfall_id"),
            "input_sha256": hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
            "hash_encoding": "UTF-8 JSON; sorted keys; ensure_ascii=True; separators=(',', ':')",
        },
        "surfaces": surfaces, "evidence": evidence, "coverage": coverage,
        "unknown": unknown, "unsupported_semantics": list(UNSUPPORTED),
        "learned_quality": {"status": "not_assessed"},
    }
