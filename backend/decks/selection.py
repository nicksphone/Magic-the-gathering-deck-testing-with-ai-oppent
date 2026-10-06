from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from collections.abc import Callable


_ARCHETYPE_PRIORITY = [
    "Aggro",
    "Burn",
    "Midrange",
    "Control",
    "Tempo",
    "Ramp",
    "Drain",
    "Aristocrats",
    "Reanimator",
    "Tokens",
    "Tribal",
    "Combo-lite",
    "Counter-heavy",
    "Removal-heavy",
    "unknown",
]


def cohort_identity(deck):
    source = _row_get(deck, "source", "")
    if source is None:
        source = ""
    if not isinstance(source, str):
        raise ValueError("Invalid cohort source identity")
    source = source.strip().casefold()
    record_id = _row_get(deck, "id", None)
    if record_id is not None:
        if type(record_id) is not int or record_id < 1:
            raise ValueError("Invalid cohort record identity")
        identity = ["record", source, record_id]
    elif source:
        identity = ["source-name", source, _row_get(deck, "name", "")]
    else:
        return None  # Legacy name-only inputs have no repository provenance.
    return json.dumps(identity, ensure_ascii=True, separators=(",", ":"))


def cohort_pair_seed(left, right, index):
    identities = [left.get('identity_key'), right.get('identity_key')]
    for deck, identity in zip((left, right), identities):
        if identity is not None and identity != cohort_identity(deck):
            raise ValueError('Invalid seed cohort identity')
    if not any(identities):
        payload = f"{left['name']}::{right['name']}::{index}"
    else:
        payload = json.dumps([identities[0] or ['legacy-name', left['name']],
                              identities[1] or ['legacy-name', right['name']], index],
                             separators=(",", ":"))
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8], 16)


def _cohort_view(rows):
    """Newest builtin only; custom/history storage is never modified."""
    unique, seen_ids, seen_fallbacks = [], {}, {}
    for row in rows:
        name = _row_get(row, 'name', None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Invalid cohort name identity')
        record_id = _row_get(row, "id", None)
        facts = {key: _row_get(row, key, None) for key in
                 ("id", "source", "name", "mainboard_json", "mainboard", "sideboard_json", "archetype_guess", "created_at")}
        if isinstance(row, dict):
            facts = {key: deepcopy(value) for key, value in row.items() if key != 'cohort_order'}
        identity = cohort_identity(row)
        if record_id is not None:
            if type(record_id) is not int or record_id < 1:
                raise ValueError("Invalid cohort record identity")
            if record_id in seen_ids:
                if facts != seen_ids[record_id]:
                    raise ValueError("Conflicting cohort record identity")
                continue
            seen_ids[record_id] = facts
        else:
            fallback = ('identity', identity) if identity else ('legacy-name', name)
            if fallback in seen_fallbacks:
                if facts != seen_fallbacks[fallback]:
                    raise ValueError('Ambiguous cohort identity without a stable ID')
                continue
            seen_fallbacks[fallback] = facts
        unique.append(row)
    def rank(row):
        order = _row_get(row, 'cohort_order', None)
        if order is not None:
            return ('', -order)
        created = _row_get(row, "created_at", None)
        return (created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
                _row_get(row, "id", None) or 0)
    newest = {}
    for row in unique:
        if (_row_get(row, "source", "") or "").strip().casefold() == "builtin":
            key = _row_get(row, "name", "").strip().casefold()
            if key not in newest or rank(row) > rank(newest[key]):
                newest[key] = row
    # Stable repository order survives input duplication/permutation when IDs exist.
    unique.sort(key=rank, reverse=True)
    return [row for row in unique if (_row_get(row, "source", "") or "").strip().casefold() != "builtin"
            or newest[_row_get(row, "name", "").strip().casefold()] is row]


def prepare_cohort(rows, *, resolve_deck_fn):
    from ai.deck_analysis import analyze_deck
    from card_data.hydration import ready_for_match
    prepared = []
    for row in _cohort_view(rows):
        board = _row_get(row, "mainboard", None)
        if board is None:
            board = json.loads(_row_get(row, "mainboard_json", "[]"))
        resolved = resolve_deck_fn(deepcopy(board))
        analysis = analyze_deck(resolved)
        complete = (bool(resolved) and all(card.get("card_data_sources") and ready_for_match(card) for card in resolved)
                    and analysis['type_metadata_coverage'] == 1 and analysis['confidence'] > 0
                    and not {"missing_card_metadata", "partial_card_metadata", "fallback_midrange"}.intersection(analysis['signals']))
        item = {"name": _row_get(row, "name", ""), "mainboard": resolved, "cohort_order": len(prepared),
                "stored_archetype": _row_get(row, "archetype_guess", "unknown"),
                "archetype_guess": analysis['primary_archetype'] if complete else 'unknown',
                "classification_status": 'resolved' if complete else 'unknown', "analysis": analysis,
                "classification_provenance": {"method": "ai.deck_analysis.analyze_deck",
                    "admission": "complete-local-canonical-v1", "sources": sorted({source for card in resolved
                        for source in card.get('card_data_sources', [])}),
                    "resolved_board_sha256": hashlib.sha256(json.dumps(resolved, sort_keys=True,
                        separators=(",", ":"), allow_nan=False).encode()).hexdigest()}}
        if _row_get(row, 'source', None) is not None:
            item['source'] = _row_get(row, 'source', None)
        if _row_get(row, 'id', None) is not None:
            item['id'] = _row_get(row, 'id', None)
        identity = cohort_identity(item)
        if identity:
            item['identity_key'] = identity
        prepared.append(item)
    return prepared


def select_representative_decks(
    rows,
    max_decks: int,
    *,
    guess_archetype_fn: Callable[[list[dict]], str],
) -> list[dict]:
    max_decks = max(2, int(max_decks or 0))
    annotated: list[dict] = []
    for row in _cohort_view(rows):
        row_name = _row_get(row, "name", "")
        row_mainboard_json = _row_get(row, "mainboard_json", "[]")
        row_archetype = (_row_get(row, "archetype_guess", "") or "").strip()
        mainboard = _row_get(row, "mainboard", None)
        if mainboard is None:
            mainboard = json.loads(row_mainboard_json)
        archetype = row_archetype
        if (not archetype or archetype.lower() == "unknown") and _row_get(row, 'classification_status', None) is None:
            archetype = guess_archetype_fn(mainboard)
        annotated.append(
            {
                "name": row_name,
                "mainboard": mainboard,
                "archetype": archetype,
            }
        )
        identity = cohort_identity(row)
        if identity:
            annotated[-1].update({"identity_key": identity, "source": _row_get(row, 'source', ''),
                                  "id": _row_get(row, 'id', None)})
        for key in ('analysis', 'classification_status', 'classification_provenance', 'stored_archetype'):
            value = _row_get(row, key, None)
            if value is not None:
                annotated[-1][key] = deepcopy(value)

    ordered_archetypes: list[str] = []
    for arch in _ARCHETYPE_PRIORITY:
        if any(item["archetype"] == arch for item in annotated):
            ordered_archetypes.append(arch)
    for item in annotated:
        if item["archetype"] not in ordered_archetypes:
            ordered_archetypes.append(item["archetype"])

    selected: list[dict] = []
    seen_names: set[tuple] = set()
    def key(item):
        return ('identity', item['identity_key']) if item.get('identity_key') else ('legacy-name', item['name'])
    for archetype in ordered_archetypes:
        for item in annotated:
            if item["archetype"] != archetype or key(item) in seen_names:
                continue
            selected.append(item)
            seen_names.add(key(item))
            break
        if len(selected) >= max_decks:
            return selected[:max_decks]

    if len(selected) < max_decks:
        for item in annotated:
            if key(item) in seen_names:
                continue
            selected.append(item)
            seen_names.add(key(item))
            if len(selected) >= max_decks:
                break

    return selected[:max_decks]


def _row_get(row, key: str, default):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)
