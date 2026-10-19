"""Generate public startup consistency pins and SVG fixtures, without startup.

Only the reviewed finite source revision below is accepted. This bundle grants
no SQL, application, browser, media-write, or operator lease authority.
"""
from __future__ import annotations

import argparse
import ast
import __future__
from copy import deepcopy
import hashlib
import html
import json
import os
from pathlib import Path
import re
import stat


# Updated only through an explicit source-binding review, never a wildcard.
SOURCE_MODULE_PINS = {'backend/main.py': '0e163563dfabf109964588d53a2a56504745b032fd56ec44818d5a95258fec9f',
 'backend/decks/bootstrap.py': 'b968836717698f55e28f0d5b2942209e45ba47d9c67cb3423aa67579274e559b',
 'backend/card_data/hydration.py': '8497ed903beccf72deba05bf5f03b5342c223cd98eb7c68bc86633f8b2455cce',
 'backend/card_data/display.py': 'f7c584f6bccb22696bc3dfa83563248b6253e597ce87e493924088962c9765eb',
 'backend/card_data/placeholders.py': '44a0ba20815a7204ee2f0332bb5dbd30c648140e78b9cee004aca5ad57acf4df',
 'backend/card_data/seed_cards.py': 'cb64ae85690d5239a24895b4ed6ac8a46b5f4c15de64d5bb67192eb187b72c71',
 'backend/decks/expansion_top_decks.py': 'df9d1667460859fc21be97ac07c8ae2a02b9980acd9391eb596f526d889b500b',
 'backend/persistence/capacity.py': 'fa0aa11cc1da4cdc13a646989fef86d2cda05b43dea9f1d10a1d4078cb5e4bf5'}
PUBLIC_INPUT_PINS = {
    **SOURCE_MODULE_PINS,
    'backend/card_data/builtin_oracle_seed.json': '9296ec1b24654374aaca985b92dc4c3b62a93e6fd024afcd6b4acd61a6007037',
    'backend/decks/builtin_decks.py': '236bc11807d9aeea3134c2b1ec9d1fa73a29d9dc366bf0e11a79ed605a14c0b3',
    'backend/decks/catalog.py': 'a3907784a4f097c6a460d38a46569dd1bd68ccf26b903d083ce6b77f4ac08aa0',
    'backend/decks/historical_event_catalog.json': '2c589f58596f09b3d3b2e7387e5bebe23030fa5c5c11c510f48f655e2c200277',
}


def _checked_directory(path: Path) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("An absolute canonical path is required")
    for parent in [*reversed(path.parents), path]:
        mode = parent.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("symlink paths are not accepted")
        if not stat.S_ISDIR(mode):
            raise ValueError("Directory path required")


def _read_public(root: Path, relative: str) -> bytes:
    path = root / relative
    _checked_directory(path.parent)
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise ValueError("symlink input is not accepted")
    if not stat.S_ISREG(mode):
        raise ValueError("Regular public source file required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("Regular public source file required")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read()
    finally:
        os.close(fd)
    if hashlib.sha256(data).hexdigest() != PUBLIC_INPUT_PINS[relative]:
        raise ValueError("Public input digest mismatch: " + relative)
    return data


def _structural(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def _functions(tree: ast.Module, names: tuple[str, ...], namespace: dict) -> None:
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in selected} != set(names) or len(selected) != len(names):
        raise ValueError("Missing canonical helper names")
    # Entire input bytes were pinned before selecting these existing pure bodies.
    exec(compile(ast.Module(body=selected, type_ignores=[]), "<pinned-public-helpers>",
                 "exec", flags=__future__.annotations.compiler_flag, dont_inherit=True), namespace)


def _assignment(tree: ast.Module, name: str):
    matches = [n.value for n in tree.body if
               isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == name
               or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    if len(matches) != 1:
        raise ValueError("Missing canonical assignment: " + name)
    return matches[0]


def build_artifact(source_root: Path) -> dict:
    """Read only twelve closed public paths; never import project modules."""
    root = Path(source_root)
    _checked_directory(root)
    data = {p: _read_public(root, p) for p in PUBLIC_INPUT_PINS}
    trees = {p: ast.parse(value, filename=p) for p, value in data.items() if p.endswith(".py")}
    for p, tree in trees.items():
        compile(tree, p, "exec", dont_inherit=True)  # Syntax check only; no module execution.
    seed = json.loads(data["backend/card_data/builtin_oracle_seed.json"])["cards"]
    builtin = ast.literal_eval(_assignment(trees["backend/decks/builtin_decks.py"], "BUILTIN_DECKS"))
    namespace = {"__builtins__": {"str": str, "int": int}, "deepcopy": deepcopy,
                 "_PACKET": json.loads(data["backend/decks/historical_event_catalog.json"]),
                 "BUILTIN_DECKS": builtin, "html": html, "re": re, "SEED_CARD_DATA": seed}
    _functions(trees["backend/decks/catalog.py"], ("event_record", "historical_entry"), namespace)
    expansion_tree = trees["backend/decks/expansion_top_decks.py"]
    _functions(expansion_tree, ("_entry",), namespace)
    namespace["OTJ_DOMAIN_RAMP"] = ast.literal_eval(_assignment(expansion_tree, "OTJ_DOMAIN_RAMP"))
    expansion = eval(compile(ast.Expression(_assignment(expansion_tree, "EXPANSION_TOP_DECKS")),
                             "<pinned-expansion-definition>", "eval"), namespace)
    seed_tree = trees["backend/card_data/seed_cards.py"]
    _functions(seed_tree, ("_normalize_card_name", "seed_card_payload"), namespace)
    namespace["_NORMALIZED_SEED_CARD_DATA"] = eval(compile(
        ast.Expression(_assignment(seed_tree, "_NORMALIZED_SEED_CARD_DATA")),
        "<pinned-seed-aliases>", "eval"), namespace)
    _functions(trees["backend/card_data/placeholders.py"], ("_family", "_slug", "_svg_for"), namespace)
    media = {}
    if type(seed) is not dict or len(seed) != 155:
        raise ValueError("Canonical 155-row seed required")
    for requested, row in sorted(seed.items()):
        if (type(row) is not dict or type(requested) is not str or not requested
                or type(row.get("name")) is not str or not row["name"]
                or type(row.get("type_line")) is not str or not row["type_line"]):
            raise ValueError("Missing canonical seed name or type")
        for name in sorted({requested, row["name"]}):
            if namespace["seed_card_payload"](name) is not row:
                raise ValueError("Unknown or ambiguous canonical seed alias")
            type_line = row["type_line"]
            family = namespace["_family"](type_line=type_line, token=False)
            filename = "placeholder-" + family + "-" + namespace["_slug"](name, type_line or family) + ".svg"
            content = namespace["_svg_for"](family, name=name, type_line=type_line, token=False)
            entry = {"name": name, "type_line": type_line, "seed_row_sha256": _structural(row),
                     "content": content, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
            if filename in media and media[filename] != entry:
                raise ValueError("Canonical fixture filename collision")
            media[filename] = entry
    return {"source_module_pins": dict(SOURCE_MODULE_PINS), "seed_cards_structural_sha256": _structural(seed),
            "builtin_decks_structural_sha256": _structural(builtin),
            "expansion_decks_structural_sha256": _structural(expansion), "startup_media": media}


def _write_exclusive(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        remaining = memoryview(data)
        while remaining:
            count = os.write(fd, remaining)
            if count == 0:
                raise OSError("Incomplete fixture write")
            remaining = remaining[count:]
    finally:
        os.close(fd)


def write_bundle(source_root: Path, output_dir: Path) -> Path:
    """Exclusively create a fresh bundle outside source; manifest written last."""
    source, output = Path(source_root), Path(output_dir)
    _checked_directory(output.parent)
    if output.is_relative_to(source):
        raise ValueError("Output must be outside the public source tree")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Exclusive output directory already exists")
    artifact = build_artifact(source)
    output.mkdir(mode=0o700)  # Never merge, overwrite, or follow an existing destination.
    fixtures = output / "fixtures"
    fixtures.mkdir(mode=0o700)
    for filename, entry in sorted(artifact["startup_media"].items()):
        _write_exclusive(fixtures / filename, entry["content"].encode("utf-8"))
    manifest = output / "startup-media-pins.json"
    _write_exclusive(manifest, (json.dumps(artifact, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    write_bundle(args.source_root, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
