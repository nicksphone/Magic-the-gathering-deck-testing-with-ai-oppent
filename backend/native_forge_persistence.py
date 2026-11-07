"""Private native-session metadata; game checkpoints retain their GPL notices."""
from contextlib import contextmanager
import fcntl
import hmac
import json
import os
from pathlib import Path
import re
import stat
import uuid

import native_checkpoint_store as checkpoints

_SID = re.compile(r"[0-9a-f]{32}")
_HEX = re.compile(r"[0-9a-f]{64}")
_LIMIT = 2 * 1024 * 1024
_PUBLIC = {"engine", "session_id", "sequence", "status", "actor_id", "state",
           "question", "info", "last_answer", "result", "error"}


class SaveError(ValueError):
    def __init__(self, code="invalid_save", *, committed=False):
        super().__init__("Native save is invalid, incompatible or unavailable")
        self.code, self.committed = code, committed


def _need(value):
    if not value:
        raise SaveError()


def _pairs(rows):
    result = {}
    for key, value in rows:
        _need(key not in result)
        result[key] = value
    return result


def _invalid_number(_value):
    raise SaveError()


def _encode(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    _need(len(raw) <= _LIMIT)
    return raw


def _key(value):
    return (type(value) is str and 0 < len(value) <= 100
            and not any(ord(c) < 32 or ord(c) == 127 or 0xd800 <= ord(c) <= 0xdfff for c in value))


def _record(value, sid):
    _need(type(value) is dict and set(value) == {"public", "actions", "controls", "start", "invocations", "last_action"})
    public = value["public"]
    _need(type(public) is dict and set(public) == _PUBLIC and public["engine"] == "forge"
          and public["session_id"] == sid and type(public["sequence"]) is int
          and 0 <= public["sequence"] < 2**63 and public["status"] in {"suspended", "completed", "aborted"}
          and public["question"] is None and public["info"] == {})
    actions, controls, invocations = (value[k] for k in ("actions", "controls", "invocations"))
    _need(type(actions) is dict and len(actions) <= 1000)
    for key, action in actions.items():
        _need(_key(key) and type(action) is dict and set(action) == {"fingerprint", "receipt"}
              and type(action["fingerprint"]) is str and _HEX.fullmatch(action["fingerprint"]))
        receipt = action["receipt"]
        _need(type(receipt) is dict and set(receipt) == {"action_id", "request_id", "status", "reason"}
              and receipt["action_id"] == key and type(receipt["request_id"]) is str
              and len(receipt["request_id"]) == 36
              and receipt["status"] in {"submitted", "processing", "processed", "rejected", "uncertain"}
              and (receipt["reason"] is None or _key(receipt["reason"])))
    _need(type(controls) is dict and len(controls) <= 128)
    for key, control in controls.items():
        _need(_key(key) and type(control) is dict and set(control) == {"operation", "fingerprint"}
              and control["operation"] in {"checkpoint", "resume"}
              and type(control["fingerprint"]) is str and _HEX.fullmatch(control["fingerprint"]))
    _need(type(invocations) is dict and len(invocations) <= 1000)
    for key, action in invocations.items():
        _need(type(key) is str and key.isascii() and key.isdecimal() and 0 <= int(key) < 1000
              and action in actions and actions[action]["receipt"]["status"] == "processing")
    _need(value["last_action"] is None or value["last_action"] in actions)
    start = value["start"]
    _need(type(start) is dict and set(start) == {"key", "fingerprint"} and _key(start["key"])
          and type(start["fingerprint"]) is str and _HEX.fullmatch(start["fingerprint"]))
    _encode(value)


def _owned(fd, directory=False):
    value = os.fstat(fd)
    _need((stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode))
          and value.st_uid == os.geteuid()
          and stat.S_IMODE(value.st_mode) == (0o700 if directory else 0o600)
          and (directory or value.st_nlink == 1))


class NativeSaves:
    def __init__(self, root, build_id):
        self.root, self.build_id = Path(root), build_id
        _need(self.root.is_absolute() and ".." not in self.root.parts
              and type(build_id) is str and _HEX.fullmatch(build_id))
        self.lease = None

    def acquire(self):
        if self.lease is not None:
            return
        fd = None
        try:
            with checkpoints._directory(self.root.parent) as parent:
                try:
                    os.mkdir(self.root.name, 0o700, dir_fd=parent)
                    os.fsync(parent)
                except FileExistsError:
                    pass
            with checkpoints._directory(self.root) as directory:
                _owned(directory, True)
                fd = os.open(".forge-runtime.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
                _owned(fd)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.lease, fd = fd, None
        except BlockingIOError:
            raise SaveError("runtime_owned") from None
        except (OSError, checkpoints.CheckpointError):
            raise SaveError() from None
        finally:
            if fd is not None:
                os.close(fd)

    def release(self):
        if self.lease is not None:
            os.close(self.lease)
            self.lease = None

    @contextmanager
    def _directory(self, sid, *, create=False):
        _need(type(sid) is str and _SID.fullmatch(sid))
        with checkpoints._directory(self.root) as parent:
            _owned(parent, True)
            name = ".saved-" + sid
            if create:
                try:
                    os.mkdir(name, 0o700, dir_fd=parent)
                    os.fsync(parent)
                except FileExistsError:
                    pass
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                _owned(fd, True)
                yield fd, self.root / name
            finally:
                os.close(fd)

    def _read(self, directory, cap):
        fd = os.open("SESSION.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as handle:
            _owned(handle.fileno())
            _need(os.fstat(handle.fileno()).st_size <= _LIMIT)
            raw = handle.read(_LIMIT + 1)
        _need(len(raw) <= _LIMIT)
        meta = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_invalid_number)
        if (type(meta) is not dict or type(cap) is not bytes or len(cap) != 32
                or type(meta.get("capability_hash")) is not str
                or not hmac.compare_digest(meta["capability_hash"], cap.hex())):
            raise SaveError("not_found")
        _need(set(meta) == {"schema", "build_id", "capability_hash", "checkpoint", "previous", "record"}
              and type(meta["schema"]) is int and meta["schema"] == 1
              and type(meta["checkpoint"]) is str and _SID.fullmatch(meta["checkpoint"])
              and (meta["previous"] is None or type(meta["previous"]) is str and _SID.fullmatch(meta["previous"])))
        if meta["build_id"] != self.build_id:
            raise SaveError("build_mismatch")
        return meta

    def _write(self, directory, meta, destination="SESSION.json"):
        _need(destination in {"SESSION.json", "EPOCH.json"})
        name = ".metadata-" + uuid.uuid4().hex
        committed = False
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            with os.fdopen(fd, "wb") as handle:
                handle.write(_encode(meta))
                handle.flush()
                os.fsync(handle.fileno())
            try:
                old = os.stat(destination, dir_fd=directory, follow_symlinks=False)
                _need(stat.S_ISREG(old.st_mode) and old.st_nlink == 1 and old.st_uid == os.geteuid())
            except FileNotFoundError:
                pass
            os.replace(name, destination, src_dir_fd=directory, dst_dir_fd=directory)
            committed = True
            os.fsync(directory)
        except OSError:
            raise SaveError("save_io", committed=committed) from None
        finally:
            if not committed:
                try:
                    os.unlink(name, dir_fd=directory)
                except FileNotFoundError:
                    pass

    def _remove_generation(self, directory, name):
        try:
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        except FileNotFoundError:
            return
        try:
            _owned(fd, True)
            names = {"CHECKPOINT.json", "manifest.json"}
            _need(set(os.listdir(fd)) == names)
            for item in names:
                child = os.open(item, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    _owned(child)
                finally:
                    os.close(child)
            for item in names:
                os.unlink(item, dir_fd=fd)
        finally:
            os.close(fd)
        os.rmdir(name, dir_fd=directory)
        os.fsync(directory)

    def _prune(self, directory, keep):
        for name in os.listdir(directory):
            if _SID.fullmatch(name) and name not in keep:
                self._remove_generation(directory, name)

    def _discard_unreferenced(self, sid, cap, generation):
        with self._directory(sid) as (directory, _):
            try:
                meta = self._read(directory, cap)
            except FileNotFoundError:
                meta = None
            if meta is None or generation not in {meta["checkpoint"], meta["previous"]}:
                self._remove_generation(directory, generation)

    def publish(self, sid, cap, snapshot, record):
        generation, committed = None, False
        try:
            _record(record, sid)
            _need(type(cap) is bytes and len(cap) == 32)
            self.acquire()
            with self._directory(sid, create=True) as (directory, path):
                try:
                    previous = self._read(directory, cap)
                except FileNotFoundError:
                    previous = None
                if previous is not None:
                    self._prune(directory, {previous["checkpoint"], previous["previous"]})
                generation = uuid.uuid4().hex
                checkpoints.save_checkpoint(snapshot, path / generation, build_id=self.build_id)
                current = checkpoints.load_checkpoint(path / generation, build_id=self.build_id)
                meta = {"schema": 1, "build_id": self.build_id, "capability_hash": cap.hex(),
                        "checkpoint": generation, "previous": previous["checkpoint"] if previous else None,
                        "record": record}
                self._write(directory, meta)
                committed = True
                self._prune(directory, {generation, meta["previous"]})
                return meta, current
        except (OSError, ValueError, TypeError, RecursionError) as error:
            committed = committed or getattr(error, "committed", False)
            if generation and not committed:
                try:
                    self._discard_unreferenced(sid, cap, generation)
                except (OSError, ValueError):
                    raise SaveError("save_cleanup") from None
            if isinstance(error, SaveError):
                error.committed = committed
                raise
            raise SaveError(committed=committed) from None

    def load(self, sid, cap):
        try:
            with self._directory(sid) as (directory, path):
                meta = self._read(directory, cap)
                _record(meta["record"], sid)
                current = checkpoints.load_checkpoint(path / meta["checkpoint"], build_id=self.build_id)
                return meta, current
        except FileNotFoundError:
            raise SaveError("not_found") from None
        except (OSError, ValueError, TypeError, RecursionError) as error:
            if isinstance(error, SaveError):
                raise
            raise SaveError() from None

    def update(self, sid, cap, record):
        try:
            _record(record, sid)
            self.acquire()
            meta, _ = self.load(sid, cap)
            with self._directory(sid) as (directory, _):
                meta["record"] = record
                self._write(directory, meta)
                return meta
        except (OSError, ValueError, TypeError, RecursionError) as error:
            if isinstance(error, SaveError):
                raise
            raise SaveError() from None

    def has_saves(self):
        try:
            with checkpoints._directory(self.root) as directory:
                _owned(directory, True)
                return any(name.startswith(".saved-") and _SID.fullmatch(name[7:])
                           for name in os.listdir(directory))
        except FileNotFoundError:
            return False
        except (OSError, checkpoints.CheckpointError):
            raise SaveError() from None

    def find_start(self, cap, key):
        """Locate this capability's durable idempotency key without loading game bodies."""
        try:
            with checkpoints._directory(self.root) as directory:
                _owned(directory, True)
                names = os.listdir(directory)
            for name in names:
                if not name.startswith(".saved-") or not _SID.fullmatch(name[7:]):
                    continue
                sid = name[7:]
                try:
                    with self._directory(sid) as (directory, _):
                        meta = self._read(directory, cap)
                except SaveError as error:
                    if error.code == "not_found":
                        continue
                    raise
                _record(meta["record"], sid)
                if meta["record"]["start"]["key"] == key:
                    return sid
            return None
        except (OSError, ValueError, TypeError, RecursionError) as error:
            if isinstance(error, SaveError):
                raise
            raise SaveError() from None

    def reserve_epoch(self):
        """Reserve a durable sequence range before a replacement owner publishes."""
        try:
            self.acquire()
            with checkpoints._directory(self.root) as directory:
                _owned(directory, True)
                try:
                    fd = os.open("EPOCH.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
                except FileNotFoundError:
                    previous = 0
                else:
                    with os.fdopen(fd, "rb") as handle:
                        _owned(handle.fileno())
                        _need(os.fstat(handle.fileno()).st_size <= 128)
                        value = json.loads(handle.read(129), object_pairs_hook=_pairs, parse_constant=_invalid_number)
                    _need(type(value) is dict and set(value) == {"epoch"} and type(value["epoch"]) is int)
                    previous = value["epoch"]
                _need(0 <= previous < (2**53 // 1_000_000) - 1)
                current = previous + 1
                self._write(directory, {"epoch": current}, "EPOCH.json")
                return current * 1_000_000
        except (OSError, ValueError, TypeError, RecursionError) as error:
            if isinstance(error, SaveError):
                raise
            raise SaveError() from None
