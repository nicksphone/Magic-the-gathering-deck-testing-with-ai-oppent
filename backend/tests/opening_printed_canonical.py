"""Six pinned complete RAW objects for the existing opening-card constructor."""
import hashlib
import json
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"
SOURCES = {
    "Gemstone Caverns": (
        "hand_entry_bookkeeping/canonical.jsonl",
        "99a897459c994dedb916a59104c0023cab4e9d96aac274d60fd3f7603c44cfc0", 1,
        "83578fec264f8bf40afc6fef586e880e2e9744312340da286649237356e749aa", 65,
    ),
    "Leyline of Anticipation": (
        "global_flash_timing_audit/leyline-of-anticipation.json",
        "ef29f3f72a77d201848b0cabbf33824d25e076e8bd5b9f6ba3fc1ac7656c5455", None,
        "a97ecfefa77554abb02425ec07a17766529f974795c65e59901db6533d264e83", 62,
    ),
    "Leyline of Sanctity": (
        "browser_inline26/canonical.jsonl",
        "3c0ac6f8912b171a0712ed3fb4d17aafae3d5e5190530e6ad960f8c147369fdd", 19,
        "fd5bb6b6f9f5c8c0471710b95306aab8be57ba233b6210d8f22754ae822961b5", 64,
    ),
    "Leyline of Transformation": (
        "opening_printed_fidelity/leyline-of-transformation.json",
        "2a436abce7873c5459d92f6bed4a49cef100607418d20abbb008ff8f8ecff487", None,
        "4dccede11af8dd7f430e8c1ab94a18ebce29d02fb0b601771260d3fdd5d0fae3", 65,
    ),
    "Leyline of Vitality": (
        "opening_printed_fidelity/leyline-of-vitality.json",
        "374c3658c858ad9ac9425458cdbe4b4019160682c4e81550d8ca957f6cf45921", None,
        "c43fe7ca448be9288a210c036493547559d8dd65679cd48332f5a91bdf3e7c52", 63,
    ),
    "Leyline of the Void": (
        "hand_entry_bookkeeping/canonical.jsonl",
        "99a897459c994dedb916a59104c0023cab4e9d96aac274d60fd3f7603c44cfc0", 4,
        "27e6e1e44435b5daad9bf8c336024793947ee9e74de9b21c71289446afb17bec", 65,
    ),
}


def raw_cards():
    cards = {}
    for name, (relative, file_sha, line, object_sha, fields) in SOURCES.items():
        encoded = (FIXTURES / relative).read_bytes()
        if hashlib.sha256(encoded).hexdigest() != file_sha:
            raise ValueError("Opening fixture source changed")
        raw = json.loads(encoded.splitlines()[line - 1] if line is not None else encoded)
        digest = hashlib.sha256(json.dumps(
            raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        if (raw.get("object") != "card" or raw.get("name") != name
                or len(raw) != fields or digest != object_sha):
            raise ValueError("Opening fixture complete object changed")
        cards[name] = raw
    return cards
