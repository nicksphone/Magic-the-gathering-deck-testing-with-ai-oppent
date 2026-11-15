"""SYNTHETIC checkpoint transport; no card rules, native games or AI strength."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid
import signal
import subprocess
import atexit

from native_forge_transport_child import state, emit, started, completion, result


def main():
    mode, root = sys.argv[1], Path(sys.argv[2])
    if mode == "detached-exit-child":
        def finish(_signum, _frame):
            time.sleep(.6)
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, finish)
        (root / "DETACHED.ready").touch()
        time.sleep(60)
        return
    if mode == "detached-exit":
        child = subprocess.Popen([sys.executable, "-u", __file__, "detached-exit-child", str(root)],
                                 start_new_session=True, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (root / "DETACHED.pid").write_text(str(child.pid))
        atexit.register(child.terminate)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        while not (root / "DETACHED.ready").exists():
            time.sleep(.005)
    spec = json.loads((root / "SPEC.json").read_text())
    decks = {row["file"]: (root / "decks" / row["file"]).read_text() for row in spec["decks"]}
    (root / "TRANSPORT.pid").write_text(str(os.getpid()))
    journals = {key: [] for key in ("starts", "completions", "native", "paid-pending", "final")}
    count = 0

    def choice():
        choices = [{"token": str(uuid.uuid4()), "display": value} for value in (True, False)]
        if mode == "ambiguous" and "-resume-" in root.name:
            choices[1]["display"] = True
        offer = {"kind": "confirm", "actor": 17, "min": 1, "max": 1,
                 "choices": [True, False], "turn": count + 1, "phase": "SYNTHETIC",
                 "info": {"prompt": "SYNTHETIC SAVE TRANSPORT"}}
        if mode == "mismatch" and "-resume-" in root.name:
            offer["phase"] = "SYNTHETIC WRONG FRONTIER"
        frame = {"event": "choice", "state": state(count + 1), "info": offer["info"],
                 "question": {"actor_id": 17, "request_id": str(uuid.uuid4()), "kind": "confirm",
                              "min": 1, "max": 1, "choices": choices}, "replay_offer": offer}
        emit(frame)
        return frame

    current = choice()
    for line in sys.stdin:
        request = json.loads(line)
        if "checkpoint_request_id" in request:
            if mode == "busy":
                emit({"event": "rejected", "reason": "checkpoint_busy"})
                continue
            rid = request["checkpoint_request_id"]
            if mode == "io-fail":
                emit({"event": "checkpoint_failed", "request_id": rid,
                      "committed": False, "reason": "write_failed_before_commit"})
                continue
            body = {"schema": 1, "spec": spec, "decks": decks,
                    "starts": len(journals["starts"]), "completions": len(journals["completions"]),
                    "pending_offer": current["replay_offer"], "actor_view": current["state"],
                    "native_state": {"players": [{"id": 17}, {"id": 23}], "stack": [],
                                     "turn": count + 1, "phase": "SYNTHETIC", "rng_delta": count},
                    "journals": journals}
            raw = json.dumps(body, separators=(",", ":")).encode()
            temporary = root / ".checkpoint.tmp"
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, root / "CHECKPOINT.json")
            if mode == "slow-capture":
                (root / "CAPTURE.pending").touch()
                time.sleep(.2)
            digest = hashlib.sha256(raw).hexdigest() if mode != "bad-hash" else "0" * 64
            emit({"event": "checkpoint_saved", "request_id": rid, "sha256": digest})
            continue
        if request.get("request_id") != current["question"]["request_id"]:
            emit({"event": "rejected", "reason": "stale_response"})
            continue
        selected = [option["display"] for token in request["tokens"]
                    for option in current["question"]["choices"] if option["token"] == token]
        ticket = {"offer": current["replay_offer"], "selected": selected}
        journals["starts"].append({"start_id": count, "parent_start": -1, "kind": "dialog", "ticket": ticket})
        started(count)
        if mode != "nested" or count != 0:
            journals["completions"].append({"start_id": count, "kind": "dialog", "ticket": ticket, "result": "void"})
            completion(count, len(journals["completions"]))
            if mode == "nested" and count == 1:
                outer = journals["starts"][0]["ticket"]
                journals["completions"].append({"start_id": 0, "kind": "dialog", "ticket": outer, "result": "void"})
                completion(0, len(journals["completions"]))
        count += 1
        if count == 3:
            result()
            return
        current = choice()
        if mode == "slow":
            time.sleep(.1)


if __name__ == "__main__":
    main()
