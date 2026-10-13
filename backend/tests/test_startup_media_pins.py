"""Offline public pin generator contracts; no application import or startup."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

import pytest


SOURCE = Path(__file__).resolve().parents[2]
SCRIPT = SOURCE / "backend/scripts/generate_startup_media_pins.py"
SEED = json.loads((SOURCE / "backend/card_data/builtin_oracle_seed.json").read_text())["cards"]
PIN_PATHS = (
    "backend/main.py", "backend/decks/bootstrap.py", "backend/card_data/hydration.py",
    "backend/card_data/display.py", "backend/card_data/placeholders.py",
    "backend/card_data/seed_cards.py", "backend/decks/expansion_top_decks.py",
    "backend/persistence/capacity.py",
)
INPUT_PATHS = PIN_PATHS + (
    "backend/decks/builtin_decks.py", "backend/decks/catalog.py",
    "backend/card_data/builtin_oracle_seed.json", "backend/decks/historical_event_catalog.json",
)


def structural(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


@pytest.fixture
def generator():
    def load():
        assert SCRIPT.is_file(), "Public startup-media pin generator is missing"
        spec = importlib.util.spec_from_file_location("public_startup_media_generator", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load


@pytest.fixture
def copied_source(tmp_path):
    root = tmp_path / "public-source"
    for relative in INPUT_PATHS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / relative, target)
    return root


def test_exact_guard_schema_pins_and_structural_formula(generator):
    generator = generator()
    before = set(sys.modules)
    artifact = generator.build_artifact(SOURCE)
    assert not {"main", "decks.bootstrap", "decks.catalog", "persistence.capacity"}.intersection(set(sys.modules) - before)
    assert set(artifact) == {"source_module_pins", "seed_cards_structural_sha256",
                             "builtin_decks_structural_sha256", "expansion_decks_structural_sha256", "startup_media"}
    assert artifact["source_module_pins"] == {p: hashlib.sha256((SOURCE / p).read_bytes()).hexdigest() for p in PIN_PATHS}
    assert artifact["seed_cards_structural_sha256"] == structural(SEED)
    assert artifact["seed_cards_structural_sha256"] == "b3f533bf23ca1f1302f9abd1139e12d3036944d41d4f3ae56968d3395aa0448a"
    assert artifact["builtin_decks_structural_sha256"] == "ee2414e7b2b11bab68a4f46649d2da21a2004b56c9c3a2702224cf5c0ee33bf8"
    assert artifact["expansion_decks_structural_sha256"] == "da2384b57b1018360dd9ff1950ae9041327ece31551e501cc2a5093346037b7e"
    tree = ast.parse((SOURCE / "backend/tests/current_built_browser_server.py").read_bytes())
    guard = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "startup_media_write")
    formula = next(n.value for n in guard.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "structural" for t in n.targets))
    exact = eval(compile(ast.Expression(formula), "<guard-structural>", "eval"), {"hashlib": hashlib, "json": json})
    for key in ("seed_cards_structural_sha256", "builtin_decks_structural_sha256", "expansion_decks_structural_sha256"):
        assert len(artifact[key]) == 64
    assert exact(SEED) == artifact["seed_cards_structural_sha256"]
    assert generator.build_artifact(SOURCE) == artifact


def test_all_public_startup_names_and_aliases_have_exact_seed_rows(generator):
    generator = generator()
    from copy import deepcopy
    import re
    def tree(relative):
        return ast.parse((SOURCE / relative).read_bytes())
    def assignment(parsed, name):
        return next(n.value for n in parsed.body if
                    isinstance(n, ast.AnnAssign) and n.target.id == name or
                    isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
    namespace = {"deepcopy": deepcopy, "_PACKET": json.loads((SOURCE / "backend/decks/historical_event_catalog.json").read_bytes())}
    for relative, selected in [("backend/decks/catalog.py", {"event_record", "historical_entry"}),
                               ("backend/decks/expansion_top_decks.py", {"_entry"})]:
        functions = [n for n in tree(relative).body if isinstance(n, ast.FunctionDef) and n.name in selected]
        exec(compile(ast.Module(body=functions, type_ignores=[]), "<public-deck-helpers>", "exec"), namespace)
    builtin = ast.literal_eval(assignment(tree("backend/decks/builtin_decks.py"), "BUILTIN_DECKS"))
    namespace["BUILTIN_DECKS"] = builtin
    expansion_tree = tree("backend/decks/expansion_top_decks.py")
    namespace["OTJ_DOMAIN_RAMP"] = ast.literal_eval(assignment(expansion_tree, "OTJ_DOMAIN_RAMP"))
    expansion = eval(compile(ast.Expression(assignment(expansion_tree, "EXPANSION_TOP_DECKS")), "<public-expansion>", "eval"), namespace)
    patterns = {key: eval(compile(ast.Expression(assignment(tree("backend/decks/parser.py"), key)), "<public-deck-grammar>", "eval"), {"re": re})
                for key in ("DECK_LINE", "SECTION_HEADER", "COMMENT_LINE")}
    names = set()
    for text in [*builtin.values(), *(row["deck_text"] for row in expansion)]:
        for line in text.splitlines():
            line = line.strip()
            if not line or patterns["SECTION_HEADER"].match(line) or patterns["COMMENT_LINE"].match(line):
                continue
            match = patterns["DECK_LINE"].match(line)
            assert match and int(match[1]) > 0
            names.add(match[2].strip())
    artifact = generator.build_artifact(SOURCE)
    assert (len(builtin), len(expansion), len(names)) == (11, 53, 149)
    assert artifact["builtin_decks_structural_sha256"] == structural(builtin)
    assert artifact["expansion_decks_structural_sha256"] == structural(expansion)
    entries = {row["name"]: row for row in artifact["startup_media"].values()}
    assert set(entries) == {alias for requested, row in SEED.items() for alias in (requested, row["name"])}
    for name in names:
        row = SEED.get(name) or next(row for row in SEED.values() if row["name"] == name)
        assert entries[name]["seed_row_sha256"] == structural(row)
    for name in ("Unknown Fixture Card", "Delver of Secrets // Bogus Face", "Counterparty alias"):
        assert name not in entries


@pytest.mark.parametrize("requested", sorted(SEED))
def test_actual_seed_rows_and_readable_svg(generator, requested):
    generator = generator()
    artifact = generator.build_artifact(SOURCE)
    row = SEED[requested]
    for name in {requested, row["name"]}:
        matches = [v for v in artifact["startup_media"].values() if v["name"] == name]
        assert len(matches) == 1
        entry = matches[0]
        assert set(entry) == {"name", "type_line", "seed_row_sha256", "content", "sha256"}
        assert entry["type_line"] == row["type_line"]
        assert entry["seed_row_sha256"] == structural(row)
        assert entry["sha256"] == hashlib.sha256(entry["content"].encode()).hexdigest()
        assert ET.fromstring(entry["content"]).tag == "{http://www.w3.org/2000/svg}svg"


def test_existing_placeholder_helpers_are_reused_exactly(generator):
    generator = generator()
    artifact = generator.build_artifact(SOURCE)
    import html
    import re
    tree = ast.parse((SOURCE / "backend/card_data/placeholders.py").read_bytes())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"_family", "_slug", "_svg_for"}]
    namespace = {"html": html, "re": re}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<canonical-placeholder-functions>", "exec"), namespace)
    for filename, entry in artifact["startup_media"].items():
        family = namespace["_family"](entry["type_line"], False)
        assert filename == "placeholder-" + family + "-" + namespace["_slug"](entry["name"], entry["type_line"] or family) + ".svg"
        assert entry["content"] == namespace["_svg_for"](family, name=entry["name"], type_line=entry["type_line"], token=False)


@pytest.mark.parametrize("relative", INPUT_PATHS)
def test_missing_and_changed_public_inputs_fail_closed(generator, copied_source, relative):
    generator = generator()
    path = copied_source / relative
    data = path.read_bytes()
    path.unlink()
    with pytest.raises((ValueError, OSError)):
        generator.build_artifact(copied_source)
    path.write_bytes(data + b"\n")
    with pytest.raises(ValueError, match="digest"):
        generator.build_artifact(copied_source)


@pytest.mark.parametrize("fault", ["row_hash", "missing_name", "unknown_name", "missing_type"])
def test_seed_row_and_name_faults_cannot_gain_artifact(generator, copied_source, fault):
    generator = generator()
    path = copied_source / "backend/card_data/builtin_oracle_seed.json"
    packet = json.loads(path.read_bytes())
    row = packet["cards"]["Lightning Bolt"]
    if fault == "row_hash":
        row["oracle_text"] += " injected"
    elif fault == "missing_name":
        del row["name"]
    elif fault == "unknown_name":
        packet["cards"]["Unknown Fixture Card"] = packet["cards"].pop("Lightning Bolt")
    else:
        del row["type_line"]
    path.write_text(json.dumps(packet), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        generator.build_artifact(copied_source)


@pytest.mark.parametrize("relative", INPUT_PATHS)
def test_source_file_symlink_rejected_even_when_bytes_match(generator, copied_source, relative):
    generator = generator()
    path = copied_source / relative
    path.unlink()
    path.symlink_to(SOURCE / relative)
    with pytest.raises(ValueError, match="symlink"):
        generator.build_artifact(copied_source)


def test_fake_and_symlink_source_roots_rejected(generator, tmp_path):
    generator = generator()
    with pytest.raises((ValueError, OSError)):
        generator.build_artifact(tmp_path / "missing")
    link = tmp_path / "source-link"
    link.symlink_to(SOURCE, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        generator.build_artifact(link)


def test_exclusive_output_bundle_and_cli(generator, tmp_path):
    generator = generator()
    output = tmp_path / "bundle"
    assert generator.main(["--source-root", str(SOURCE), "--output-dir", str(output)]) == 0
    manifest = output / "startup-media-pins.json"
    artifact = json.loads(manifest.read_bytes())
    assert artifact == generator.build_artifact(SOURCE)
    fixtures = output / "fixtures"
    assert {p.name for p in fixtures.iterdir()} == set(artifact["startup_media"])
    for filename, entry in artifact["startup_media"].items():
        assert (fixtures / filename).read_bytes() == entry["content"].encode("utf-8")
    old = manifest.read_bytes()
    with pytest.raises(FileExistsError):
        generator.write_bundle(SOURCE, output)
    assert manifest.read_bytes() == old
    other = tmp_path / "second"
    generator.write_bundle(SOURCE, other)
    assert (other / "startup-media-pins.json").read_bytes() == old


@pytest.mark.parametrize("kind", ["file", "symlink", "parent_symlink"])
def test_output_fake_paths_and_symlinks_never_overwritten(generator, tmp_path, kind):
    generator = generator()
    target = tmp_path / "target"
    target.mkdir()
    sentinel = target / "preserve"
    sentinel.write_bytes(b"operator-owned")
    output = tmp_path / "bundle"
    if kind == "file":
        output.write_bytes(b"existing")
    elif kind == "symlink":
        output.symlink_to(target, target_is_directory=True)
    else:
        output.symlink_to(target, target_is_directory=True)
        output = output / "child"
    with pytest.raises((ValueError, FileExistsError)):
        generator.write_bundle(SOURCE, output)
    assert sentinel.read_bytes() == b"operator-owned"
    assert not (target / "child").exists()


def test_invalid_source_leaves_no_output(generator, copied_source, tmp_path):
    generator = generator()
    (copied_source / "backend/main.py").write_text("raise RuntimeError('must never execute')\n")
    output = tmp_path / "not-created"
    with pytest.raises(ValueError, match="digest"):
        generator.write_bundle(copied_source, output)
    assert not output.exists()
