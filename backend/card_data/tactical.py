from __future__ import annotations

import re


def tactical_tags(oracle_text: str, type_line: str = "", types: list[str] | None = None) -> set[str]:
    """Derive conservative card roles from printed rules text, never its name."""
    text = str(oracle_text or "").lower()
    card_types = {part.lower() for part in (types or [])}
    card_types.update(re.split(r"\s+", str(type_line or "").split("—", 1)[0].lower()))
    tags: set[str] = set()

    if re.search(r"\bcounter target(?: [a-z -]{0,45})?\b(?:spell|ability)\b", text):
        tags.add("counter")
    if ("destroy all creatures" in text or "exile all creatures" in text
            or re.search(r"\beach creature gets -[x0-9]+/-[x0-9]+", text)):
        tags.add("sweeper")
    if "draw" in text or ("look at the top" in text and "into your hand" in text):
        tags.add("draw")
    if re.search(r"\bgains?\b[^.\n]{0,80}\blife\b", text):
        tags.add("gain")
    if "destroy target" in text or "exile target" in text or re.search(r"\bdeals?\b.*\bdamage\b", text):
        tags.add("removal")
    if re.search(r"\bdeals?\s+(?:\d+|x|that much)\s+damage to\s+(?:any target|target (?:player|opponent)|each (?:player|opponent))", text):
        tags.add("burn")
    if re.search(r"\badd\b[^.\n]{0,35}\{[wubrgc]\}", text) or re.search(r"search your library for[^.]*\bland cards?\b", text):
        tags.add("ramp")
    if "create" in text and "token" in text:
        tags.add("token")
    if "attack" in text:
        tags.add("attack")
    if "block" in text:
        tags.add("block")
    if "look at the top" in text and "creature cards" in text and "onto the battlefield" in text:
        tags.add("creature_deploy_topdeck")
    if "creatures you control get" in text or "+1/+1" in text:
        tags.add("anthem")
    if "enchantment" in card_types:
        tags.add("enchantment")
    if re.search(r"(?:return|put) target creature card from your graveyard (?:to|onto) the battlefield", text):
        tags.add("reanimate")
    if "from your graveyard" in text and any(word in text for word in ("cast", "return", "play")):
        tags.add("recursion")
    for word in ("discard", "mill", "sacrifice", "dies"):
        if word in text:
            tags.add("death" if word == "dies" else word)
    if "lose" in text and "gain" in text:
        tags.add("drain")
    if any(word in text for word in ("whenever", "at the beginning", "landfall", "magecraft", "prowess", "artifact or enchantment", "another permanent enters the battlefield", "another permanent dies")):
        tags.add("engine")
    return tags


def canonical_tactical_tags(raw: dict) -> dict[str, list[str]]:
    faces = raw.get("card_faces") or []
    result = {"tactical_tags": sorted(tactical_tags(raw.get("oracle_text", ""), raw.get("type_line", "")))}
    if isinstance(faces, list) and faces:
        result["face_tactical_tags"] = [
            sorted(tactical_tags(face.get("oracle_text", ""), face.get("type_line", "")))
            for face in faces if isinstance(face, dict)
        ]
    return result
