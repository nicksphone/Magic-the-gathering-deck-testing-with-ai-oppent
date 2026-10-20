"""Local-file release publication races; no app, event loop, or native browser."""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'release_stage_original_controls',
    Path(__file__).with_name('test_firefox_response_cache.py'))
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


class ReleaseStageRaceTests(original.ScratchCase):
    def prepared(self):
        broker = original.CacheTests.response(self)
        self.run_app(broker)
        capture, entry = original.CacheTests.receipts(self, broker, write_release=False)
        claim = json.loads((self.cache / (capture + '.claim')).read_bytes())
        release = {**claim, 'kind': 'native_ack_release',
                   'ack_method': 'network.continueResponse', 'ack_command_id': 7}
        stage = self.cache / (capture + '.release.next')
        fd = os.open(stage, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.addCleanup(os.close, fd)
        os.write(fd, json.dumps(release).encode())
        os.fsync(fd)
        final = self.cache / (capture + '.release')
        os.link(stage, final)
        self.assertEqual(stage.stat().st_nlink, 2)
        self.assertEqual(stage.stat().st_ino, final.stat().st_ino)
        return broker, capture, entry, stage, final, fd

    @contextmanager
    def publication_snapshot(self, prepared, change='complete'):
        broker, capture, entry, stage, final, fd = prepared
        native_lstat = Path.lstat
        calls = []

        def lstat(file, *args, **kwargs):
            if file == stage:
                calls.append(file)
                if len(calls) == 2:
                    if change == 'stage-survives':
                        final.unlink()
                        return native_lstat(stage, *args, **kwargs)
                    # Model pathname lookup before unlink and stat delivery after it.
                    # The returned nlink-one metadata is real, from the held inode.
                    stage.unlink()
                    snapshot = os.fstat(fd)
                    self.assertEqual(snapshot.st_nlink, 1)
                    self.assertEqual(snapshot.st_ino, final.stat().st_ino)
                    if change == 'unrelated-final':
                        replacement = self.cache / 'unrelated-final'
                        data = json.loads(final.read_bytes())
                        data['capture_id'] = 'f' * 32
                        replacement.write_text(json.dumps(data))
                        replacement.chmod(0o600)
                        os.replace(replacement, final)
                    elif change == 'bad-claim':
                        claim = self.cache / (capture + '.claim')
                        data = json.loads(claim.read_bytes())
                        data['body_sha256'] = 'f' * 64
                        claim.write_text(json.dumps(data))
                    elif change == 'root-drift':
                        self.cache.chmod(0o755)
                    return snapshot
            return native_lstat(file, *args, **kwargs)

        try:
            with patch.object(Path, 'lstat', lstat):
                yield
        finally:
            self.cache.chmod(0o700)
        self.assertGreaterEqual(len(calls), 2)

    def test_completed_same_inode_stage_unlink_reaps_only_authenticated_release(self):
        prepared = self.prepared()
        broker, capture, entry, stage, final, fd = prepared
        with self.publication_snapshot(prepared):
            try:
                sent = self.run_app(broker)
            except original.module.Unavailable as error:
                self.fail('Completed owned publication must admit the next response: ' + str(error))
        self.assertEqual(sent[0]['status'], 200)
        self.assertNotIn(capture, broker.entries)
        self.assertFalse(stage.exists())
        self.assertFalse(final.exists())
        self.assertEqual(os.fstat(fd).st_nlink, 0)
        self.assertEqual(len(broker.entries), 1)
        broker.close()

    def assert_rejected(self, change):
        prepared = self.prepared()
        broker, capture, entry, stage, final, fd = prepared
        with self.publication_snapshot(prepared, change):
            with self.assertRaises(original.module.Unavailable):
                self.run_app(broker)
        self.assertIs(broker.entries[capture], entry)
        self.assertEqual((self.cache / (capture + '.body')).read_bytes(), b'{}')
        self.assertEqual(len(broker.entries), 1)
        if change == 'stage-survives':
            self.assertTrue(stage.exists())
            self.assertFalse(final.exists())
        else:
            self.assertFalse(stage.exists())
            self.assertTrue(final.exists())
        if change == 'unrelated-final':
            self.assertEqual(json.loads(final.read_bytes())['capture_id'], 'f' * 32)
        if change == 'bad-claim':
            self.assertEqual(json.loads((self.cache / (capture + '.claim')).read_bytes())
                             ['body_sha256'], 'f' * 64)

    def test_surviving_stage_is_not_disappearance_or_cleanup_authority(self):
        self.assert_rejected('stage-survives')

    def test_unrelated_final_after_disappearance_is_not_a_release(self):
        self.assert_rejected('unrelated-final')

    def test_bad_claim_after_disappearance_is_not_cleanup_authority(self):
        self.assert_rejected('bad-claim')

    def test_root_drift_during_disappearance_is_not_ignored(self):
        self.assert_rejected('root-drift')


if __name__ == '__main__':
    unittest.main(verbosity=2)
