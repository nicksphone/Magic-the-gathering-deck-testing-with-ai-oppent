# SPDX-License-Identifier: GPL-3.0-or-later
# Original host-store tests for the Forge Team/Card-Forge native engine.
# LABELLED SYNTHETIC format fixtures, never native-game or resume evidence.
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "checkpoint_store.py"
STORE = None
if MODULE_PATH.exists():
    module_spec = importlib.util.spec_from_file_location("checkpoint_store", MODULE_PATH)
    STORE = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(STORE)

BUILD_ID = "a" * 64
LIMIT = 64 * 1024 * 1024


def synthetic_checkpoint():
    """Synthetic one-of-two pending selection; not a captured native game."""
    first = {"card_id": 101, "owner_id": 17, "name": "SYNTHETIC FIRST"}
    second = {"card_id": 102, "owner_id": 17, "name": "SYNTHETIC SECOND"}
    offer = {
        "kind": "input:InputSelectEntitiesFromList", "actor": 17,
        "min": 1, "max": 1, "choices": [first, second],
        "turn": 2, "phase": "SYNTHETIC MAIN",
        "info": {"prompt": "SYNTHETIC; DO NOT INTERPRET", "selection": {
            "input": "InputSelectEntitiesFromList", "actor": 17,
            "min": 2, "max": 2, "chosen": [first],
            "generation": 3, "priority_epoch": 4, "revision": 5}},
    }
    ticket = {"offer": copy.deepcopy(offer), "selected": [first]}
    return {
        "schema": 1,
        "spec": {"human_seat": 1, "seed": 123, "open_decklists": True,
                 "decks": [{"file": "first.dck", "name": "SYNTHETIC A", "main": {}},
                           {"file": "second.dck", "name": "SYNTHETIC B", "main": {}}],
                 "synthetic_metadata": {"null": None, "bool": True, "unicode": "\u96ea"}},
        "decks": {"first.dck": "[metadata]\r\nName=SYNTHETIC \u96ea\r\n\r\n",
                  "second.dck": "[metadata]\nName=SYNTHETIC B\n"},
        "starts": 2, "completions": 1,
        "pending_offer": copy.deepcopy(offer),
        "actor_view": {"actor_id": 17, "turn": 2, "phase": "SYNTHETIC MAIN",
                       "selection": {"chosen": [first]}, "players": []},
        "native_state": {
            "players": [{"id": 17, "life": 20, "zones": {"Hand": [[101, "SYNTHETIC"]]},
                         "mana": [[1, 99, 17, False, False]]},
                        {"id": 23, "life": 19, "zones": {}, "mana": []}],
            "stack": [{"id": 7, "source": 101, "paid": [[1, 99, 17]]}],
            "turn": 2, "phase": "SYNTHETIC MAIN", "rng_delta": 41},
        "journals": {
            "starts": [
                {"start_id": 0, "parent_start": -1, "kind": "dispatch", "ticket": copy.deepcopy(ticket),
                 "parent_edge": {"synthetic": True}},
                {"start_id": 1, "parent_start": 0, "kind": "dialog", "ticket": copy.deepcopy(ticket)}],
            "completions": [{"start_id": 0, "kind": "dispatch", "ticket": copy.deepcopy(ticket),
                             "result": "SYNTHETIC RETURN", "producer": {"synthetic": True}}],
            "native": [{"event": "SYNTHETIC EVENT", "state": {"rng_delta": 40}}],
            "paid-pending": [{"synthetic": True, "paid": [[1, 99, 17]]}],
            "final": []},
    }


class SyntheticCheckpointStoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(STORE, "checkpoint_store.py has not been implemented")
        self.root = Path(tempfile.mkdtemp(prefix="synthetic-checkpoint-case-"))
        self.snapshot = self.root / "snapshot.json"
        self.archive = self.root / "archive"
        self.checkpoint = synthetic_checkpoint()
        self.write_snapshot()

    def write_snapshot(self, value=None, raw=None):
        if raw is None:
            raw = json.dumps(self.checkpoint if value is None else value,
                             ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        self.snapshot.write_bytes(raw)
        return raw

    def save(self):
        STORE.save_checkpoint(self.snapshot, self.archive, build_id=BUILD_ID)

    def load(self):
        return STORE.load_checkpoint(self.archive, build_id=BUILD_ID)

    def reject_snapshot(self, value):
        self.write_snapshot(value)
        with self.assertRaises(STORE.CheckpointError):
            self.save()
        self.assertFalse(self.archive.exists())

    def edit_manifest(self, edit):
        path = self.archive / "manifest.json"
        manifest = json.loads(path.read_bytes())
        edit(manifest)
        path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_roundtrip_exact_nine_keys_and_raw_snapshot_bytes(self):
        original = self.snapshot.read_bytes()
        self.save()
        self.assertEqual(set(self.archive.iterdir()),
                         {self.archive / "CHECKPOINT.json", self.archive / "manifest.json"})
        self.assertEqual((self.archive / "CHECKPOINT.json").read_bytes(), original)
        self.assertEqual(self.load(), self.checkpoint)
        self.assertEqual(len(self.load()), 9)
        self.assertEqual(json.loads((self.archive / "manifest.json").read_bytes()), {
            "schema": 1, "build_id": BUILD_ID,
            "checkpoint_sha256": hashlib.sha256(original).hexdigest()})

    def test_synthetic_one_of_two_pending_preserves_first_choice(self):
        self.save()
        restored = self.load()
        self.assertEqual(restored["pending_offer"]["info"]["selection"]["chosen"],
                         [{"card_id": 101, "owner_id": 17, "name": "SYNTHETIC FIRST"}])
        self.assertEqual(restored["pending_offer"]["info"]["selection"]["max"], 2)
        self.assertEqual(restored["pending_offer"]["max"], 1)
        STORE.verify_frontier(self.checkpoint, restored)

    def test_actor_is_native_player_id_not_human_seat(self):
        self.save()
        self.assertEqual(self.load()["actor_view"]["actor_id"], 17)
        self.assertEqual(self.load()["spec"]["human_seat"], 1)

    def test_mirrored_deck_filename_is_valid_and_restored_once(self):
        self.checkpoint["spec"]["decks"][1]["file"] = "first.dck"
        del self.checkpoint["decks"]["second.dck"]
        self.write_snapshot()
        self.save()
        target = self.root / "restored"
        STORE.restore_inputs(self.load(), target)
        self.assertEqual([p.name for p in (target / "decks").iterdir()], ["first.dck"])

    def test_zero_count_frontier_is_allowed_without_inferred_choice(self):
        self.checkpoint["starts"] = self.checkpoint["completions"] = 0
        self.checkpoint["journals"]["starts"] = []
        self.checkpoint["journals"]["completions"] = []
        self.write_snapshot()
        self.save()
        self.assertEqual(self.load(), self.checkpoint)

    def test_maximum_start_budget_and_all_completed_pending_frontier(self):
        row = self.checkpoint["journals"]["starts"][0]
        starts = [dict(copy.deepcopy(row), start_id=i) for i in range(1000)]
        self.checkpoint["starts"] = self.checkpoint["completions"] = 1000
        self.checkpoint["journals"]["starts"] = starts
        self.checkpoint["journals"]["completions"] = copy.deepcopy(list(reversed(starts)))
        self.write_snapshot()
        self.save()
        self.assertEqual(self.load(), self.checkpoint)

    def test_nested_json_is_preserved_without_defaults_or_choice_inference(self):
        self.checkpoint["spec"]["synthetic_metadata"]["tokens"] = ["SYNTHETIC DATA, NOT WIRE TOKENS"]
        self.checkpoint["pending_offer"]["info"]["selection"]["chosen"] = []
        self.checkpoint["actor_view"]["extension"] = {"ratio": 1.25, "empty": [], "null": None}
        self.write_snapshot()
        self.save()
        self.assertEqual(self.load(), self.checkpoint)

    def test_source_snapshot_and_dictionary_are_never_mutated(self):
        raw = self.snapshot.read_bytes()
        before = copy.deepcopy(self.checkpoint)
        self.save()
        loaded = self.load()
        STORE.restore_inputs(loaded, self.root / "restored")
        STORE.verify_frontier(self.checkpoint, loaded)
        self.assertEqual(self.snapshot.read_bytes(), raw)
        self.assertEqual(self.checkpoint, before)
        self.assertEqual(loaded, before)

    def test_restore_only_original_spec_and_exact_deck_text(self):
        target = self.root / "restored"
        STORE.restore_inputs(self.checkpoint, target)
        self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob("*")},
                         {"SPEC.json", "decks", "decks/first.dck", "decks/second.dck"})
        self.assertEqual(json.loads((target / "SPEC.json").read_bytes()), self.checkpoint["spec"])
        for name, content in self.checkpoint["decks"].items():
            self.assertEqual((target / "decks" / name).read_bytes(), content.encode("utf-8"))

    def test_fresh_archive_and_restore_are_private_under_permissive_umask(self):
        old = os.umask(0)
        try:
            self.save()
            target = self.root / "restored"
            STORE.restore_inputs(self.checkpoint, target)
        finally:
            os.umask(old)
        for root in (self.archive, target):
            for path in [root, *root.rglob("*")]:
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)

    def test_error_type_is_value_error(self):
        self.assertTrue(issubclass(STORE.CheckpointError, ValueError))
        with self.assertRaises(STORE.CheckpointError):
            STORE.load_checkpoint(self.root / "missing", build_id=BUILD_ID)

    def test_build_id_rejects_invalid_values_before_creating_destination(self):
        for build in (None, True, 1, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 64 + "\n"):
            with self.subTest(build=build), self.assertRaises(STORE.CheckpointError):
                STORE.save_checkpoint(self.snapshot, self.archive, build_id=build)
        self.assertFalse(self.archive.exists())

    def test_load_rejects_invalid_caller_build_id(self):
        self.save()
        with self.assertRaises(STORE.CheckpointError):
            STORE.load_checkpoint(self.archive, build_id="A" * 64)

    def test_load_rejects_changed_build_id(self):
        self.save()
        with self.assertRaises(STORE.CheckpointError):
            STORE.load_checkpoint(self.archive, build_id="b" * 64)

    def test_load_rejects_changed_checkpoint_hash(self):
        self.save()
        with (self.archive / "CHECKPOINT.json").open("ab") as handle:
            handle.write(b" ")
        with self.assertRaises(STORE.CheckpointError):
            self.load()

    def test_load_revalidates_schema_even_with_matching_hash(self):
        self.save()
        invalid = copy.deepcopy(self.checkpoint)
        invalid["extra"] = None
        raw = json.dumps(invalid).encode()
        (self.archive / "CHECKPOINT.json").write_bytes(raw)
        self.edit_manifest(lambda m: m.update(checkpoint_sha256=hashlib.sha256(raw).hexdigest()))
        with self.assertRaises(STORE.CheckpointError):
            self.load()

    def test_manifest_requires_exact_schema_and_valid_hash_and_build(self):
        self.save()
        path = self.archive / "manifest.json"
        original = path.read_bytes()
        for edit in (lambda m: m.update(extra=1), lambda m: m.pop("schema"),
                     lambda m: m.update(schema=True), lambda m: m.update(schema=2),
                     lambda m: m.update(build_id="A" * 64),
                     lambda m: m.update(checkpoint_sha256="g" * 64),
                     lambda m: m.update(checkpoint_sha256="0" * 64)):
            with self.subTest(edit=edit):
                path.write_bytes(original)
                self.edit_manifest(edit)
                with self.assertRaises(STORE.CheckpointError):
                    self.load()

    def test_manifest_rejects_duplicate_json_keys(self):
        self.save()
        path = self.archive / "manifest.json"
        raw = path.read_bytes()
        path.write_bytes(b'{"schema":1,' + raw[1:])
        with self.assertRaises(STORE.CheckpointError):
            self.load()

    def test_manifest_rejects_malformed_truncated_or_oversized_data(self):
        self.save()
        path = self.archive / "manifest.json"
        for raw in (b"", b"{", b"[]", b"\xff", b" " * 4097):
            with self.subTest(raw_length=len(raw)):
                path.write_bytes(raw)
                with self.assertRaises(STORE.CheckpointError):
                    self.load()

    def test_snapshot_requires_exact_nine_keys(self):
        for key in self.checkpoint:
            invalid = copy.deepcopy(self.checkpoint)
            del invalid[key]
            with self.subTest(missing=key):
                self.reject_snapshot(invalid)
        invalid = dict(self.checkpoint, extra=None)
        self.reject_snapshot(invalid)

    def test_snapshot_schema_is_integer_one_not_bool(self):
        for value in (True, False, 0, 2, "1", 1.0, None):
            with self.subTest(schema=value):
                self.reject_snapshot(dict(self.checkpoint, schema=value))

    def test_counts_require_integers_and_budget_and_completions_subset(self):
        for key in ("starts", "completions"):
            for value in (True, False, -1, 1001, 1.0, "1", None):
                with self.subTest(key=key, value=value):
                    self.reject_snapshot(dict(self.checkpoint, **{key: value}))
        self.reject_snapshot(dict(self.checkpoint, starts=0, completions=1))

    def test_count_and_journal_lengths_must_match(self):
        self.reject_snapshot(dict(self.checkpoint, starts=3))
        self.reject_snapshot(dict(self.checkpoint, completions=0))

    def test_journals_require_exact_five_keys_and_list_of_object_rows(self):
        for key in self.checkpoint["journals"]:
            invalid = copy.deepcopy(self.checkpoint)
            del invalid["journals"][key]
            with self.subTest(missing=key):
                self.reject_snapshot(invalid)
            for value in (None, {}, "rows", [None], [1], [[]]):
                invalid = copy.deepcopy(self.checkpoint)
                invalid["journals"][key] = value
                with self.subTest(stream=key, value=value):
                    self.reject_snapshot(invalid)
        invalid = copy.deepcopy(self.checkpoint)
        invalid["journals"]["extra"] = []
        self.reject_snapshot(invalid)

    def test_unfinished_snapshot_rejects_nonempty_final(self):
        invalid = copy.deepcopy(self.checkpoint)
        invalid["journals"]["final"] = [{"synthetic": True}]
        self.reject_snapshot(invalid)

    def test_start_ids_must_be_consecutive_in_order_without_duplicates(self):
        for value in (-1, 0, 3, True, 1.0, "1", None):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["journals"]["starts"][1]["start_id"] = value
            with self.subTest(start_id=value):
                self.reject_snapshot(invalid)
        invalid = copy.deepcopy(self.checkpoint)
        invalid["journals"]["starts"].reverse()
        self.reject_snapshot(invalid)

    def test_start_and_completion_rows_require_kind_ticket_and_start_id(self):
        for stream in ("starts", "completions"):
            for key in ("kind", "ticket", "start_id"):
                invalid = copy.deepcopy(self.checkpoint)
                del invalid["journals"][stream][0][key]
                with self.subTest(stream=stream, missing=key):
                    self.reject_snapshot(invalid)
            for key, value in (("kind", ""), ("kind", 1), ("ticket", []), ("ticket", None)):
                invalid = copy.deepcopy(self.checkpoint)
                invalid["journals"][stream][0][key] = value
                with self.subTest(stream=stream, key=key, value=value):
                    self.reject_snapshot(invalid)

    def test_duplicate_completion_ids_rejected(self):
        invalid = copy.deepcopy(self.checkpoint)
        invalid["completions"] = 2
        invalid["journals"]["completions"] *= 2
        self.reject_snapshot(invalid)

    def test_completion_ids_must_reference_existing_starts(self):
        for value in (-1, 2, True, 0.0, "0", None):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["journals"]["completions"][0]["start_id"] = value
            with self.subTest(start_id=value):
                self.reject_snapshot(invalid)

    def test_completion_kind_and_ticket_must_match_start(self):
        for key, value in (("kind", "different"), ("ticket", {"selected": []})):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["journals"]["completions"][0][key] = value
            with self.subTest(key=key):
                self.reject_snapshot(invalid)

    def test_spec_requires_object_human_seat_and_two_file_rows(self):
        for value in (None, [], "spec"):
            self.reject_snapshot(dict(self.checkpoint, spec=value))
        for value in (True, False, -1, 2, 0.0, "0", None):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["spec"]["human_seat"] = value
            with self.subTest(human_seat=value):
                self.reject_snapshot(invalid)
        for value in (None, {}, [], [{}], [{}, {}, {}], [None, None]):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["spec"]["decks"] = value
            with self.subTest(decks=value):
                self.reject_snapshot(invalid)

    def test_deck_references_must_exactly_match_imported_deck_names(self):
        for edit in (lambda d: d.pop("second.dck"), lambda d: d.update(extra="SYNTHETIC")):
            invalid = copy.deepcopy(self.checkpoint)
            edit(invalid["decks"])
            self.reject_snapshot(invalid)

    def test_deck_map_and_deck_text_require_json_objects_and_strings(self):
        for value in (None, [], "decks", {"first.dck": 1, "second.dck": "text"}):
            self.reject_snapshot(dict(self.checkpoint, decks=value))

    def test_unsafe_deck_basenames_rejected_before_any_restore_write(self):
        for name in ("", ".", "..", "./file", "../file", "a/b", "a\\b", "/absolute", "a\x00b"):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["spec"]["decks"][0]["file"] = name
            invalid["decks"][name] = invalid["decks"].pop("first.dck")
            with self.subTest(name=name):
                self.reject_snapshot(invalid)
                target = self.root / "restored"
                with self.assertRaises(STORE.CheckpointError):
                    STORE.restore_inputs(invalid, target)
                self.assertFalse(target.exists())

    def test_actor_view_and_pending_actor_must_match_existing_native_player(self):
        for actor in (True, -1, "17", 17.0, None, 999):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["pending_offer"]["actor"] = actor
            with self.subTest(actor=actor):
                self.reject_snapshot(invalid)
        invalid = copy.deepcopy(self.checkpoint)
        invalid["pending_offer"]["actor"] = invalid["actor_view"]["actor_id"] = 999
        self.reject_snapshot(invalid)
        invalid = copy.deepcopy(self.checkpoint)
        invalid["actor_view"]["actor_id"] = 23
        self.reject_snapshot(invalid)

    def test_pending_offer_actor_view_and_native_state_must_be_objects(self):
        for key in ("pending_offer", "actor_view", "native_state", "journals"):
            for value in (None, [], "object"):
                with self.subTest(key=key, value=value):
                    self.reject_snapshot(dict(self.checkpoint, **{key: value}))

    def test_native_state_requires_players_stack_turn_phase_rng(self):
        for key in ("players", "stack", "turn", "phase", "rng_delta"):
            invalid = copy.deepcopy(self.checkpoint)
            del invalid["native_state"][key]
            with self.subTest(missing=key):
                self.reject_snapshot(invalid)
        for key, value in (("players", []), ("players", {}), ("players", [{}]),
                           ("stack", {}), ("turn", True), ("turn", -1),
                           ("phase", None), ("rng_delta", True), ("rng_delta", -1)):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["native_state"][key] = value
            with self.subTest(key=key, value=value):
                self.reject_snapshot(invalid)

    def test_native_player_ids_require_distinct_nonnegative_integers(self):
        for value in (True, 17.0, "17", None, -1, 17):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["native_state"]["players"][1]["id"] = value
            with self.subTest(player_id=value):
                self.reject_snapshot(invalid)

    def test_pending_offer_requires_native_fields_not_wire_tokens(self):
        for key in ("kind", "actor", "min", "max", "choices", "info", "turn", "phase"):
            invalid = copy.deepcopy(self.checkpoint)
            del invalid["pending_offer"][key]
            with self.subTest(missing=key):
                self.reject_snapshot(invalid)
        for key, value in (("kind", ""), ("min", True), ("max", -1), ("choices", {}),
                           ("info", []), ("turn", True), ("phase", None),
                           ("request_id", "SYNTHETIC-WIRE"), ("tokens", ["SYNTHETIC-WIRE"])):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["pending_offer"][key] = value
            with self.subTest(key=key):
                self.reject_snapshot(invalid)
        invalid = copy.deepcopy(self.checkpoint)
        invalid["pending_offer"]["choices"][0]["token"] = "SYNTHETIC-WIRE"
        self.reject_snapshot(invalid)

    def test_snapshot_duplicate_json_keys_rejected_at_every_depth(self):
        raw = json.dumps(self.checkpoint).encode()
        for invalid in (b'{"schema":1,' + raw[1:],
                        raw.replace(b'"seed": 123', b'"seed": 123, "seed": 123'),
                        raw.replace(b'"rng_delta": 41', b'"rng_delta": 41, "rng_delta": 41')):
            self.write_snapshot(raw=invalid)
            with self.assertRaises(STORE.CheckpointError):
                self.save()

    def test_snapshot_malformed_truncated_nonobject_utf8_and_nonfinite_rejected(self):
        raw = json.dumps(self.checkpoint).encode()
        for invalid in (b"", b"{", raw[:-1], raw + b"{}", b"[]", b"null", b"\xff",
                        raw.replace(b'"seed": 123', b'"seed": NaN'),
                        raw.replace(b'"seed": 123', b'"seed": Infinity'),
                        raw.replace(b'"seed": 123', b'"seed": 1e999')):
            with self.subTest(length=len(invalid)):
                self.write_snapshot(raw=invalid)
                with self.assertRaises(STORE.CheckpointError):
                    self.save()

    def test_save_rejects_snapshot_over_64_mib(self):
        with self.snapshot.open("wb") as handle:
            handle.truncate(LIMIT + 1)
        with self.assertRaises(STORE.CheckpointError):
            self.save()

    def test_load_rejects_snapshot_over_64_mib(self):
        self.save()
        with (self.archive / "CHECKPOINT.json").open("wb") as handle:
            handle.truncate(LIMIT + 1)
        with self.assertRaises(STORE.CheckpointError):
            self.load()

    def test_save_rejects_symlink_snapshot_and_ancestor(self):
        alias = self.root / "alias.json"
        alias.symlink_to(self.snapshot)
        with self.assertRaises(STORE.CheckpointError):
            STORE.save_checkpoint(alias, self.archive, build_id=BUILD_ID)
        parent_alias = self.root / "alias-dir"
        parent_alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(STORE.CheckpointError):
            STORE.save_checkpoint(parent_alias / "snapshot.json", self.archive, build_id=BUILD_ID)

    def test_save_rejects_nonregular_snapshot_without_blocking(self):
        self.snapshot.unlink()
        os.mkfifo(self.snapshot)
        with self.assertRaises(STORE.CheckpointError):
            self.save()

    def test_load_rejects_archive_directory_symlink_and_ancestor(self):
        self.save()
        alias = self.root / "alias"
        alias.symlink_to(self.archive, target_is_directory=True)
        with self.assertRaises(STORE.CheckpointError):
            STORE.load_checkpoint(alias, build_id=BUILD_ID)
        parent_alias = self.root / "parent-alias"
        parent_alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(STORE.CheckpointError):
            STORE.load_checkpoint(parent_alias / "archive", build_id=BUILD_ID)

    def test_load_rejects_symlink_archive_files(self):
        self.save()
        for name in ("CHECKPOINT.json", "manifest.json"):
            path = self.archive / name
            original = path.read_bytes()
            outside = self.root / ("outside-" + name)
            outside.write_bytes(original)
            path.unlink()
            path.symlink_to(outside)
            with self.subTest(name=name), self.assertRaises(STORE.CheckpointError):
                self.load()
            path.unlink()
            path.write_bytes(original)

    def test_load_rejects_extra_entries_and_missing_files(self):
        self.save()
        extra = self.archive / "extra"
        extra.write_text("SYNTHETIC", encoding="utf-8")
        with self.assertRaises(STORE.CheckpointError):
            self.load()
        extra.unlink()
        extra.mkdir()
        with self.assertRaises(STORE.CheckpointError):
            self.load()
        extra.rmdir()
        (self.archive / "manifest.json").unlink()
        with self.assertRaises(STORE.CheckpointError):
            self.load()

    def test_load_rejects_nonregular_archive_entries_without_blocking(self):
        self.save()
        path = self.archive / "manifest.json"
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(STORE.CheckpointError):
            self.load()

    def test_save_and_restore_never_overwrite_existing_destination(self):
        for shape in ("empty-directory", "populated-directory", "file", "symlink", "dangling-symlink"):
            for operation in ("save", "restore"):
                with self.subTest(shape=shape, operation=operation):
                    target = self.root / (shape + "-" + operation)
                    if shape.endswith("directory"):
                        target.mkdir()
                        if shape == "populated-directory":
                            (target / "marker").write_bytes(b"SYNTHETIC UNCHANGED")
                    elif shape == "file":
                        target.write_bytes(b"SYNTHETIC UNCHANGED")
                    else:
                        target.symlink_to(self.root if shape == "symlink" else self.root / "absent")
                    with self.assertRaises(STORE.CheckpointError):
                        if operation == "save":
                            STORE.save_checkpoint(self.snapshot, target, build_id=BUILD_ID)
                        else:
                            STORE.restore_inputs(self.checkpoint, target)
                    if shape == "file":
                        self.assertEqual(target.read_bytes(), b"SYNTHETIC UNCHANGED")
                    elif shape == "populated-directory":
                        self.assertEqual((target / "marker").read_bytes(), b"SYNTHETIC UNCHANGED")
                    elif shape == "empty-directory":
                        self.assertEqual(list(target.iterdir()), [])
                    else:
                        self.assertTrue(target.is_symlink())

    def test_save_and_restore_reject_symlink_destination_parent(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        for operation in ("save", "restore"):
            with self.subTest(operation=operation), self.assertRaises(STORE.CheckpointError):
                if operation == "save":
                    STORE.save_checkpoint(self.snapshot, alias / operation, build_id=BUILD_ID)
                else:
                    STORE.restore_inputs(self.checkpoint, alias / operation)
        self.assertFalse((self.root / "save").exists())
        self.assertFalse((self.root / "restore").exists())

    def test_atomic_publish_does_not_replace_racing_empty_directory(self):
        real_fsync = os.fsync
        for operation in ("save", "restore"):
            target = self.root / ("race-" + operation)
            def race(fd):
                if not target.exists():
                    target.mkdir()
                return real_fsync(fd)
            with self.subTest(operation=operation):
                with mock.patch.object(STORE.os, "fsync", side_effect=race):
                    with self.assertRaises(STORE.CheckpointError):
                        if operation == "save":
                            STORE.save_checkpoint(self.snapshot, target, build_id=BUILD_ID)
                        else:
                            STORE.restore_inputs(self.checkpoint, target)
                self.assertEqual(list(target.iterdir()), [])

    def test_write_failure_never_publishes_partial_destination(self):
        with mock.patch.object(STORE.os, "fsync", side_effect=OSError("SYNTHETIC fsync failure")):
            with self.assertRaises(STORE.CheckpointError):
                self.save()
        self.assertFalse(self.archive.exists())
        self.assertEqual(self.snapshot.read_bytes(), self.write_snapshot())

    def test_restore_validates_entire_checkpoint_before_writing(self):
        invalid = copy.deepcopy(self.checkpoint)
        invalid["journals"]["completions"] *= 2
        target = self.root / "restored"
        with self.assertRaises(STORE.CheckpointError):
            STORE.restore_inputs(invalid, target)
        self.assertFalse(target.exists())

    def test_frontier_equality_is_independent_of_json_object_key_order(self):
        other = json.loads(json.dumps(self.checkpoint, sort_keys=True))
        STORE.verify_frontier(self.checkpoint, other)

    def test_frontier_rejects_changed_actor_even_when_internally_consistent(self):
        other = copy.deepcopy(self.checkpoint)
        other["pending_offer"]["actor"] = other["actor_view"]["actor_id"] = 23
        with self.assertRaises(STORE.CheckpointError):
            STORE.verify_frontier(self.checkpoint, other)

    def test_frontier_rejects_changed_rng(self):
        other = copy.deepcopy(self.checkpoint)
        other["native_state"]["rng_delta"] += 1
        with self.assertRaises(STORE.CheckpointError):
            STORE.verify_frontier(self.checkpoint, other)

    def test_frontier_rejects_changed_native_mana_and_stack_paid_costs(self):
        for edit in (lambda c: c["native_state"]["players"][0].update(mana=[]),
                     lambda c: c["native_state"]["stack"][0].update(paid=[])):
            other = copy.deepcopy(self.checkpoint)
            edit(other)
            with self.subTest(edit=edit), self.assertRaises(STORE.CheckpointError):
                STORE.verify_frontier(self.checkpoint, other)

    def test_frontier_rejects_changed_selected_pending_or_actor_view(self):
        for edit in (lambda c: c["pending_offer"]["info"]["selection"].update(chosen=[]),
                     lambda c: c["actor_view"]["selection"].update(chosen=[])):
            other = copy.deepcopy(self.checkpoint)
            edit(other)
            with self.subTest(edit=edit), self.assertRaises(STORE.CheckpointError):
                STORE.verify_frontier(self.checkpoint, other)

    def test_frontier_rejects_changed_journals_including_native_and_paid_pending(self):
        for stream in ("native", "paid-pending"):
            other = copy.deepcopy(self.checkpoint)
            other["journals"][stream].append({"synthetic": True})
            with self.subTest(stream=stream), self.assertRaises(STORE.CheckpointError):
                STORE.verify_frontier(self.checkpoint, other)

    def test_frontier_validates_both_inputs_even_if_identically_invalid(self):
        invalid = dict(self.checkpoint, extra=None)
        for left, right in ((invalid, self.checkpoint), (self.checkpoint, invalid), (invalid, invalid)):
            with self.subTest(left_invalid="extra" in left, right_invalid="extra" in right):
                with self.assertRaises(STORE.CheckpointError):
                    STORE.verify_frontier(left, right)

    def test_frontier_distinguishes_nested_boolean_from_integer(self):
        other = copy.deepcopy(self.checkpoint)
        other["spec"]["synthetic_metadata"]["bool"] = 1
        with self.assertRaises(STORE.CheckpointError):
            STORE.verify_frontier(self.checkpoint, other)

    def test_dictionary_apis_reject_non_json_values_nonstring_keys_and_cycles(self):
        for value in (float("nan"), float("inf"), {1: "not JSON"}, (1, 2), {1, 2}, "\ud800"):
            invalid = copy.deepcopy(self.checkpoint)
            invalid["spec"]["synthetic_metadata"]["invalid"] = value
            with self.subTest(value=repr(value)), self.assertRaises(STORE.CheckpointError):
                STORE.restore_inputs(invalid, self.root / "restored")
        invalid = copy.deepcopy(self.checkpoint)
        invalid["spec"]["cycle"] = invalid
        with self.assertRaises(STORE.CheckpointError):
            STORE.verify_frontier(invalid, invalid)


if __name__ == "__main__":
    unittest.main()
