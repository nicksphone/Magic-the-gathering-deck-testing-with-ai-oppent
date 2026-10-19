"""Local construction/individual-write limits, not total RAM or storage quotas."""
from __future__ import annotations

import json
import re
import time
from types import MappingProxyType


RESOURCE_LIMITS = MappingProxyType(dict(
    request_json_bytes=2097152, result_json_bytes=1048576,
    snapshot_json_bytes=1048576, error_utf8_bytes=1024,
    trace_entry_utf8_bytes=65536, trace_scalar_utf8_bytes=8192,
    trace_value_nodes=8192, trace_depth=32,
    game_log_utf8_bytes=4194304, game_log_entries=32768,
    batch_log_utf8_bytes=33554432, batch_log_entries=131072,
    action_log_growth_reserve=65536, deadline_seconds=600,
))
_ESCAPED = re.compile(r'["\\]|[^\x20-\x7e]')


class SimulationResourceLimit(RuntimeError):
    def __init__(self, dimension: str):
        self.dimension = dimension
        super().__init__("resource_limit:" + dimension)


def checked_text(value, limit: int, dimension: str):
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Resource text must be a string")
    if len(value) > limit:
        raise SimulationResourceLimit(dimension)
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError:
        raise SimulationResourceLimit(dimension) from None
    if size > limit:
        raise SimulationResourceLimit(dimension)
    return value


def _quoted_size(value: str, remaining: int, dimension: str) -> int:
    # Count default ensure_ascii escapes before allocating an escaped string.
    size = len(value) + 2
    if size > remaining:
        raise SimulationResourceLimit(dimension)
    for match in _ESCAPED.finditer(value):
        char = match[0]
        cost = 2 if char in '"\\\b\f\n\r\t' else 12 if ord(char) > 65535 else 6
        size += cost - 1
        if size > remaining:
            raise SimulationResourceLimit(dimension)
    return size


class _JSONWalk:
    def __init__(self, limit, dimension, depth, nodes, scalar=None, separators=(", ", ": ")):
        self.remaining, self.dimension = limit, dimension
        self.depth, self.nodes, self.scalar = depth, nodes, scalar
        self.separators = separators
        self.ancestors = set()

    def charge(self, size):
        self.remaining -= size
        if self.remaining < 0:
            raise SimulationResourceLimit(self.dimension)

    def string(self, value):
        if self.scalar is not None:
            checked_text(value, self.scalar, "trace_scalar")
        self.charge(_quoted_size(value, self.remaining, self.dimension))

    def visit(self, value, level=0):
        self.nodes -= 1
        if self.nodes < 0:
            raise SimulationResourceLimit("trace_nodes" if self.scalar is not None else self.dimension)
        if level > self.depth:
            raise SimulationResourceLimit("trace_depth" if self.scalar is not None else self.dimension)
        if isinstance(value, str):
            self.string(value)
            return
        if value is None or isinstance(value, (bool, int, float)):
            if isinstance(value, int) and value.bit_length() > 4 * self.remaining + 4:
                raise SimulationResourceLimit(self.dimension)
            try:
                self.charge(len(json.dumps(value)))
            except ValueError:
                raise SimulationResourceLimit(self.dimension) from None
            return
        if not isinstance(value, (dict, list, tuple)):
            raise TypeError("Object of type " + type(value).__name__ + " is not JSON serializable")
        identity = id(value)
        if identity in self.ancestors:
            raise SimulationResourceLimit(self.dimension)
        self.ancestors.add(identity)
        try:
            self.charge(2)
            for index, item in enumerate(value.items() if isinstance(value, dict) else value):
                if index:
                    self.charge(len(self.separators[0]))
                if isinstance(value, dict):
                    key, child = item
                    if not isinstance(key, (str, int, float, bool)) and key is not None:
                        raise TypeError("JSON keys must be strings or scalar values")
                    self.visit(key if isinstance(key, str) else json.dumps(key), level + 1)
                    self.charge(len(self.separators[1]))
                else:
                    child = item
                self.visit(child, level + 1)
        finally:
            self.ancestors.remove(identity)


def checked_json(value, limit, dimension, *, separators=None, depth=32, nodes=None, scalar=None, encoder=None):
    separators = separators or (", ", ": ")
    walk = _JSONWalk(limit, dimension, depth, limit if nodes is None else nodes, scalar, separators)
    walk.visit(value)
    if encoder is not None:
        # Preserve the writer's existing encoder after exact bounded preflight.
        encoded = encoder()
        if len(encoded.encode("utf-8")) > limit:
            raise SimulationResourceLimit(dimension)
        return encoded
    parts, used = [], 0
    for chunk in json.JSONEncoder(separators=separators).iterencode(value):
        used += len(chunk)  # Default ensure_ascii makes each output character one byte.
        if used > limit:
            raise SimulationResourceLimit(dimension)
        parts.append(chunk)
    return "".join(parts)


class ResourceBudget:
    def __init__(self, limits=RESOURCE_LIMITS, *, clock=None):
        self.limits = dict(limits)
        if any(type(value) is not int or value < 0 for value in self.limits.values()):
            raise ValueError("Resource limits must be nonnegative integers")
        self.clock = clock or time.monotonic
        self.deadline = self.clock() + self.limits["deadline_seconds"]
        self.batch_bytes = self.batch_entries = self.game_bytes = self.game_entries = 0

    def check_deadline(self):
        if self.clock() >= self.deadline:
            raise SimulationResourceLimit("deadline")

    def _log_cost(self, log):
        if len(log) > self.limits["game_log_entries"]:
            raise SimulationResourceLimit("game_log_entries")
        size = 0
        for line in log:
            checked_text(line, self.limits["game_log_utf8_bytes"], "game_log")
            size += len(line.encode("utf-8"))
            if size > self.limits["game_log_utf8_bytes"]:
                raise SimulationResourceLimit("game_log")
        return size

    def _check_batch(self, size, entries):
        if self.batch_bytes + size > self.limits["batch_log_utf8_bytes"]:
            raise SimulationResourceLimit("batch_log")
        if self.batch_entries + entries > self.limits["batch_log_entries"]:
            raise SimulationResourceLimit("batch_log_entries")

    def begin_game(self, log):
        self.check_deadline()
        size = self._log_cost(log)
        self._check_batch(size, len(log))
        self.game_bytes, self.game_entries = size, len(log)
        self.batch_bytes += size
        self.batch_entries += len(log)

    def before_clone(self, trace_bytes=0):
        self.check_deadline()
        reserve = self.limits["action_log_growth_reserve"] + trace_bytes
        if self.game_bytes + reserve > self.limits["game_log_utf8_bytes"]:
            raise SimulationResourceLimit("game_log")
        if self.game_entries + 1 > self.limits["game_log_entries"]:
            raise SimulationResourceLimit("game_log_entries")
        self._check_batch(reserve, 1)

    def trace_inputs(self, state, pid, action, reasoning):
        self.before_clone()
        if len(state.cards) > self.limits["trace_value_nodes"]:
            raise SimulationResourceLimit("trace_nodes")
        walk = _JSONWalk(self.limits["trace_entry_utf8_bytes"], "trace_entry",
                         self.limits["trace_depth"], self.limits["trace_value_nodes"],
                         self.limits["trace_scalar_utf8_bytes"], (",", ":"))
        for player_id in (pid, 3 - pid):
            player = state.players[player_id]
            for cid in player.hand:
                walk.visit(state.cards[cid].name)
            for cid in player.battlefield:
                card = state.cards[cid]
                for value in (cid, card.name, card.types, card.keywords,
                              card.counters.get("__damage_marked", 0)):
                    walk.visit(value)
        walk.visit(state.players[pid].mana_pool)
        walk.visit(reasoning)
        for key in ("type", "card_id", "card_name", "ability_index", "selected_face_index",
                    "x_value", "attackers", "blocks", "targets", "cost_choice"):
            if key in action:
                walk.visit(action[key])
        for item in state.stack:
            payload = item.payload or {}
            for key, value in payload.items():
                if not key.startswith("__") or key in ("__announced_targets", "__source_lki", "__ability_target_text"):
                    walk.visit(key)
                    walk.visit(value)
            source = state.cards.get(item.source_card_id)
            for value in (item.id, item.label, item.effect_key,
                          source.oracle_text if source is not None else None,
                          source.name if source is not None else None,
                          source.types if source is not None else None,
                          source.mana_cost if source is not None else None):
                walk.visit(value)

    def trace_line(self, payload):
        prefix = "AI TRACE "
        encoded = checked_json(payload, self.limits["trace_entry_utf8_bytes"] - len(prefix),
                               "trace_entry", separators=(",", ":"), depth=self.limits["trace_depth"],
                               nodes=self.limits["trace_value_nodes"], scalar=self.limits["trace_scalar_utf8_bytes"])
        line = prefix + encoded
        self.before_clone(len(line))
        return line

    def accept_candidate(self, previous, candidate, trace_line=None):
        self.check_deadline()
        if len(candidate.cards) > self.limits["trace_value_nodes"]:
            raise SimulationResourceLimit("trace_nodes")
        size = self._log_cost(candidate.log)
        prefix = len(candidate.log) >= len(previous.log) and all(
            candidate.log[index] == line for index, line in enumerate(previous.log))
        added = size - self.game_bytes if prefix else size
        entries = len(candidate.log) - self.game_entries if prefix else len(candidate.log)
        if added > self.limits["action_log_growth_reserve"]:
            raise SimulationResourceLimit("action_log")
        trace_bytes = len(trace_line) if trace_line is not None else 0
        final_size, final_entries = size + trace_bytes, len(candidate.log) + (trace_line is not None)
        if final_size > self.limits["game_log_utf8_bytes"]:
            raise SimulationResourceLimit("game_log")
        if final_entries > self.limits["game_log_entries"]:
            raise SimulationResourceLimit("game_log_entries")
        self._check_batch(added + trace_bytes, entries + (trace_line is not None))
        if trace_line is not None:
            candidate.log.insert(len(previous.log), trace_line)
        self.game_bytes, self.game_entries = final_size, final_entries
        self.batch_bytes += added + trace_bytes
        self.batch_entries += entries + (trace_line is not None)

    def checked_result(self, result):
        self.check_deadline()
        limit = min(self.limits["result_json_bytes"], self.limits["snapshot_json_bytes"])
        _JSONWalk(limit, "result_json", self.limits["trace_depth"], limit).visit(result)
