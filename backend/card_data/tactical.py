from __future__ import annotations

import re


CARD_TYPES = frozenset({
    "artifact", "battle", "creature", "enchantment", "instant", "kindred",
    "land", "planeswalker", "sorcery", "tribal",
})

HAND_LAND_DEPLOYMENT_RE = re.compile(
    r"(?:^|[.\n,:]\s*)(?:you may )?put (?:a|an|one) land card from your hand onto the battlefield(?: tapped)?\.",
    re.IGNORECASE,
)


def printed_card_types(type_line: str = "", types: list[str] | None = None) -> set[str]:
    words = re.findall(r"[a-z]+", str(type_line or "").split("\u2014", 1)[0].lower())
    return (set(words) | {str(t).lower() for t in (types or [])}) & CARD_TYPES


def _rules_surface(text: str) -> str:
    # Mask reminder text and granted/quoted abilities without moving source spans.
    chars = list(text)
    depth = 0
    quoted = False
    for i, char in enumerate(text):
        if char == "(":
            depth += 1
        if char in {'"', '\u201c', '\u201d'} and not depth:
            quoted = not quoted
            chars[i] = " "
            continue
        if depth or quoted:
            chars[i] = " " if char != "\n" else "\n"
        if char == ")" and depth:
            depth -= 1
    return "".join(chars)


def tactical_clauses(oracle_text: str, type_line: str = "", types: list[str] | None = None) -> list[dict]:
    """Paragraph-local surface descriptors, not an Oracle interpreter.

    Trigger conditions and activation costs stay distinct from effects. Static
    classification is contextual, not proof of continuous-effect support.
    """
    text = str(oracle_text or "")
    surface = _rules_surface(text)
    card_types = printed_card_types(type_line, types)
    clauses = []
    for match in re.finditer(r"[^\n]+", surface):
        if not match.group().strip():
            continue
        start, end = match.span()
        line = match.group().lower().strip()
        kind, confidence = "unknown", "unknown"
        body = match.group().lower()
        condition = cost = ""
        # Ability-word prefixes are labels, not separate executable abilities.
        heading = re.sub(r"^[a-z -]+\s+\u2014\s+", "", line)
        if re.match(r"^(?:when|whenever|at the beginning|at the end)\b", heading) and "," in body:
            kind, confidence = "triggered", "surface_pattern"
            condition, body = body.split(",", 1)
        elif ":" in body and re.search(r"\{[^}]+\}|^[+\-\u2212]?\d+\s*:|\b(?:pay|sacrifice|discard|tap|untap)\b[^:]*:", body.split(":", 1)[0] + ":"):
            kind, confidence = "activated", "surface_pattern"
            cost, body = body.split(":", 1)
        elif re.search(r"\bwould\b[^\n]*\binstead\b", body):
            kind, confidence = "replacement", "surface_pattern"
        elif line.startswith("as an additional cost"):
            kind, confidence = "additional_cost", "explicit_text"
            cost, body = body, ""
        elif re.search(r"\brather than pay\b", body):
            kind, confidence = "alternative_cost", "explicit_text"
        elif card_types & {"instant", "sorcery"}:
            kind, confidence = "spell_effect", "type_context"
        elif card_types:
            kind, confidence = "static_or_keyword", "type_context"
        clauses.append({
            "start": start, "end": end, "text": text[start:end],
            "kind": kind, "confidence": confidence,
            "effect": body, "condition": condition, "cost": cost,
        })
    return clauses


def _effect_tags(text: str) -> set[str]:
    """Bounded positive instruction patterns. Not detecting a role is not absence."""
    tags: set[str] = set()
    quantity = r"(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+|x|that much)"
    if re.search(r"\bcounter target\b[^.\n]*\b(?:spell|ability)\b", text):
        tags.add("counter")
    if (re.search(r"\b(?:destroy|exile) all creatures\b", text)
            or re.search(r"\beach creature gets -[x0-9]+/-[x0-9]+", text)):
        tags.add("sweeper")
    if (re.search(r"\bdraws? " + quantity + r" cards?\b", text)
            or re.search(r"\blook at the top\b[^\n]*\binto your hand\b", text)):
        tags.add("draw")
    if re.search(r"\bgains? " + quantity + r" life\b", text):
        tags.add("gain")
    damage = re.search(r"\bdeals? " + quantity + r" damage\b", text)
    if re.search(r"\b(?:destroy|exile) target\b", text) or damage:
        tags.add("removal")
    if re.search(r"\bdeals? " + quantity + r" damage to (?:any target|target (?:player|opponent)|each (?:player|opponent))\b", text):
        tags.add("burn")
    if (re.search(r"\badd\b[^.\n]*\{[wubrgc]\}", text)
            or re.search(r"\badd (?:" + quantity + r" mana|mana of any)", text)
            or re.search(r"\bsearch your library for\b[^.\n]*\bland cards?\b", text)
            or HAND_LAND_DEPLOYMENT_RE.search(_rules_surface(text))):
        tags.add("ramp")
    if re.search(r"\bcreates?\b[^.\n]*\btokens?\b", text):
        tags.add("token")
    if re.search(r"\battack(?:s|ed|ing)?\b", text):
        tags.add("attack")
    if re.search(r"\bblock(?:s|ed|ing)?\b", text):
        tags.add("block")
    if re.search(r"\blook at the top\b[^\n]*\bcreature cards\b[^\n]*\bonto the battlefield\b", text):
        tags.add("creature_deploy_topdeck")
    if re.search(r"\bcreatures you control get [+-][0-9x]+/[+-][0-9x]+", text):
        tags.add("anthem")
    if re.search(r"\b(?:return|put) target creature card from your graveyard (?:to|onto) the battlefield\b", text):
        tags.add("reanimate")
    if re.search(r"\b(?:cast|return|play)\b[^.\n]*\bfrom your graveyard\b", text):
        tags.add("recursion")
    for word in ("discard", "mill", "sacrifice", "dies"):
        if re.search(r"\b" + word + r"(?:s)?\b", text):
            tags.add("death" if word == "dies" else word)
    # Do not pair unrelated clauses or sentences into a drain effect.
    for sentence in re.split(r"[.\n]", text):
        if (re.search(r"\bloses? " + quantity + r" life\b", sentence)
                and re.search(r"\bgains? " + quantity + r" life\b", sentence)):
            tags.add("drain")
    return tags


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
    if (re.search(r"\badd\b[^.\n]{0,35}\{[wubrgc]\}", text)
            or re.search(r"search your library for[^.]*\bland cards?\b", text)
            or HAND_LAND_DEPLOYMENT_RE.search(_rules_surface(text))):
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


def canonical_tactical_tags(raw: dict) -> dict:
    faces = raw.get("card_faces") or []
    result = {"tactical_tags": sorted(tactical_tags(raw.get("oracle_text", ""), raw.get("type_line", "")))}
    if isinstance(faces, list) and faces:
        result["face_tactical_tags"] = [
            sorted(tactical_tags(face.get("oracle_text", ""), face.get("type_line", "")))
            for face in faces if isinstance(face, dict)
        ]
    from knowledge.mechanic_metadata import mechanic_metadata

    result["mechanic_metadata"] = mechanic_metadata(raw)
    return result
