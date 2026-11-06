"""Opt-in local Forge process ownership, not Python rules or native-game policy.

Only operator configuration supplies commands and paths. Public snapshots contain
ActorBoundary projections, never native journals, replay offers or raw errors.
Original host transport implementation; underlying card rules and AI are by the
Forge Team/Card-Forge. See THIRD-PARTY-NOTICES for upstream attribution.
"""
from __future__ import annotations

from collections import deque
import copy
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import signal
import stat
import subprocess
import threading
import time
import uuid


_FRAME_LIMIT = 2 * 1024 * 1024
_TRANSCRIPT_LIMIT = 16 * 1024 * 1024
_FRAME_COUNT_LIMIT = 20000
_MAX_ACTIONS = 1000
_MAX_RECORDS = 128
_WALL_TIMEOUT = 7200
_IDLE_TIMEOUT = 600
_EXIT_GRACE = 3
_TERM_GRACE = .3
_KILL_GRACE = 1
_WRITE_TIMEOUT = 1
_LAUNCH_TIMEOUT = 5
_POLL = .05
_OPAQUE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
_CAPABILITY = re.compile(r"[0-9a-f]{64}")
_ZONES = {"Hand", "Library", "Graveyard", "Battlefield", "Exile", "Command", "Sideboard"}
_TERMINAL = {"completed", "aborted", "failed"}


class ForgeError(ValueError):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class _ProtocolError(ValueError):
    pass


def _require(condition):
    if not condition:
        raise _ProtocolError("Invalid native projection")


def _integer(value, minimum=0, maximum=2**63 - 1):
    return type(value) is int and minimum <= value <= maximum


def _text(value, limit=65536):
    _require(type(value) is str and len(value) <= limit)
    value.encode("utf-8")
    return value


def _opaque(value):
    _require(type(value) is str and _OPAQUE.fullmatch(value) is not None)
    return value


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _nonfinite(_value):
    raise _ProtocolError("Non-finite JSON")


def _decode(raw):
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)


def _encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _fingerprint(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False,
                     separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).digest()


def _key(value):
    if (type(value) is not str or not 1 <= len(value) <= 100
            or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value)):
        raise ForgeError(422, "invalid_key", "Supply a bounded request key")
    return value


def _capability_hash(value):
    if type(value) is not str or _CAPABILITY.fullmatch(value) is None:
        raise ForgeError(401, "invalid_capability", "Native session capability required")
    return hashlib.sha256(value.encode("ascii")).digest()


def _safe_name(value, maximum):
    if (type(value) is not str or not value.strip() or len(value) > maximum
            or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF
                   or c in "[]\u2028\u2029" for c in value)):
        raise ForgeError(422, "invalid_deck", "Deck names must be bounded single-line text")
    return value


def _start_payload(payload):
    required = {"deck_a", "deck_b", "name_a", "name_b", "human_seat"}
    if type(payload) is not dict or not required <= payload.keys() or payload.keys() - required - {"seed"}:
        raise ForgeError(422, "invalid_start", "Invalid native start fields")
    if not _integer(payload["human_seat"], 0, 1) or (
            "seed" in payload and not _integer(payload["seed"])):
        raise ForgeError(422, "invalid_start", "Invalid native seat or seed")
    decks = []
    for label, filename in (("a", "a.dck"), ("b", "b.dck")):
        name = _safe_name(payload["name_" + label], 200)
        rows = payload["deck_" + label]
        if type(rows) is not list or not 1 <= len(rows) <= 60:
            raise ForgeError(422, "invalid_deck", "Exactly 60 mainboard cards required")
        main = {}
        for row in rows:
            if (type(row) is not dict or set(row) != {"quantity", "card_name"}
                    or not _integer(row["quantity"], 1, 60)):
                raise ForgeError(422, "invalid_deck", "Invalid mainboard entry")
            card = _safe_name(row["card_name"], 200)
            main[card] = main.get(card, 0) + row["quantity"]
        if sum(main.values()) != 60:
            raise ForgeError(422, "invalid_deck", "Exactly 60 mainboard cards required")
        decks.append({"file": filename, "name": name, "main": main})
    return {"human_seat": payload["human_seat"], "open_decklists": True,
            "flat_monte_carlo": False, "seed": payload.get("seed", secrets.randbits(63)), "decks": decks}


def _local_root(path):
    _require(path.is_absolute() and ".." not in path.parts)
    _require(not any(parent.is_symlink() for parent in (path, *path.parents)))
    # Linux mount metadata avoids spawning a command or placing private files on NFS.
    mounts = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        mount = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), left.split()[4])
        if path == Path(mount) or Path(mount) in path.parents:
            mounts.append((len(mount), right.split()[0]))
    _require(bool(mounts))
    filesystem = max(mounts)[1]
    _require(filesystem not in {"nfs", "nfs4", "cifs", "smbfs", "9p", "ceph", "autofs"}
             and not filesystem.startswith("fuse."))
    if path.exists():
        metadata = path.stat()
        _require(stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == os.geteuid()
                 and stat.S_IMODE(metadata.st_mode) == 0o700)
    else:
        _require(path.parent.is_dir())


@dataclass(frozen=True)
class RuntimeConfig:
    argv: tuple[str, ...]
    cwd: Path
    sessions_dir: Path
    build_id: str

    def __post_init__(self):
        try:
            _require(type(self.argv) in (list, tuple) and bool(self.argv)
                     and all(type(arg) is str and arg and "\x00" not in arg for arg in self.argv))
            _require(os.path.isabs(self.argv[0]) and "{session}" not in self.argv[0]
                     and any("{session}" in arg for arg in self.argv))
            _require(all("{" not in arg.replace("{session}", "")
                         and "}" not in arg.replace("{session}", "") for arg in self.argv))
            object.__setattr__(self, "argv", tuple(self.argv))
            object.__setattr__(self, "cwd", Path(self.cwd))
            object.__setattr__(self, "sessions_dir", Path(self.sessions_dir))
            _require(self.cwd.is_absolute() and self.cwd.is_dir())
            _require(type(self.build_id) is str and _CAPABILITY.fullmatch(self.build_id) is not None)
            _local_root(self.sessions_dir)
        except (OSError, ValueError, TypeError, RecursionError):
            raise ForgeError(503, "invalid_runtime_config", "Native runtime configuration unavailable") from None

    @classmethod
    def from_file(cls, path):
        try:
            with Path(path).open("rb") as handle:
                raw = handle.read(65537)
            _require(len(raw) <= 65536)
            value = _decode(raw)
            _require(type(value) is dict and set(value) == {"argv", "cwd", "sessions_dir", "build_id"})
            return cls(**value)
        except (OSError, ValueError, TypeError, RecursionError):
            raise ForgeError(503, "invalid_runtime_config", "Native runtime configuration unavailable") from None


def _face(value):
    _require(type(value) is dict)
    result = {key: _text(value[key]) for key in ("name", "type", "mana_cost", "oracle_text")}
    for key in ("power", "toughness"):
        _require(_integer(value[key], -(2**63)))
        result[key] = value[key]
    return result


def _card(value):
    _require(type(value) is dict)
    if value.get("hidden") is True:
        return {"hidden": True}
    result = {}
    for key in ("card_id", "controller_id", "owner_id"):
        _require(_integer(value[key]))
        result[key] = value[key]
    for key in ("tapped", "face_down"):
        _require(type(value[key]) is bool)
        result[key] = value[key]
    result["face"] = _face(value["face"])
    if "known_face" in value:
        result["known_face"] = _face(value["known_face"])
    return result


def _display(value):
    if type(value) in (str, bool, int):
        if type(value) is str:
            _text(value)
        return value
    _require(type(value) is dict)
    if "stack_id" in value:
        _require(_integer(value["stack_id"]))
        return {"stack_id": value["stack_id"], "source": _card(value["source"])}
    if "ability_id" in value:
        _require(_integer(value["ability_id"]))
        return {"ability_id": value["ability_id"], "description": _text(value["description"]),
                "source": _card(value["source"])}
    if "player_id" in value:
        _require(_integer(value["player_id"]))
        return {"player_id": value["player_id"], "name": _text(value["name"])}
    return _card(value)


def _state(value):
    _require(type(value) is dict and _integer(value["actor_id"]) and _integer(value["turn"]))
    _require(type(value["players"]) is list and len(value["players"]) == 2)
    players, ids = [], set()
    for player in value["players"]:
        _require(type(player) is dict and _integer(player["player_id"])
                 and player["player_id"] not in ids and _integer(player["life"], -(2**63)))
        ids.add(player["player_id"])
        source = player["zones"]
        _require(type(source) is dict and set(source) == _ZONES)
        zones = {}
        for key, zone in source.items():
            _require(type(zone) is dict and _integer(zone["count"], 0, 100000)
                     and type(zone["visible_cards"]) is list
                     and len(zone["visible_cards"]) <= zone["count"])
            zones[key] = {"count": zone["count"], "visible_cards": [_card(card) for card in zone["visible_cards"]]}
        players.append({"player_id": player["player_id"], "name": _text(player["name"]),
                        "life": player["life"], "zones": zones})
    _require(value["actor_id"] in ids and type(value["stack"]) is list and len(value["stack"]) <= 1000)
    stack = []
    for entry in value["stack"]:
        _require(type(entry) is dict and _integer(entry["stack_id"]))
        stack.append({"stack_id": entry["stack_id"], "source": _card(entry["source"])})
    return {"actor_id": value["actor_id"], "turn": value["turn"], "phase": _text(value["phase"], 128),
            "players": players, "stack": stack}


def _question(value, actor):
    _require(type(value) is dict and type(value["actor_id"]) is int and value["actor_id"] == actor
             and _integer(value["min"], 0, 256) and _integer(value["max"], value["min"], 256)
             and type(value["choices"]) is list and len(value["choices"]) <= 256
             and value["max"] <= len(value["choices"]))
    choices, tokens = [], set()
    for row in value["choices"]:
        _require(type(row) is dict)
        token = _opaque(row["token"])
        _require(token not in tokens)
        tokens.add(token)
        choices.append({"token": token, "display": _display(row["display"])})
    kind = _text(value["kind"], 128)
    _require(bool(kind))
    return {"actor_id": actor, "request_id": _opaque(value["request_id"]), "kind": kind,
            "min": value["min"], "max": value["max"], "choices": choices}


def _info(value, actor):
    _require(type(value) is dict)
    result = {key: _text(value[key]) for key in ("prompt", "title", "ok_label", "cancel_label") if key in value}
    if "labels" in value:
        _require(type(value["labels"]) is list and len(value["labels"]) <= 256)
        result["labels"] = [_text(label) for label in value["labels"]]
    for key in ("selection", "stack_selection"):
        if key not in value:
            continue
        row = value[key]
        _require(type(row) is dict and type(row["actor"]) is int and row["actor"] == actor
                 and type(row["chosen"]) is list and len(row["chosen"]) <= 256)
        selection = {"actor": actor, "input": _text(row["input"], 128),
                     "chosen": [_display(item) for item in row["chosen"]]}
        for name in ("generation", "priority_epoch", "revision"):
            _require(_integer(row[name]))
            selection[name] = row[name]
        if key == "selection":
            _require(_integer(row["min"], 0, 256) and _integer(row["max"], row["min"], 256))
            selection.update(min=row["min"], max=row["max"])
        result[key] = selection
    return result


def _private_file(path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.fchmod(fd, 0o600)
    return os.fdopen(fd, "wb", buffering=0)


class _Session:
    def __init__(self, config, session_id, capability, spec):
        self.config, self.id, self.capability = config, session_id, capability
        self.directory = config.sessions_dir / session_id
        self.lock = threading.RLock()
        self.stopping, self.closed = threading.Event(), threading.Event()
        self.launched = threading.Event()
        self.process = self.reader = None
        self.files = []
        self.actions, self.awaiting, self.invocations = {}, deque(), {}
        self.requests = set()
        self.last_action = None
        self.starts = self.completions = 0
        self.deferred = self.pending_result = None
        self.result_at = None
        self.activity_at = time.monotonic()
        self.data = {"engine": "forge", "session_id": session_id, "sequence": 0, "status": "starting",
                     "actor_id": None, "state": None, "question": None, "info": {},
                     "last_answer": None, "result": None, "error": None}
        try:
            _local_root(config.sessions_dir)
            config.sessions_dir.mkdir(mode=0o700, exist_ok=True)
            self.directory.mkdir(mode=0o700)
            (self.directory / "decks").mkdir(mode=0o700)
            with _private_file(self.directory / "SPEC.json") as handle:
                handle.write(_encode(spec))
            for row in spec["decks"]:
                text = "[metadata]\nName=" + row["name"] + "\n[Main]\n"
                text += "".join(str(quantity) + " " + name + "\n" for name, quantity in row["main"].items())
                with _private_file(self.directory / "decks" / row["file"]) as handle:
                    handle.write(text.encode("utf-8"))
            for name in ("stdout.private.jsonl", "stderr.private.log"):
                self.files.append(_private_file(self.directory / name))
            self.reader = threading.Thread(target=self._run, name="forge-" + session_id, daemon=True)
            self.reader.start()
            if not self.launched.wait(timeout=_LAUNCH_TIMEOUT):
                self._fail("native_launch_timeout", "Native worker launch did not finish in time")
            elif self.stopping.is_set():
                self.reader.join(timeout=_POLL + _TERM_GRACE + _KILL_GRACE + 1)
        except (OSError, ValueError, TypeError, RuntimeError):
            self._fail("native_launch_failed", "Native worker could not start")
            self._shutdown()
            self.closed.set()
            self.launched.set()

    def _run(self):
        # Linux parent-death signals follow the creating thread, not just its
        # process. Keep Popen on this owner until the child has been reaped.
        try:
            try:
                if self.stopping.is_set():
                    return
                argv = [arg.replace("{session}", str(self.directory)) for arg in self.config.argv]
                self.process = subprocess.Popen(
                    argv, cwd=self.config.cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    bufsize=0, start_new_session=True, close_fds=True, umask=0o077,
                    env={"LANG": "C.UTF-8", "HOME": str(Path.home()), "PATH": os.defpath})
                os.set_blocking(self.process.stdin.fileno(), False)
            except (OSError, ValueError, TypeError, RuntimeError):
                self._fail("native_launch_failed", "Native worker could not start")
            finally:
                self.launched.set()
            if not self.stopping.is_set():
                self._read()
        finally:
            self._shutdown()
            self.closed.set()

    def _changed(self):
        self.data["sequence"] += 1

    def snapshot(self, action=None):
        with self.lock:
            value = dict(self.data)
            action = self.last_action if action is None else action
            value["last_answer"] = self.actions[action]["receipt"] if action is not None else None
            return copy.deepcopy(value)

    def _receipt(self, action, status, reason=None):
        self.actions[action]["receipt"].update(status=status, reason=reason)
        self._changed()

    def _invalidate(self, reason):
        self.data.update(question=None, info={})
        self.deferred = None
        for action, record in self.actions.items():
            if record["receipt"]["status"] in {"submitted", "processing"}:
                self._receipt(action, "uncertain", reason)

    def _fail(self, code, message):
        with self.lock:
            self.data.update(status="failed", result=None, error={"code": code, "message": message})
            self._invalidate(code)
            self._changed()
            self.stopping.set()

    def _bind(self, state):
        actor = self.data["actor_id"]
        _require(actor is None or actor == state["actor_id"])
        self.data["actor_id"] = state["actor_id"]

    def _frame(self, frame):
        _require(type(frame) is dict and type(frame.get("event")) is str)
        event = frame["event"]
        if event in {"checkpoint_saved", "checkpoint_failed"}:
            return
        _require(self.pending_result is None and self.data["status"] not in _TERMINAL)
        if event == "view":
            state = _state(frame["state"])
            self._bind(state)
            if self.data["question"] is not None:
                self.deferred = state
                return
            self.data.update(state=state, status="running")
        elif event == "choice":
            state = _state(frame["state"])
            self._bind(state)
            question = _question(frame["question"], state["actor_id"])
            info = _info(frame["info"], state["actor_id"])
            request = question["request_id"]
            _require(request not in self.requests and len(self.requests) < 4096)
            self.requests.add(request)
            self.data.update(state=state, question=question, info=info, status="running")
            self.deferred = None
        elif event == "input_ready":
            _text(frame["input"], 128)
            _require(all(_integer(frame[key]) for key in ("generation", "priority_epoch", "revision")))
            return
        elif event == "started":
            _require(_integer(frame["count"], 1, _MAX_ACTIONS) and frame["count"] == self.starts + 1
                     and _integer(frame["start_id"]) and frame["start_id"] == self.starts
                     and frame["role"] == "invocation_not_acceptance" and bool(self.awaiting))
            action = self.awaiting.popleft()
            self.invocations[frame["start_id"]] = action
            self.starts += 1
            self._receipt(action, "processing")
            return
        elif event == "completion":
            _require(_integer(frame["count"], 1, _MAX_ACTIONS) and frame["count"] == self.completions + 1
                     and _integer(frame["start_id"]) and frame["start_id"] in self.invocations
                     and frame["role"] == "native_return_not_cast_receipt")
            self.completions += 1
            self._receipt(self.invocations.pop(frame["start_id"]), "processed")
            return
        elif event == "rejected":
            _require(bool(self.awaiting))
            reason = frame.get("reason")
            if reason not in {"input_replaced_before_dispatch", "stale_response", "invalid_response"}:
                reason = "native_rejected"
            self._receipt(self.awaiting.popleft(), "rejected", reason)
            return
        elif event == "game_complete":
            _require(not self.awaiting and not self.invocations and self.starts == self.completions
                     and type(frame["outcomes"]) is list and 1 <= len(frame["outcomes"]) <= 4
                     and _integer(frame["turns"]) and type(frame["draw"]) is bool)
            self.pending_result = {"outcomes": [_text(row) for row in frame["outcomes"]],
                                   "turns": frame["turns"], "draw": frame["draw"],
                                   "win_condition": _text(frame["win_condition"], 128)}
            self.result_at = time.monotonic()
            self.data.update(question=None, info={})
            self.deferred = None
        elif event == "aborted":
            self.data["status"] = "aborted"
            self._invalidate("native_aborted")
            self.stopping.set()
        elif event == "error":
            self._fail("native_worker_error", "Native worker reported failure")
            return
        else:
            raise _ProtocolError("Unknown native worker event")
        self._changed()

    def _read(self):
        process = self.process
        started = time.monotonic()
        exited_at = None
        total = frames = 0
        pending = bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                for index, pipe in enumerate((process.stdout, process.stderr)):
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, selectors.EVENT_READ, index)
                while not self.stopping.is_set():
                    now = time.monotonic()
                    if now - started >= _WALL_TIMEOUT:
                        self._fail("native_wall_timeout", "Native session reached its wall limit")
                        break
                    if now - self.activity_at >= _IDLE_TIMEOUT:
                        self._fail("native_idle_timeout", "Native worker exceeded its idle limit")
                        break
                    if self.result_at is not None and now - self.result_at >= _EXIT_GRACE:
                        self._fail("native_exit_timeout", "Native worker did not exit after its result")
                        break
                    code = process.poll()
                    if code is not None:
                        exited_at = exited_at or now
                        if not selector.get_map():
                            break
                        if now - exited_at >= _EXIT_GRACE:
                            self._fail("native_transport_open", "Native worker left its transport open")
                            break
                    for key, _mask in selector.select(_POLL):
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        if total + len(chunk) > _TRANSCRIPT_LIMIT:
                            self._fail("native_output_limit", "Native worker exceeded its output limit")
                            break
                        total += len(chunk)
                        self.files[key.data].write(chunk)
                        if key.data != 0:
                            continue
                        self.activity_at = time.monotonic()
                        pending.extend(chunk)
                        while b"\n" in pending:
                            raw, _, rest = pending.partition(b"\n")
                            pending = bytearray(rest)
                            _require(len(raw) <= _FRAME_LIMIT and frames < _FRAME_COUNT_LIMIT)
                            frames += 1
                            frame = _decode(raw.decode("utf-8"))
                            with self.lock:
                                if self.stopping.is_set():
                                    break
                                self._frame(frame)
                        _require(len(pending) <= _FRAME_LIMIT)
            with self.lock:
                if not self.stopping.is_set():
                    if pending or process.poll() != 0 or self.pending_result is None:
                        self._fail("native_exit_failed", "Native worker ended without a verified result")
                    else:
                        self.data.update(status="completed", result=self.pending_result, question=None, info={})
                        self._changed()
        except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
            self._fail("native_protocol_error", "Invalid native worker output")

    def _shutdown(self):
        process = self.process
        if process is not None:
            if process.stdin is not None:
                process.stdin.close()
            # The group is owned by start_new_session; clean descendants even if
            # the direct child already exited or a wrapper retained a pipe.
            for sig, grace in ((signal.SIGTERM, _TERM_GRACE), (signal.SIGKILL, _KILL_GRACE)):
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=grace)
                except subprocess.TimeoutExpired:
                    continue
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
        for handle in self.files:
            handle.close()

    def answer(self, payload):
        with self.lock:
            if type(payload) is not dict or set(payload) != {"request_id", "tokens", "sequence", "action_id"}:
                raise ForgeError(422, "invalid_answer", "Invalid native answer fields")
            action = _key(payload["action_id"])
            try:
                fingerprint = _fingerprint(payload)
            except (TypeError, ValueError, RecursionError, OverflowError):
                raise ForgeError(422, "invalid_answer", "Invalid native answer") from None
            if action in self.actions:
                if not hmac.compare_digest(self.actions[action]["fingerprint"], fingerprint):
                    raise ForgeError(409, "action_conflict", "Action key already identifies another answer")
                return self.snapshot(action)
            if self.data["status"] in _TERMINAL or self.stopping.is_set():
                raise ForgeError(409, "session_closed", "Native session is closed")
            question = self.data["question"]
            if (not _integer(payload["sequence"]) or payload["sequence"] != self.data["sequence"]
                    or question is None or payload["request_id"] != question["request_id"]):
                raise ForgeError(409, "stale_question", "Read the current native question before answering")
            tokens = payload["tokens"]
            if (type(tokens) is not list or not question["min"] <= len(tokens) <= question["max"]
                    or not all(type(token) is str for token in tokens)
                    or len(set(tokens)) != len(tokens)
                    or not set(tokens) <= {row["token"] for row in question["choices"]}):
                raise ForgeError(422, "invalid_tokens", "Select only the offered native tokens and bounds")
            if len(self.actions) >= _MAX_ACTIONS:
                raise ForgeError(409, "action_limit", "Native session action limit reached")
            raw = _encode({"request_id": payload["request_id"], "tokens": tokens}) + b"\n"
            if len(raw) > 16384:
                raise ForgeError(422, "invalid_answer", "Native answer exceeds the wire limit")
            self.actions[action] = {"fingerprint": fingerprint, "receipt": {
                "action_id": action, "request_id": payload["request_id"], "status": "submitted", "reason": None}}
            self.awaiting.append(action)
            self.last_action = action
            self.data.update(question=None, info={})
            if self.deferred is not None:
                self.data["state"] = self.deferred
                self.deferred = None
            self._changed()
            self.activity_at = time.monotonic()
            try:
                fd = self.process.stdin.fileno()
                remaining = memoryview(raw)
                deadline = time.monotonic() + _WRITE_TIMEOUT
                with selectors.DefaultSelector() as writer:
                    writer.register(fd, selectors.EVENT_WRITE)
                    while remaining:
                        timeout = deadline - time.monotonic()
                        if timeout <= 0 or not writer.select(timeout):
                            raise OSError("Native pipe write timed out")
                        try:
                            written = os.write(fd, remaining)
                        except BlockingIOError:
                            continue
                        if written <= 0:
                            raise OSError("Native pipe closed")
                        remaining = remaining[written:]
            except (OSError, ValueError):
                self._fail("native_write_uncertain", "Native answer delivery is uncertain; do not resend")
            return self.snapshot()

    def close(self):
        with self.lock:
            if self.data["status"] not in _TERMINAL:
                self.data["status"] = "aborted"
                self._invalidate("session_closed")
                self._changed()
            self.stopping.set()
            if self.process is not None and self.process.stdin is not None:
                self.process.stdin.close()
        if self.reader is not None and self.reader.ident is not None:
            self.reader.join(timeout=_POLL + _TERM_GRACE + _KILL_GRACE + 1)
            if self.reader.is_alive():
                raise ForgeError(503, "native_close_timeout", "Native session shutdown is still pending")
        if self.process is not None and self.process.poll() is None:
            raise ForgeError(503, "native_close_timeout", "Native session shutdown is still pending")
        return self.snapshot()


class ForgeManager:
    def __init__(self, config_or_none):
        if config_or_none is not None and not isinstance(config_or_none, RuntimeConfig):
            raise ForgeError(503, "invalid_runtime_config", "Native runtime configuration unavailable")
        self.config = config_or_none
        self._lock = threading.RLock()
        self._sessions, self._starts = {}, {}
        self._closed = False

    @classmethod
    def from_environment(cls):
        path = os.environ.get("MTG_FORGE_RUNTIME_CONFIG")
        return cls(RuntimeConfig.from_file(path) if path else None)

    @property
    def available(self):
        return self.config is not None and not self._closed

    def create(self, payload, capability, key):
        capability = _capability_hash(capability)
        key = _key(key)
        with self._lock:
            if not self.available:
                raise ForgeError(503, "native_unavailable", "Native Forge runtime is disabled")
            spec = _start_payload(payload)
            fingerprint = _fingerprint(payload)
            identity = (capability, key)
            if identity in self._starts:
                old_fingerprint, session_id = self._starts[identity]
                if not hmac.compare_digest(old_fingerprint, fingerprint):
                    raise ForgeError(409, "start_conflict", "Start key already identifies another request")
                return self._sessions[session_id].snapshot()
            if sum(not row.closed.is_set() or (row.process is not None and row.process.poll() is None)
                   for row in self._sessions.values()) >= 2:
                raise ForgeError(503, "native_capacity", "Native session capacity reached")
            while len(self._sessions) >= _MAX_RECORDS:
                expired = next((sid for sid, row in self._sessions.items()
                                if row.closed.is_set() and row.data["status"] in _TERMINAL
                                and (row.process is None or row.process.poll() is not None)), None)
                if expired is None:
                    raise ForgeError(503, "native_capacity", "Native session capacity reached")
                del self._sessions[expired]
                self._starts = {identity: record for identity, record in self._starts.items() if record[1] != expired}
            session_id = uuid.uuid4().hex
            session = _Session(self.config, session_id, capability, spec)
            self._sessions[session_id] = session
            self._starts[identity] = (fingerprint, session_id)
            return session.snapshot()

    def _session(self, session_id, capability):
        capability = _capability_hash(capability)
        with self._lock:
            session = self._sessions.get(session_id) if type(session_id) is str else None
            if session is None or not hmac.compare_digest(session.capability, capability):
                raise ForgeError(404, "session_not_found", "Native session not found")
            return session

    def get(self, session_id, capability):
        return self._session(session_id, capability).snapshot()

    def answer(self, session_id, capability, payload):
        return self._session(session_id, capability).answer(payload)

    def close(self, session_id, capability):
        return self._session(session_id, capability).close()

    def close_all(self):
        with self._lock:
            self._closed = True
            sessions = list(self._sessions.values())
        failure = None
        for session in sessions:
            try:
                session.close()
            except ForgeError as error:
                failure = failure or error
        if failure is not None:
            raise failure
