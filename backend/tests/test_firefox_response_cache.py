"""Pure ASGI/local-file controls; no project app, database, browser or listener."""
import asyncio
import builtins
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'firefox_body_cache_app', Path(__file__).with_name('firefox_body_cache_app.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Timers:
    """Scheduling boundary only: no event loop self-pipe/socket is created."""
    def __init__(self): self.handles = []
    def call_later(self, delay, fn, *args):
        class Handle:
            cancelled = False
            def cancel(self): self.cancelled = True
        h = Handle(); self.handles.append((delay, fn, args, h)); return h
    def fire(self):
        for _, fn, args, h in list(self.handles):
            if not h.cancelled: fn(*args)

def drive(coro):
    try: coro.send(None)
    except StopIteration as end: return end.value
    raise AssertionError('Unexpected asynchronous I/O in synthetic ASGI test')

class ScratchCase(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module, 'Approved body broker feature is absent')
        self.scratch = tempfile.TemporaryDirectory(prefix="firefox-body-unit-", dir="/tmp")
        self.addCleanup(self.scratch.cleanup)
        self.cache = Path(self.scratch.name).resolve()
        self.cache.chmod(0o700)
        self.scope = {'type':'http', 'method':'GET', 'path':'/matches/test', 'raw_path':b'/matches/test', 'query_string':b'', 'headers':[(b'origin',b'http://127.0.0.1:15173')]}
        self.enrollment = {'run_nonce':'0'*32, 'episode':'human_vs_human', 'api_origin':'http://127.0.0.1:19000', 'frontend_origin':'http://127.0.0.1:15173', 'source_binding':'a'*64}
        self.publish_control(True,1)
        self.loop = Timers()
        timer_patch = patch.object(module.asyncio, "get_running_loop", return_value=self.loop)
        timer_patch.start()
        self.addCleanup(timer_patch.stop)
    def publish_control(self, enabled, generation):
        at=time.monotonic_ns()
        self.control={**self.enrollment,'schema_version':1,'generation':generation,'enabled':enabled,'publisher_uid':os.getuid(),'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'native_top_context':'context-unit' if enabled else None,'armed_ns':str(at),'expires_ns':str(at+900000000000)}
        p=self.cache/'enrollment.json';p.write_text(json.dumps(self.control));os.chmod(p,0o600)
    def data_files(self):return [p for p in self.cache.iterdir() if re.fullmatch(r'[0-9a-f]{32}\.(body|json|claim|release)',p.name)]
    def make(self, upstream): return module.BodyCache(upstream, self.cache, {k:self.enrollment[k] for k in ('run_nonce','source_binding','api_origin','frontend_origin')})
    def run_app(self, broker, scope=None):
        sent = []
        async def receive(): return {'type':'http.request','body':b'', 'more_body':False}
        async def send(message): sent.append(message)
        drive(broker(scope or self.scope, receive, send)); return sent

class CacheTests(ScratchCase):
    def test_original_capture_constants_and_real_producer_identity(self):
        self.assertEqual(module.MAX_BODY, 8 * 1024 * 1024)
        self.assertEqual(module.TTL_NS, 15_000_000_000)
        self.assertEqual(module.CAPTURE, b'x-release-test-capture-id')
        broker = self.response()
        self.run_app(broker)
        metadata = next(iter(broker.entries.values()))['metadata']
        self.assertEqual(metadata['producer_pid'], os.getpid())
        self.assertEqual(metadata['producer_start'],
                         Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
        broker.close()

    def test_buffers_complete_genuine_reply_before_forwarding_once(self):
        calls=[]; completed=[]; wire=[]
        async def original(scope, receive, send):
            calls.append((scope,receive))
            await send({'type':'http.response.start','status':200,'headers':[(b'x-probe',b'one'),(b'x-probe',b'two'),(b'content-type',b'application/json')]})
            self.assertEqual(wire, [])
            await send({'type':'http.response.body','body':b'{"ok":','more_body':True})
            self.assertEqual(wire, [])
            completed.append(True)
            await send({'type':'http.response.body','body':b'true}','more_body':False})
        async def receive(): return {'type':'http.request','body':b'', 'more_body':False}
        async def send(message):
            self.assertEqual(completed,[True])
            self.assertEqual(len([p for p in self.data_files() if p.suffix=='.json']),1)
            wire.append(message)
        broker=self.make(original); drive(broker(self.scope, receive, send))
        self.assertEqual(len(calls),1);self.assertIs(calls[0][0],self.scope);self.assertIs(calls[0][1],receive)
        self.assertEqual(wire[0]['headers'][:-1],[(b'x-probe',b'one'),(b'x-probe',b'two'),(b'content-type',b'application/json')])
        self.assertEqual(wire[0]['headers'][-1][0],b'x-release-test-capture-id')
        self.assertRegex(wire[0]['headers'][-1][1].decode(),'^[0-9a-f]{32}$')
        self.assertEqual(b''.join(m.get('body',b'') for m in wire),b'{"ok":true}')
        self.assertEqual(next(self.cache.glob('*.body')).read_bytes(),b'{"ok":true}')
        meta=json.loads(next(p for p in self.data_files() if p.suffix=='.json').read_bytes());self.assertEqual(meta['body_sha256'],hashlib.sha256(b'{"ok":true}').hexdigest())
        self.assertEqual(int(meta['expires_ns'])-int(meta['published_ns']),15_000_000_000)
        self.assertEqual(len(broker.entries),1)
    def test_post_and_options_are_eligible_without_request_changes(self):
        for method,status,body in [('POST',200,b'{"id":"x"}'),('OPTIONS',204,b'')]:
            self.scope['method']=method
            async def original(scope, receive, send):
                self.assertIs(scope,self.scope)
                await send({'type':'http.response.start','status':status,'headers':[]})
                await send({'type':'http.response.body','body':body})
            sent=self.run_app(self.make(original));self.assertEqual(sent[0]['status'],status)
            self.assertEqual(sent[1]['body'],body)
    def test_image_and_fixture_routes_passthrough_without_capture(self):
        for path in ['/card-images/x','/__built__/fixture']:
            scope={**self.scope,'path':path,'raw_path':path.encode()}; messages=[{'type':'http.response.start','status':200,'headers':[]},{'type':'http.response.body','body':b'x'}]
            async def original(scope,receive,send):
                for m in messages: await send(m)
            self.assertEqual(self.run_app(self.make(original),scope),messages)
        self.assertEqual(self.data_files(),[])
    def test_nonhttp_scope_and_receive_delegate_identically(self):
        seen=[]
        async def original(scope,receive,send): seen.append(scope);await send({'type':'lifespan.startup.complete'})
        s={'type':'lifespan'};self.assertEqual(self.run_app(self.make(original),s),[{'type':'lifespan.startup.complete'}]);self.assertIs(seen[0],s)
    def test_compressed_reply_unavailable_never_partial_success(self):
        async def original(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[(b'content-encoding',b'gzip')]})
            await send({'type':'http.response.body','body':b'compressed'})
        with self.assertRaises(module.Unavailable): self.run_app(self.make(original))
        self.assertEqual(self.data_files(),[])
    def test_reserved_capture_header_collision_unavailable(self):
        async def original(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[(b'X-Release-Test-Capture-Id',b'existing')]})
        with self.assertRaises(module.Unavailable): self.run_app(self.make(original))
        self.assertEqual(self.data_files(),[])
    def test_eight_mib_limit_counts_chunks_without_truncation(self):
        async def original(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'x'*(8*1024*1024),'more_body':True})
            await send({'type':'http.response.body','body':b'y'})
        with self.assertRaises(module.Unavailable): self.run_app(self.make(original))
        self.assertEqual(self.data_files(),[])
    def test_upstream_exception_after_body_does_not_publish_success(self):
        async def original(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'partial','more_body':True})
            raise ValueError('synthetic upstream failure')
        with self.assertRaises(ValueError): self.run_app(self.make(original))
        self.assertEqual(self.data_files(),[])
    def test_incomplete_body_and_trailers_are_unavailable(self):
        for trailers in [False,True]:
            async def original(scope,receive,send):
                await send({'type':'http.response.start','status':200,'headers':[],'trailers':trailers})
                if not trailers: await send({'type':'http.response.body','body':b'partial','more_body':True})
            with self.assertRaises(module.Unavailable): self.run_app(self.make(original))
    def test_sixtyfour_capacity_is_failclosed_and_shutdown_cleans_owned(self):
        async def original(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'{}'})
        broker=self.make(original)
        for _ in range(64): self.run_app(broker)
        with self.assertRaises(module.Unavailable): self.run_app(broker)
        self.assertEqual(len(list(self.cache.glob('*.body'))),64)
        broker.close();self.assertEqual(self.data_files(),[])
    def test_cleanup_refuses_replaced_inode(self):
        async def original(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]});await send({'type':'http.response.body','body':b'{}'})
        broker=self.make(original);self.run_app(broker);p=next(self.cache.glob('*.body'));p.unlink();p.write_bytes(b'replacement');os.chmod(p,0o600)
        with self.assertRaises(module.Unavailable):broker.close()
        self.assertEqual(p.read_bytes(),b'replacement')
    def test_wrong_root_mode_rejected_before_upstream(self):
        # Wrong root mode must fail before upstream is ever invoked.
        os.chmod(self.cache,0o755)
        async def original(*args):raise AssertionError('must not execute')
        with self.assertRaises(module.Unavailable):self.make(original)

    def response(self):
        async def original(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'{}'})
        return self.make(original)

    def receipts(self, broker, method='network.continueResponse', write_release=True):
        capture, entry = next(iter(broker.entries.items()))
        claim = {'schema_version':1,'kind':'response_body_claim','capture_id':capture,'run_nonce':'0'*32,
                 'episode':'human_vs_human','native_context':'context-unit','native_request_id':'request-unit',
                 'response_status':200,'body_sha256':hashlib.sha256(b'{}').hexdigest(),'source_binding':'a'*64,'enrollment_generation':entry['metadata'].get('enrollment_generation',1)}
        path = self.cache / (capture+'.claim')
        path.write_text(json.dumps(claim));os.chmod(path,0o600)
        if write_release:
            path = self.cache / (capture+'.release')
            path.write_text(json.dumps({**claim,'kind':'native_ack_release','ack_method':method,'ack_command_id':7}));os.chmod(path,0o600)
        return capture, entry

    def test_valid_release_reclaims_all_four_inodes_before_next_admission(self):
        broker=self.response();self.run_app(broker);capture,entry=self.receipts(broker)
        self.run_app(broker)
        self.assertFalse(any((self.cache/(capture+suffix)).exists() for suffix in ('.body','.json','.claim','.release')))
        self.assertEqual(len(broker.entries),1)
        broker.close()

    def test_partial_release_cannot_reclaim_or_execute_another_app(self):
        broker=self.response();self.run_app(broker);capture,entry=self.receipts(broker,write_release=False)
        p=self.cache/(capture+'.release');p.write_bytes(b'{');os.chmod(p,0o600)
        with self.assertRaises(module.Unavailable):self.run_app(broker)
        self.assertEqual(len(broker.entries),1)
        self.assertEqual(p.read_bytes(),b'{')

    def test_continue_request_or_wrong_native_bindings_never_free_a_slot(self):
        broker=self.response();self.run_app(broker);capture,entry=self.receipts(broker,method='network.continueRequest')
        with self.assertRaises(module.Unavailable):self.run_app(broker)
        self.assertEqual(len(broker.entries),1)

    def test_authenticated_claim_without_ack_expires_at_fixed_deadline(self):
        broker=self.response();self.run_app(broker);capture,entry=self.receipts(broker,write_release=False)
        saved=module.time.monotonic_ns
        module.time.monotonic_ns=lambda:entry['expires_ns']
        try:broker._expire(capture)
        finally:module.time.monotonic_ns=saved
        self.assertEqual(broker.entries,{})
        self.assertEqual(self.data_files(),[])

    def test_release_without_claim_is_residual_error_not_cleanup_permission(self):
        broker=self.response();self.run_app(broker);capture,entry=self.receipts(broker)
        (self.cache/(capture+'.claim')).unlink()
        with self.assertRaises(module.Unavailable):broker.close()
        self.assertTrue((self.cache/(capture+'.release')).exists())

    def test_real_file_descriptor_balance_on_authenticated_cleanup(self):
        opened=[];closed=[];old_open,old_close=module.os.open,module.os.close
        def counted_open(*args,**kwargs):fd=old_open(*args,**kwargs);opened.append(fd);return fd
        def counted_close(fd):closed.append(fd);return old_close(fd)
        module.os.open=counted_open;module.os.close=counted_close
        try:
            broker=self.response();self.run_app(broker);self.receipts(broker);self.run_app(broker);broker.close()
        finally:module.os.open=old_open;module.os.close=old_close
        self.assertGreaterEqual(len(opened),6)
        self.assertEqual(sorted(opened),sorted(closed))

    def test_all_sixtyfour_authenticated_releases_reclaim_actual_files(self):
        broker=self.response()
        for _ in range(64):self.run_app(broker)
        for capture,entry in list(broker.entries.items()):
            claim={'schema_version':1,'kind':'response_body_claim','capture_id':capture,'run_nonce':'0'*32,
                   'episode':'human_vs_human','native_context':'context-unit','native_request_id':'request-'+capture,
                   'response_status':200,'body_sha256':hashlib.sha256(b'{}').hexdigest(),'source_binding':'a'*64,'enrollment_generation':entry['metadata'].get('enrollment_generation',1)}
            for suffix,value in [('.claim',claim),('.release',{**claim,'kind':'native_ack_release','ack_method':'network.failRequest','ack_command_id':7})]:
                p=self.cache/(capture+suffix);p.write_text(json.dumps(value));os.chmod(p,0o600)
        self.assertEqual(len(self.data_files()),256)
        self.run_app(broker)
        self.assertEqual(len(broker.entries),1)
        self.assertEqual(len(self.data_files()),2)
        broker.close()

    def test_absent_disabled_enrollment_preserves_genuine_response_without_marker(self):
        for state in ('absent','disabled'):
            if state=='absent':(self.cache/'enrollment.json').unlink()
            else:self.publish_control(False,2)
            broker=self.response();sent=self.run_app(broker)
            self.assertEqual(sent,[{'type':'http.response.start','status':200,'headers':[]},{'type':'http.response.body','body':b'{}'}])
            self.assertEqual(broker.entries,{})

    def test_retirement_during_body_capture_never_publishes_a_marker(self):
        async def original(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            self.publish_control(False,2)
            await send({'type':'http.response.body','body':b'{}'})
        broker=self.make(original);sent=self.run_app(broker)
        self.assertEqual(sent[0]['headers'],[]);self.assertEqual(broker.entries,{})

    def test_malformed_or_replaced_same_generation_record_is_unavailable(self):
        broker=self.response();self.run_app(broker)
        self.publish_control(True,1)
        with self.assertRaises(module.Unavailable):self.run_app(broker)

    def test_entry_keeps_old_generation_binding_for_authentic_cleanup(self):
        broker=self.response();self.run_app(broker);capture,entry=self.receipts(broker)
        self.publish_control(False,2)
        self.run_app(broker)
        self.assertEqual(broker.entries,{})
        self.assertEqual(self.data_files(),[])

    def test_release_common_fields_reject_boolean_and_float_coercions(self):
        for field,value in [('schema_version',True),('schema_version',1.0),('enrollment_generation',True),('enrollment_generation',1.0),('response_status',200.0)]:
            broker=self.response();self.run_app(broker);capture,entry=self.receipts(broker)
            p=self.cache/(capture+'.release');receipt=json.loads(p.read_bytes());receipt[field]=value;p.write_text(json.dumps(receipt));os.chmod(p,0o600)
            with self.assertRaises(module.Unavailable):self.run_app(broker)
            self.assertTrue((self.cache/(capture+'.body')).exists());self.assertTrue(p.exists())

    def assert_release_integer_type(self, field, value):
        broker=self.response();self.run_app(broker);capture,entry=self.receipts(broker)
        p=self.cache/(capture+'.release');receipt=json.loads(p.read_bytes());receipt[field]=value;p.write_text(json.dumps(receipt));os.chmod(p,0o600)
        with self.assertRaises(module.Unavailable):self.run_app(broker)
        self.assertTrue((self.cache/(capture+'.body')).exists())
    def test_release_schema_version_bool_rejected(self):self.assert_release_integer_type('schema_version',True)
    def test_release_generation_float_rejected(self):self.assert_release_integer_type('enrollment_generation',1.0)
    def test_release_status_float_rejected(self):self.assert_release_integer_type('response_status',200.0)

    def test_constructor_requires_exact_four_immutable_bootstrap_bindings(self):
        bindings={k:self.enrollment[k] for k in ('run_nonce','source_binding','api_origin','frontend_origin')}
        good=module.BodyCache(None,self.cache,bindings)
        bindings['run_nonce']='f'*32
        self.assertEqual(good.enrollment['run_nonce'],'0'*32)
        for field,value in [('run_nonce',True),('run_nonce','A'*32),('run_nonce','0'*31),('source_binding',1.0),('source_binding','g'*64),('api_origin','http://127.0.0.1:0'),('frontend_origin','http://127.0.0.1:15173/path')]:
            bad=dict(good.enrollment);bad[field]=value
            with self.assertRaises(module.Unavailable):module.BodyCache(None,self.cache,bad)
        for bad in [None,{**good.enrollment,'episode':'human_vs_human'}]:
            with self.assertRaises(module.Unavailable):module.BodyCache(None,self.cache,bad)

    def test_bootstrap_rejects_each_control_binding_mismatch(self):
        for field,value in [('run_nonce','f'*32),('source_binding','b'*64),('api_origin','http://127.0.0.1:19001'),('frontend_origin','http://127.0.0.1:15174')]:
            broker=self.response();record=dict(self.control);record[field]=value
            p=self.cache/'enrollment.json';p.write_text(json.dumps(record));os.chmod(p,0o600)
            with self.assertRaises(module.Unavailable):self.run_app(broker)
            self.assertEqual(broker.entries,{})
            self.publish_control(True,1)


class BootstrapTests(ScratchCase):
    def setUp(self):
        super().setUp()
        self.env = {
            'MTG_RELEASE_BODY_CACHE_ROOT': str(self.cache),
            'MTG_RELEASE_BODY_CACHE_ENROLLMENT': str(self.cache / 'enrollment.json'),
            'MTG_BUILT_BACKEND_PORT': '19000',
            'MTG_BUILT_PAGE_ORIGIN': self.enrollment['frontend_origin'],
            'MTG_BROKER_RUN_NONCE': self.enrollment['run_nonce'],
            'MTG_BROKER_SOURCE_BINDING': self.enrollment['source_binding'],
        }

    def assert_rejected_before_project_import(self):
        self.assertTrue(callable(getattr(module, 'create_app', None)),
                        'Explicit create_app factory is absent')
        original_import = builtins.__import__
        attempts = []

        def reject_project(name, *args, **kwargs):
            if name == 'tests.current_built_browser_server' or name == 'main':
                attempts.append(name)
                raise AssertionError('Project import preceded bootstrap rejection')
            return original_import(name, *args, **kwargs)

        with patch.dict(os.environ, self.env, clear=True):
            with patch.object(builtins, '__import__', side_effect=reject_project):
                try:
                    with self.assertRaises(module.Unavailable):
                        module.create_app()
                finally:
                    self.assertEqual(attempts, [])

    def test_missing_each_bootstrap_env_rejected_before_import(self):
        for name in list(self.env):
            with self.subTest(name=name):
                value = self.env.pop(name)
                try:
                    self.assert_rejected_before_project_import()
                finally:
                    self.env[name] = value

    def test_empty_each_bootstrap_env_rejected_before_import(self):
        for name in list(self.env):
            with self.subTest(name=name):
                value = self.env[name]
                self.env[name] = ''
                try:
                    self.assert_rejected_before_project_import()
                finally:
                    self.env[name] = value

    def test_nonexistent_root_rejected_without_creating_it(self):
        missing = self.cache / 'missing'
        self.env['MTG_RELEASE_BODY_CACHE_ROOT'] = str(missing)
        self.env['MTG_RELEASE_BODY_CACHE_ENROLLMENT'] = str(missing / 'enrollment.json')
        self.assert_rejected_before_project_import()
        self.assertFalse(missing.exists())

    def test_relative_root_rejected_before_import(self):
        self.env['MTG_RELEASE_BODY_CACHE_ROOT'] = os.path.relpath(self.cache)
        self.assert_rejected_before_project_import()

    def test_noncanonical_root_spellings_rejected_before_import(self):
        root = str(self.cache)
        child = self.cache / 'child'
        child.mkdir(mode=0o700)
        for value in (root + '/', root + '/.', root + '/child/..', '/' + root):
            with self.subTest(root=value):
                self.env['MTG_RELEASE_BODY_CACHE_ROOT'] = value
                self.env['MTG_RELEASE_BODY_CACHE_ENROLLMENT'] = value + '/enrollment.json'
                self.assert_rejected_before_project_import()

    def test_symlink_root_rejected_before_import(self):
        alias = self.cache / 'alias'
        alias.symlink_to(self.cache, target_is_directory=True)
        self.env['MTG_RELEASE_BODY_CACHE_ROOT'] = str(alias)
        self.env['MTG_RELEASE_BODY_CACHE_ENROLLMENT'] = str(alias / 'enrollment.json')
        self.assert_rejected_before_project_import()

    def test_symlink_root_ancestor_rejected_before_import(self):
        actual = self.cache / 'actual'
        actual.mkdir(mode=0o700)
        (actual / 'nested').mkdir(mode=0o700)
        alias = self.cache / 'alias'
        alias.symlink_to(actual, target_is_directory=True)
        self.env['MTG_RELEASE_BODY_CACHE_ROOT'] = str(alias / 'nested')
        self.env['MTG_RELEASE_BODY_CACHE_ENROLLMENT'] = str(alias / 'nested/enrollment.json')
        self.assert_rejected_before_project_import()

    def test_root_file_rejected_before_import(self):
        self.env['MTG_RELEASE_BODY_CACHE_ROOT'] = str(self.cache / 'enrollment.json')
        self.assert_rejected_before_project_import()

    def test_insecure_root_mode_rejected_without_repair(self):
        self.cache.chmod(0o755)
        self.assert_rejected_before_project_import()
        self.assertEqual(self.cache.stat().st_mode & 0o7777, 0o755)

    def test_missing_enrollment_file_rejected_without_creating_it(self):
        path = self.cache / 'enrollment.json'
        path.unlink()
        self.assert_rejected_before_project_import()
        self.assertFalse(path.exists())

    def test_relative_enrollment_path_rejected_before_import(self):
        self.env['MTG_RELEASE_BODY_CACHE_ENROLLMENT'] = os.path.relpath(self.cache / 'enrollment.json')
        self.assert_rejected_before_project_import()

    def test_nonexact_enrollment_paths_rejected_before_import(self):
        root = str(self.cache)
        for path in (root + '/./enrollment.json', root + '//enrollment.json',
                     root + '/enrollment.json/', root + '/other.json',
                     root + '/../enrollment.json'):
            with self.subTest(path=path):
                self.env['MTG_RELEASE_BODY_CACHE_ENROLLMENT'] = path
                self.assert_rejected_before_project_import()

    def test_symlink_enrollment_file_rejected_before_import(self):
        path = self.cache / 'enrollment.json'
        target = self.cache / 'control.json'
        path.rename(target)
        path.symlink_to(target)
        self.assert_rejected_before_project_import()

    def test_hardlinked_enrollment_file_rejected_before_import(self):
        os.link(self.cache / 'enrollment.json', self.cache / 'control.json')
        self.assert_rejected_before_project_import()

    def test_enrollment_directory_rejected_before_import(self):
        path = self.cache / 'enrollment.json'
        path.unlink()
        path.mkdir(mode=0o700)
        self.assert_rejected_before_project_import()

    def test_insecure_enrollment_mode_rejected_without_repair(self):
        path = self.cache / 'enrollment.json'
        path.chmod(0o644)
        self.assert_rejected_before_project_import()
        self.assertEqual(path.stat().st_mode & 0o7777, 0o644)

    def test_malformed_enrollment_rejected_before_import(self):
        (self.cache / 'enrollment.json').write_bytes(b'{')
        self.assert_rejected_before_project_import()

    def test_duplicate_enrollment_keys_rejected_before_import(self):
        path = self.cache / 'enrollment.json'
        encoded = json.dumps(self.control)
        path.write_text('{"generation":1,' + encoded[1:])
        self.assert_rejected_before_project_import()

    def test_control_binding_mismatches_rejected_before_import(self):
        for key, value in (('run_nonce', 'f' * 32), ('source_binding', 'b' * 64),
                           ('api_origin', 'http://127.0.0.1:19001'),
                           ('frontend_origin', 'http://127.0.0.1:15174')):
            with self.subTest(key=key):
                record = {**self.control, key: value}
                (self.cache / 'enrollment.json').write_text(json.dumps(record))
                self.assert_rejected_before_project_import()

    def test_invalid_scalar_bindings_rejected_before_import(self):
        for key, value in (('MTG_BROKER_RUN_NONCE', 'A' * 32),
                           ('MTG_BROKER_SOURCE_BINDING', 'g' * 64),
                           ('MTG_BUILT_BACKEND_PORT', '019000'),
                           ('MTG_BUILT_BACKEND_PORT', '65536'),
                           ('MTG_BUILT_PAGE_ORIGIN', 'https://example.invalid')):
            with self.subTest(key=key, value=value):
                original = self.env[key]
                self.env[key] = value
                try:
                    self.assert_rejected_before_project_import()
                finally:
                    self.env[key] = original


if __name__ == '__main__':
    unittest.main(verbosity=2)
