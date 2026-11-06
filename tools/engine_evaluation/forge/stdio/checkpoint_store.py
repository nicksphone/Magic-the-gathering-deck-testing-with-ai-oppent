# SPDX-License-Identifier: GPL-3.0-or-later
# Original private host checkpoint store for the Forge Team/Card-Forge engine.
"""Archive native pending frontiers, not engine installations or wire tokens.

The trusted deployment caller supplies the engine build ID. These local-host
APIs do not accept browser commands, run an engine, or infer accepted choices.
"""
from contextlib import contextmanager
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import uuid


_SNAPSHOT_LIMIT = 64 * 1024 * 1024
_MANIFEST_LIMIT = 4096
_SNAPSHOT_KEYS = {"schema", "spec", "decks", "starts", "completions",
                  "pending_offer", "actor_view", "native_state", "journals"}
_JOURNAL_KEYS = {"starts", "completions", "native", "paid-pending", "final"}
_MANIFEST_KEYS = {"schema", "build_id", "checkpoint_sha256"}
_WIRE_KEYS = {"request_id", "token", "tokens"}
_HEX64 = re.compile(r"[0-9a-f]{64}")


class CheckpointError(ValueError):
    """Invalid, incompatible, unsafe, or unavailable local checkpoint."""


@contextmanager
def _errors():
    try:
        yield
    except CheckpointError:
        raise
    except (OSError, ValueError, TypeError, RecursionError, OverflowError) as error:
        raise CheckpointError("Invalid or unavailable checkpoint") from error


def _require(condition, message):
    if not condition:
        raise CheckpointError(message)


def _integer(value, minimum=0, maximum=None):
    return type(value) is int and value >= minimum and (maximum is None or value <= maximum)


def _object(value, name):
    _require(type(value) is dict, name + " must be an object")


def _hex64(value):
    return type(value) is str and _HEX64.fullmatch(value) is not None


def _json_tree(value):
    if type(value) is dict:
        for key, item in value.items():
            _require(type(key) is str, "JSON object keys must be strings")
            _json_tree(item)
    elif type(value) is list:
        for item in value:
            _json_tree(item)
    else:
        _require(value is None or type(value) in (str, bool, int, float), "Non-JSON value")
        if type(value) is float:
            _require(math.isfinite(value), "Non-finite JSON number")


def _encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON object key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise CheckpointError("Non-JSON number")


def _decode(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=_invalid_constant)


def _same_json(left, right):
    # Python's True == 1 must not hide a changed nested JSON value.
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same_json(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same_json(a, b) for a, b in zip(left, right))
    return left == right


def _basename(name):
    _require(type(name) is str and name not in ("", ".", "..")
             and not any(c in name for c in ("/", "\\", "\x00")), "Unsafe deck basename")


def _token_free(value):
    if type(value) is dict:
        _require(not (_WIRE_KEYS & value.keys()), "Opaque wire tokens are not checkpoint inputs")
        for item in value.values():
            _token_free(item)
    elif type(value) is list:
        for item in value:
            _token_free(item)


def _validate(checkpoint):
    _json_tree(checkpoint)
    _require(len(_encode(checkpoint)) <= _SNAPSHOT_LIMIT, "Checkpoint exceeds size limit")
    _object(checkpoint, "Checkpoint")
    _require(set(checkpoint) == _SNAPSHOT_KEYS, "Unexpected checkpoint schema")
    _require(type(checkpoint["schema"]) is int and checkpoint["schema"] == 1,
             "Unsupported checkpoint schema")
    spec, decks = checkpoint["spec"], checkpoint["decks"]
    _object(spec, "Spec")
    _require(_integer(spec.get("human_seat"), 0, 1), "Invalid human seat")
    rows = spec.get("decks")
    _require(type(rows) is list and len(rows) == 2, "Exactly two deck rows required")
    references = set()
    for row in rows:
        _object(row, "Spec deck")
        name = row.get("file")
        _basename(name)
        references.add(name)
    _object(decks, "Decks")
    for name, text in decks.items():
        _basename(name)
        _require(type(text) is str, "Deck text must be a string")
    _require(references == set(decks), "Imported deck basenames do not match spec")
    starts, completions = checkpoint["starts"], checkpoint["completions"]
    _require(_integer(starts, 0, 1000) and _integer(completions, 0, 1000)
             and completions <= starts, "Invalid invocation counts")
    offer, view, native = (checkpoint[k] for k in ("pending_offer", "actor_view", "native_state"))
    _object(offer, "Pending offer")
    _object(view, "Actor view")
    _object(native, "Native state")
    _require(type(offer.get("kind")) is str and bool(offer["kind"]), "Invalid pending kind")
    _require(_integer(offer.get("min")) and _integer(offer.get("max"))
             and offer["min"] <= offer["max"], "Invalid pending bounds")
    _require(type(offer.get("choices")) is list and type(offer.get("info")) is dict,
             "Invalid pending choices or info")
    _require(_integer(offer.get("turn")) and type(offer.get("phase")) is str,
             "Invalid pending turn or phase")
    _token_free(offer)
    actor = offer.get("actor")
    _require(_integer(actor) and _integer(view.get("actor_id")) and actor == view["actor_id"],
             "Pending actor does not match actor view")
    players = native.get("players")
    _require(type(players) is list and bool(players), "Native players required")
    player_ids = set()
    for player in players:
        _object(player, "Native player")
        player_id = player.get("id")
        _require(_integer(player_id) and player_id not in player_ids, "Invalid native player ID")
        player_ids.add(player_id)
    _require(actor in player_ids, "Pending actor is not a native player")
    _require(type(native.get("stack")) is list and _integer(native.get("turn"))
             and type(native.get("phase")) is str and _integer(native.get("rng_delta")),
             "Invalid native stack, turn, phase or RNG")
    journals = checkpoint["journals"]
    _object(journals, "Journals")
    _require(set(journals) == _JOURNAL_KEYS, "Unexpected journal streams")
    for stream in journals.values():
        _require(type(stream) is list and all(type(row) is dict for row in stream),
                 "Journals must contain lists of object rows")
    _require(not journals["final"], "Checkpoint is not an unfinished frontier")
    _require(len(journals["starts"]) == starts and len(journals["completions"]) == completions,
             "Journal lengths do not match counts")
    for index, row in enumerate(journals["starts"]):
        _require(_integer(row.get("start_id")) and row["start_id"] == index,
                 "Start IDs must be consecutive and ordered")
        _require(type(row.get("kind")) is str and bool(row["kind"])
                 and type(row.get("ticket")) is dict, "Invalid start kind or ticket")
        _token_free(row["ticket"])
    completed = set()
    for row in journals["completions"]:
        index = row.get("start_id")
        _require(_integer(index) and index < starts and index not in completed,
                 "Duplicate or unknown completed start")
        original = journals["starts"][index]
        _require(type(row.get("kind")) is str and row["kind"] == original["kind"]
                 and type(row.get("ticket")) is dict
                 and _same_json(row["ticket"], original["ticket"]), "Completion kind or ticket changed")
        completed.add(index)


@contextmanager
def _directory(path):
    path = Path(path)
    _require(".." not in path.parts, "Parent traversal is not permitted")
    if not path.is_absolute():
        path = Path.cwd() / path
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in path.parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _read_at(directory_fd, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    with os.fdopen(fd, "rb") as handle:
        metadata = os.fstat(handle.fileno())
        _require(stat.S_ISREG(metadata.st_mode), "Regular checkpoint file required")
        _require(metadata.st_size <= limit, "Checkpoint file exceeds size limit")
        raw = handle.read(limit + 1)
    _require(len(raw) <= limit, "Checkpoint file exceeds size limit")
    return raw


def _write_at(directory_fd, name, raw):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=directory_fd)
    with os.fdopen(fd, "wb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _rename_noreplace(parent_fd, source, destination):
    # rename() can overwrite a racing empty directory. Linux RENAME_NOREPLACE
    # publishes the entire private directory atomically without that race.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    _require(rename is not None, "Atomic no-replace directory rename is unavailable")
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(parent_fd, os.fsencode(source), parent_fd, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _publish(destination, files, decks=None):
    destination = Path(destination)
    _require(destination.name not in ("", ".", ".."), "Fresh named destination required")
    with _directory(destination.parent) as parent_fd:
        try:
            os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise CheckpointError("Destination already exists")
        staging = ".native-checkpoint-" + uuid.uuid4().hex
        os.mkdir(staging, 0o700, dir_fd=parent_fd)
        stage_fd = os.open(staging, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        deck_fd = None
        published = False
        try:
            os.fchmod(stage_fd, 0o700)
            for name, raw in files.items():
                _write_at(stage_fd, name, raw)
            if decks is not None:
                os.mkdir("decks", 0o700, dir_fd=stage_fd)
                deck_fd = os.open("decks", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=stage_fd)
                os.fchmod(deck_fd, 0o700)
                for name, raw in decks.items():
                    _write_at(deck_fd, name, raw)
                os.fsync(deck_fd)
            os.fsync(stage_fd)
            _rename_noreplace(parent_fd, staging, destination.name)
            published = True
            os.fsync(parent_fd)
        finally:
            # Remove only this operation's unpublished staging files, never a
            # destination (including one created by another writer).
            if not published:
                if deck_fd is not None:
                    for name in os.listdir(deck_fd):
                        os.unlink(name, dir_fd=deck_fd)
                    os.rmdir("decks", dir_fd=stage_fd)
                for name in files:
                    try:
                        os.unlink(name, dir_fd=stage_fd)
                    except FileNotFoundError:
                        pass
                os.rmdir(staging, dir_fd=parent_fd)
            if deck_fd is not None:
                os.close(deck_fd)
            os.close(stage_fd)


def save_checkpoint(snapshot_path: Path, destination: Path, *, build_id: str) -> None:
    """Validate and privately archive exact snapshot bytes for a pinned build."""
    with _errors():
        _require(_hex64(build_id), "Trusted build ID must be 64 lowercase hex characters")
        snapshot_path = Path(snapshot_path)
        with _directory(snapshot_path.parent) as parent_fd:
            raw = _read_at(parent_fd, snapshot_path.name, _SNAPSHOT_LIMIT)
        _validate(_decode(raw))
        manifest = {"schema": 1, "build_id": build_id,
                    "checkpoint_sha256": hashlib.sha256(raw).hexdigest()}
        _publish(destination, {"CHECKPOINT.json": raw, "manifest.json": _encode(manifest)})


def load_checkpoint(directory: Path, *, build_id: str) -> dict:
    """Load only a bounded, hash-verified archive from the same pinned build."""
    with _errors():
        _require(_hex64(build_id), "Trusted build ID must be 64 lowercase hex characters")
        with _directory(directory) as fd:
            expected = {"CHECKPOINT.json", "manifest.json"}
            _require(set(os.listdir(fd)) == expected, "Unexpected checkpoint archive entries")
            manifest = _decode(_read_at(fd, "manifest.json", _MANIFEST_LIMIT))
            _object(manifest, "Manifest")
            _require(set(manifest) == _MANIFEST_KEYS, "Unexpected manifest schema")
            _require(type(manifest["schema"]) is int and manifest["schema"] == 1,
                     "Unsupported manifest schema")
            _require(_hex64(manifest["build_id"]) and manifest["build_id"] == build_id,
                     "Checkpoint build ID mismatch")
            _require(_hex64(manifest["checkpoint_sha256"]), "Invalid checkpoint digest")
            raw = _read_at(fd, "CHECKPOINT.json", _SNAPSHOT_LIMIT)
            _require(hashlib.sha256(raw).hexdigest() == manifest["checkpoint_sha256"],
                     "Checkpoint byte hash mismatch")
            _require(set(os.listdir(fd)) == expected, "Checkpoint archive entries changed")
        checkpoint = _decode(raw)
        _validate(checkpoint)
        return checkpoint


def restore_inputs(checkpoint: dict, destination: Path) -> None:
    """Restore original semantic spec and exact deck text, never journal commands."""
    with _errors():
        _validate(checkpoint)
        _publish(destination, {"SPEC.json": _encode(checkpoint["spec"])},
                 {name: text.encode("utf-8") for name, text in checkpoint["decks"].items()})


def verify_frontier(saved: dict, current: dict) -> None:
    """Require the entire validated native frontier to match before further play."""
    with _errors():
        _validate(saved)
        _validate(current)
        _require(_same_json(saved, current), "Native checkpoint frontier mismatch")
