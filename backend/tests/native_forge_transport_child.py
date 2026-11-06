"""SYNTHETIC stdin/stdout child. These scenarios are NOT native games."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def opaque(number):
    return "00000000-0000-0000-0000-" + format(number, "012x")


def state(turn=1, actor=17):
    def zones():
        return {name: {"count": 0, "visible_cards": []} for name in (
            "Hand", "Library", "Graveyard", "Battlefield", "Exile", "Command", "Sideboard")}
    return {"actor_id": actor, "turn": turn, "phase": "SYNTHETIC",
            "players": [{"player_id": 17, "name": "SYNTHETIC A", "life": 20, "zones": zones()},
                        {"player_id": 23, "name": "SYNTHETIC B", "life": 20, "zones": zones()}],
            "stack": []}


def choice(number=1, turn=1):
    return {"event": "choice", "state": state(turn), "info": {"prompt": "SYNTHETIC TRANSPORT"},
            "question": {"actor_id": 17, "request_id": opaque(number), "kind": "confirm",
                         "min": 1, "max": 1, "choices": [
                             {"token": opaque(10 + number), "display": True},
                             {"token": opaque(20 + number), "display": False}]},
            "replay_offer": {"PRIVATE_SYNTHETIC": True}, "native_state": {"PRIVATE_SYNTHETIC": True}}


def emit(value):
    sys.stdout.buffer.write(json.dumps(value, separators=(",", ":")).encode() + b"\n")
    sys.stdout.buffer.flush()


def started(number):
    emit({"event": "started", "count": number + 1, "start_id": number,
          "role": "invocation_not_acceptance"})


def completion(number, count):
    emit({"event": "completion", "count": count, "start_id": number,
          "role": "native_return_not_cast_receipt"})


def result():
    emit({"event": "game_complete", "outcomes": ["SYNTHETIC TRANSPORT ONLY"],
          "turns": 3, "draw": False, "win_condition": "SYNTHETIC",
          "coverage": {"PRIVATE_SYNTHETIC": True}})


def main():
    mode, root = sys.argv[1], Path(sys.argv[2])
    if mode == "group-descendant":
        time.sleep(60)
        return
    if mode == "parent-death":
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        libc.prctl.restype = ctypes.c_int
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "SYNTHETIC parent-death setup failed")
        mode = "finish"
    (root / "TRANSPORT.pid").write_text(str(os.getpid()))
    if mode == "silent":
        time.sleep(60)
        return
    if mode == "group":
        child = subprocess.Popen([sys.executable, "-u", __file__, "group-descendant", str(root)])
        (root / "DESCENDANT.pid").write_text(str(child.pid))

        def terminate(_signum, _frame):
            child.wait(timeout=2)
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, terminate)
    if mode == "bad-json":
        sys.stdout.buffer.write(b"SYNTHETIC PRIVATE BAD JSON\n")
        sys.stdout.buffer.flush()
        time.sleep(60)
        return
    if mode == "bad-utf8":
        sys.stdout.buffer.write(b"\xff\n")
        sys.stdout.buffer.flush()
        return
    if mode == "duplicate-json":
        sys.stdout.buffer.write(b'{"event":"view","event":"choice"}\n')
        sys.stdout.buffer.flush()
        return
    if mode == "unknown":
        emit({"event": "SYNTHETIC_UNKNOWN", "private": "DO NOT PUBLISH"})
        return
    if mode == "oversize":
        sys.stdout.buffer.write(b"x" * (2 * 1024 * 1024 + 1))
        sys.stdout.buffer.flush()
        time.sleep(60)
        return
    if mode == "stderr-flood":
        sys.stderr.buffer.write(b"SYNTHETIC PRIVATE\n" * 20000)
        sys.stderr.buffer.flush()
        time.sleep(60)
        return
    if mode == "partial-eof":
        sys.stdout.buffer.write(b'{"event":"view"')
        sys.stdout.buffer.flush()
        return
    first = choice()
    if mode == "foreign-question":
        first["question"]["actor_id"] = 23
    if mode == "duplicate-token":
        first["question"]["choices"][1]["token"] = first["question"]["choices"][0]["token"]
    if mode == "selection":
        first["question"].update(kind="order", min=2, max=2)
    if mode == "projection":
        first["info"]["provenance"] = "PRIVATE SYNTHETIC"
        first["state"]["journals"] = "PRIVATE SYNTHETIC"
        first["question"]["native_state"] = "PRIVATE SYNTHETIC"
    if mode == "reveal":
        card = {"card_id": 101, "controller_id": 23, "owner_id": 23, "tapped": False,
                "face_down": False, "face": {"name": "SYNTHETIC AUTHORIZED REVEAL", "type": "SYNTHETIC",
                    "mana_cost": "", "oracle_text": "SYNTHETIC\nPUBLIC", "power": 0, "toughness": 0,
                    "private": "DO NOT PUBLISH"}, "private": "DO NOT PUBLISH"}
        first["state"]["players"][1]["zones"]["Library"] = {"count": 60, "visible_cards": [card]}
    if mode == "surrogate":
        first["info"]["prompt"] = "\ud800"
    if mode == "partial":
        raw = json.dumps(first).encode() + b"\n"
        sys.stdout.buffer.write(raw[:20])
        sys.stdout.buffer.flush()
        time.sleep(.04)
        sys.stdout.buffer.write(raw[20:])
        sys.stdout.buffer.flush()
    else:
        emit({"event": "view", "state": state()})
        emit(first)
    if mode == "defer":
        emit({"event": "view", "state": state(2)})
        (root / "VIEW_SENT").touch()
    if mode == "private-checkpoint":
        emit({"event": "checkpoint_saved", "request_id": "PRIVATE", "sha256": "PRIVATE"})
        emit({"event": "checkpoint_failed", "reason": "PRIVATE"})
    if mode == "foreign-view":
        emit({"event": "view", "state": state(actor=23)})
    if mode == "frame-flood":
        for _ in range(20):
            emit({"event": "view", "state": state()})
    if mode == "eof":
        return
    if mode == "aborted":
        emit({"event": "aborted", "reason": "input_closed"})
        raise SystemExit(2)
    if mode == "error":
        emit({"event": "error", "reason": "/PRIVATE/SYNTHETIC/runtime"})
        raise SystemExit(1)
    for number, line in enumerate(sys.stdin.buffer):
        with (root / "RECEIVED.private.jsonl").open("ab") as log:
            log.write(line)
        value = json.loads(line)
        if set(value) != {"request_id", "tokens"}:
            raise SystemExit(9)
        if mode in {"hold", "group"}:
            continue
        if mode == "reject":
            emit(choice(2, 2))
            emit({"event": "rejected", "reason": "input_replaced_before_dispatch"})
            continue
        if mode == "bad-start":
            emit({"event": "started", "count": 1, "start_id": 99,
                  "role": "invocation_not_acceptance"})
            continue
        started(number)
        if mode == "bad-completion":
            completion(99, 1)
            continue
        if mode in {"stderr-after-start", "stderr-after-result"}:
            if mode == "stderr-after-start":
                emit(choice(number + 2, number + 2))
            else:
                completion(number, number + 1)
                result()
            (root / "STDERR_READY").touch(mode=0o600)
            while not (root / "RELEASE_STDERR").exists():
                time.sleep(.01)
            sys.stderr.buffer.write(b"SYNTHETIC STDERR PREFIX\n")
            sys.stderr.buffer.flush()
            while not (root / "RELEASE_STDERR_FLOOD").exists():
                time.sleep(.01)
            sys.stderr.buffer.write(b"SYNTHETIC PRIVATE\n" * 20000)
            sys.stderr.buffer.flush()
            time.sleep(60)
            return
        if mode == "nested":
            if number == 0:
                emit(choice(2, 2))
            elif number == 1:
                completion(1, 1)
                emit(choice(3, 3))
                while not (root / "RELEASE_PARENT").exists():
                    time.sleep(.01)
                completion(0, 2)
            continue
        completion(number, number + 1)
        if mode in {"finish", "result-nonzero", "result-hang"}:
            result()
            if mode == "result-hang":
                time.sleep(60)
            raise SystemExit(7 if mode == "result-nonzero" else 0)
        emit(choice(number + 2, number + 2))
    if mode == "group":
        time.sleep(60)


if __name__ == "__main__":
    main()
