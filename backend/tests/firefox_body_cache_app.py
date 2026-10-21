"""Private test ASGI body buffer; no App/runtime authority or listener of its own."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import time

MAX_BODY = 8 * 1024 * 1024
TTL_NS = 15_000_000_000
CAPTURE = b'x-release-test-capture-id'

class Unavailable(RuntimeError):
    pass

class BodyCache:
    def __init__(self, upstream, directory, enrollment=None):
        self.upstream = upstream
        self.directory = Path(directory)
        if (not isinstance(enrollment, dict) or set(enrollment) != {'run_nonce','api_origin','frontend_origin','source_binding'}
                or not isinstance(enrollment['run_nonce'], str) or len(enrollment['run_nonce']) != 32
                or any(c not in '0123456789abcdef' for c in enrollment['run_nonce'])
                or not isinstance(enrollment['source_binding'], str) or len(enrollment['source_binding']) != 64
                or any(c not in '0123456789abcdef' for c in enrollment['source_binding'])
                or any(not isinstance(enrollment[k], str) or not enrollment[k].startswith('http://127.0.0.1:')
                       or not enrollment[k][17:].isascii() or not enrollment[k][17:].isdecimal()
                       or enrollment[k][17:] != str(int(enrollment[k][17:]))
                       or not 1 <= int(enrollment[k][17:]) <= 65535 for k in ('api_origin','frontend_origin'))):
            raise Unavailable('ENROLLMENT')
        self.enrollment = dict(enrollment)
        info = self.directory.lstat()
        if (not self.directory.is_absolute() or self.directory.resolve() != self.directory
                or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise Unavailable('CACHE_DIRECTORY')
        self.identity = (info.st_dev, info.st_ino)
        self.control_identity = None
        self.control_generation = 0
        self.publisher = None
        self.entries = {}
        self.pending = 0
        self.errors = []
        self.closed = False

    def _control(self):
        record = self._receipt({'id':'enrollment'}, '.json')
        if record is None: return None
        value, identity = record
        keys = {'schema_version','generation','enabled','episode','run_nonce','source_binding','api_origin','frontend_origin','publisher_uid','pid','start_ticks','native_top_context','armed_ns','expires_ns'}
        if (not isinstance(value, dict) or set(value) != keys or type(value['schema_version']) is not int or value['schema_version'] != 1
                or type(value['generation']) is not int or not 0 <= value['generation'] <= 6 or type(value['enabled']) is not bool
                or (value['generation'] == 0 and (value['enabled'] is not False or value['episode'] is not None
                    or value['native_top_context'] is not None or value['armed_ns'] != '0' or value['expires_ns'] != '0'))
                or (value['generation'] != 0 and value['episode'] not in ('human_vs_human','player_vs_ai','player_vs_ai-seat2'))
                or type(value['publisher_uid']) is not int or value['publisher_uid'] != os.getuid()
                or any(type(value[k]) is not int or not 0 < value[k] <= 9007199254740991 for k in ('pid','start_ticks'))
                or any(not isinstance(value[k], str) or not value[k].isascii() or not value[k].isdecimal()
                       or (len(value[k]) > 1 and value[k][0] == '0') or len(value[k]) > 20 for k in ('armed_ns','expires_ns'))
                or not isinstance(value['run_nonce'], str) or len(value['run_nonce']) != 32 or any(c not in '0123456789abcdef' for c in value['run_nonce'])
                or not isinstance(value['source_binding'], str) or len(value['source_binding']) != 64 or any(c not in '0123456789abcdef' for c in value['source_binding'])
                or any(not isinstance(value[k], str) or not value[k].startswith('http://127.0.0.1:') for k in ('api_origin','frontend_origin'))
                or (value['enabled'] and (not isinstance(value['native_top_context'], str) or not 0 < len(value['native_top_context']) <= 128))
                or (not value['enabled'] and value['native_top_context'] is not None)):
            raise Unavailable('ENROLLMENT_CONTROL_SCHEMA')
        expected_ms = 900000 if value['episode'] == 'human_vs_human' else 1200000
        if value['generation'] != 0 and int(value['expires_ns']) - int(value['armed_ns']) != expected_ms * 1000000:
            raise Unavailable('ENROLLMENT_CLOCK')
        initial_bootstrap = (value['generation'] == 0 and self.control_generation == 0
                             and self.control_identity is None and self.publisher is None)
        if value['generation'] < self.control_generation or (value['generation'] == self.control_generation
                and self.control_identity != identity and not initial_bootstrap):
            raise Unavailable('ENROLLMENT_GENERATION')
        publisher = (value['publisher_uid'], value['pid'], value['start_ticks'])
        actual_start = Path('/proc/'+str(value['pid'])+'/stat').read_text().rsplit(')',1)[1].split()[19]
        if actual_start != str(value['start_ticks']) or (self.publisher is not None and self.publisher != publisher):
            raise Unavailable('ENROLLMENT_PUBLISHER')
        bindings = {k:value[k] for k in ('run_nonce','source_binding','api_origin','frontend_origin')}
        if any(self.enrollment[k] != v for k,v in bindings.items()):
            raise Unavailable('ENROLLMENT_BINDING')
        self.publisher = publisher
        self.control_identity, self.control_generation = identity, value['generation']
        if not value['enabled'] or time.monotonic_ns() >= int(value['expires_ns']): return None
        return value

    def _root(self):
        info = self.directory.lstat()
        if ((info.st_dev, info.st_ino) != self.identity or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise Unavailable('CACHE_DIRECTORY_CHANGED')

    def _write(self, entry, suffix, data):
        self._root()
        path = self.directory / (entry['id'] + suffix)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise Unavailable('CACHE_FILE')
            entry['files'][suffix] = (info.st_dev, info.st_ino, info.st_ctime_ns, info.st_size)
            view = memoryview(data)
            while view:
                size = os.write(fd, view)
                if size <= 0: raise Unavailable('CACHE_WRITE')
                view = view[size:]
            os.fsync(fd)
        finally:
            final = os.fstat(fd)
            if suffix in entry['files']:
                entry['files'][suffix] = (final.st_dev, final.st_ino, final.st_ctime_ns, final.st_size)
            os.close(fd)

    def _remove(self, entry):
        self._root()
        # Validate the entire registered set before unlinking any of it.
        for suffix, identity in list(entry['files'].items()):
            path = self.directory / (entry['id'] + suffix)
            info = path.lstat()
            if ((info.st_dev, info.st_ino, info.st_ctime_ns, info.st_size) != identity or not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
                raise Unavailable('CACHE_INODE_CHANGED')
        for suffix in list(entry['files']):
            path = self.directory / (entry['id'] + suffix)
            path.unlink()
            del entry['files'][suffix]
        if entry.get('timer'): entry['timer'].cancel()
        self.entries.pop(entry['id'], None)

    def _receipt(self, entry, suffix):
        self._root()
        path = self.directory / (entry['id'] + suffix)
        try: before = path.lstat()
        except FileNotFoundError: return None
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) != 0o600 or before.st_size > 4096):
            raise Unavailable('CACHE_RECEIPT_FILE')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(fd)
            identity = (before.st_dev, before.st_ino, before.st_ctime_ns, before.st_size)
            if (opened.st_dev, opened.st_ino, opened.st_ctime_ns, opened.st_size) != identity:
                raise Unavailable('CACHE_RECEIPT_CHANGED')
            chunks = []
            while True:
                chunk = os.read(fd, 4097 - sum(map(len, chunks)))
                if not chunk: break
                chunks.append(chunk)
                if sum(map(len, chunks)) > 4096: raise Unavailable('CACHE_RECEIPT_CAP')
            final = os.fstat(fd)
            leaf = path.lstat()
            if any((s.st_dev, s.st_ino, s.st_ctime_ns, s.st_size) != identity for s in (final, leaf)):
                raise Unavailable('CACHE_RECEIPT_CHANGED')
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result: raise Unavailable('CACHE_RECEIPT_DUPLICATE_KEY')
                    result[key] = value
                return result
            try: value = json.loads(b''.join(chunks), object_pairs_hook=unique)
            except (ValueError, UnicodeError): raise Unavailable('CACHE_RECEIPT_JSON') from None
            return value, identity
        finally: os.close(fd)

    def _register_receipts(self, entry, require_release=False):
        # A staging name is mutable, not a receipt or cleanup authority.
        # The exact linked pair is deferred until the sole publisher removes it.
        def staging():
            self._root()
            stage = self.directory / (entry['id'] + '.release.next')
            try: info = stage.lstat()
            except FileNotFoundError: return None
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 4096
                    or info.st_nlink not in (1, 2)):
                raise Unavailable('CACHE_RELEASE_STAGE')
            final = self.directory / (entry['id'] + '.release')
            try: leaf = final.lstat()
            except FileNotFoundError: leaf = None
            try: current = stage.lstat()
            except FileNotFoundError: self._root(); return None
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise Unavailable('CACHE_RELEASE_STAGE_REPLACED')
            if (not stat.S_ISREG(current.st_mode) or current.st_uid != os.getuid()
                    or stat.S_IMODE(current.st_mode) != 0o600 or current.st_size > 4096
                    or current.st_nlink not in (1, 2)):
                raise Unavailable('CACHE_RELEASE_STAGE')
            info = current
            if info.st_nlink == 2:
                try: leaf = final.lstat()
                except FileNotFoundError: leaf = None
                if (leaf is None or not stat.S_ISREG(leaf.st_mode) or leaf.st_nlink != 2
                        or leaf.st_uid != info.st_uid or stat.S_IMODE(leaf.st_mode) != 0o600
                        or (leaf.st_dev, leaf.st_ino, leaf.st_ctime_ns, leaf.st_size)
                        != (info.st_dev, info.st_ino, info.st_ctime_ns, info.st_size)):
                    # Publication may have completed while inspecting its stage.
                    try: stage.lstat()
                    except FileNotFoundError: self._root(); return None
                    raise Unavailable('CACHE_RELEASE_STAGE_PAIR')
            elif leaf is not None:
                try: stage.lstat()
                except FileNotFoundError: self._root(); return None
                raise Unavailable('CACHE_RELEASE_STAGE_PAIR')
            return info
        staged = staging()
        release = None if staged is not None else self._receipt(entry, '.release')
        claim = self._receipt(entry, '.claim')
        if release is not None and claim is None: raise Unavailable('CACHE_RELEASE_WITHOUT_CLAIM')
        if require_release and release is None and staged is None: return False
        if claim is None:
            if staged is not None: raise Unavailable('CACHE_RELEASE_STAGE_WITHOUT_CLAIM')
            return False
        data, claim_identity = claim
        fields = {'schema_version','kind','capture_id','run_nonce','episode','native_context','native_request_id','response_status','body_sha256','source_binding','enrollment_generation'}
        if (not isinstance(data, dict) or set(data) != fields or type(data['schema_version']) is not int
                or data['schema_version'] != 1 or data['kind'] != 'response_body_claim'
                or type(data['response_status']) is not int
                or type(data['enrollment_generation']) is not int or not 1 <= data['enrollment_generation'] <= 6
                or any(not isinstance(data[k], str) or not 0 < len(data[k]) <= 128 for k in ('native_context','native_request_id'))):
            raise Unavailable('CACHE_CLAIM_SCHEMA')
        expected = {'capture_id':entry['id'], 'run_nonce':entry['metadata']['run_nonce'],
                    'episode':entry['metadata']['episode'], 'response_status':entry['metadata']['status'],
                    'body_sha256':entry['metadata']['body_sha256'], 'source_binding':entry['metadata']['source_binding'],
                    'enrollment_generation':entry['metadata']['enrollment_generation']}
        if any(data[k] != v for k, v in expected.items()): raise Unavailable('CACHE_CLAIM_BINDING')
        if '.claim' in entry['files'] and entry['files']['.claim'] != claim_identity:
            raise Unavailable('CACHE_CLAIM_REPLACED')
        if staged is not None:
            current = staging()
            if current is not None:
                if (current.st_dev, current.st_ino) != (staged.st_dev, staged.st_ino):
                    raise Unavailable('CACHE_RELEASE_STAGE_REPLACED')
                if not require_release: raise Unavailable('CACHE_RELEASE_STAGE_PENDING_CLEANUP')
                return False
            # Only exact staging-name disappearance admits the original reader.
            release = self._receipt(entry, '.release')
        if release is not None:
            released, release_identity = release
            if (not isinstance(released, dict) or set(released) != fields | {'ack_method','ack_command_id'}
                    or any(released[k] != v for k, v in data.items() if k != 'kind')
                    or any(type(released[k]) is not type(v) for k,v in data.items())
                    or released['kind'] != 'native_ack_release'
                    or released['ack_method'] not in ('network.continueResponse','network.failRequest','network.provideResponse')
                    or type(released['ack_command_id']) is not int or not 0 < released['ack_command_id'] <= 9007199254740991):
                raise Unavailable('CACHE_RELEASE_SCHEMA_BINDING')
            if '.release' in entry['files'] and entry['files']['.release'] != release_identity:
                raise Unavailable('CACHE_RELEASE_REPLACED')
            entry['files']['.release'] = release_identity
        entry['files']['.claim'] = claim_identity
        return release is not None

    def _reap(self):
        for entry in list(self.entries.values()):
            if self._register_receipts(entry, require_release=True): self._remove(entry)

    def _expire(self, capture):
        entry = self.entries.get(capture)
        if entry is None: return
        if time.monotonic_ns() < entry['expires_ns']:
            # asyncio timers can fire slightly early; retain the fixed deadline.
            entry['timer'] = asyncio.get_running_loop().call_later((entry['expires_ns']-time.monotonic_ns())/1e9, self._expire, capture)
            return
        try:
            self._register_receipts(entry)
            self._remove(entry)
        except Unavailable as error: self.errors.append(str(error))

    def close(self):
        self.closed = True
        errors = []
        for entry in list(self.entries.values()):
            if entry.get('timer'): entry['timer'].cancel()
            try:
                self._register_receipts(entry)
                self._remove(entry)
            except Unavailable as error: errors.append(str(error))
        if errors or self.errors: raise Unavailable('CACHE_CLEANUP_INCOMPLETE')

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if scope['type'] == 'lifespan':
            async def lifecycle(message):
                if message['type'] == 'lifespan.shutdown.complete': self.close()
                await send(message)
            return await self.upstream(scope, receive, lifecycle)
        if scope['type'] != 'http' or path.startswith(('/card-images/', '/__built__/')):
            return await self.upstream(scope, receive, send)
        if self.closed: raise Unavailable('CACHE_CLOSED')
        self._root()
        self._reap()
        control = self._control()
        if control is None: return await self.upstream(scope, receive, send)
        if len(self.entries) + self.pending >= 64: raise Unavailable('CACHE_CAPACITY')
        self.pending += 1
        start = None
        messages = []
        chunks = []
        total = 0
        complete = False
        entry = None
        async def capture(message):
            nonlocal start, total, complete
            kind = message['type']
            if complete: raise Unavailable('ASGI_AFTER_BODY')
            if kind == 'http.response.start':
                if start is not None or message.get('trailers') or set(message) - {'type','status','headers','trailers'}:
                    raise Unavailable('ASGI_START')
                for name, value in message.get('headers', []):
                    if not isinstance(name, bytes) or not isinstance(value, bytes): raise Unavailable('ASGI_HEADER')
                    if name.lower() == CAPTURE: raise Unavailable('CAPTURE_COLLISION')
                    if name.lower() == b'content-encoding' and value.lower().strip() != b'identity':
                        raise Unavailable('UNSUPPORTED_ENCODING')
                start = message
                if type(start.get('status')) is not int or not 100 <= start['status'] <= 599:
                    raise Unavailable('ASGI_STATUS')
            elif kind == 'http.response.body':
                if start is None or set(message) - {'type','body','more_body'}: raise Unavailable('ASGI_BODY')
                body = message.get('body', b'')
                if not isinstance(body, bytes): raise Unavailable('ASGI_BODY_TYPE')
                total += len(body)
                if total > MAX_BODY: raise Unavailable('CACHE_BODY_CAP')
                chunks.append(body)
                messages.append(message)
                complete = not message.get('more_body', False)
            else: raise Unavailable('ASGI_EXTENSION')
        try:
            await self.upstream(scope, receive, capture)
            if not complete or start is None: raise Unavailable('ASGI_INCOMPLETE')
            current = self._control()
            if current is None or any(current[k] != control[k] for k in ('generation','native_top_context','episode','armed_ns','expires_ns')):
                await send(start)
                for message in messages: await send(message)
                return
            body = b''.join(chunks)
            raw_path = scope.get('raw_path')
            query = scope.get('query_string', b'')
            if not isinstance(raw_path, bytes) or not isinstance(query, bytes): raise Unavailable('RAW_URL')
            if scope.get('method') not in ('GET','POST','OPTIONS'): raise Unavailable('ASGI_METHOD')
            if any(b < 0x21 or b > 0x7e for b in raw_path + query): raise Unavailable('RAW_URL_ASCII')
            capture_id = secrets.token_hex(16)
            published = time.monotonic_ns()
            entry = {'id':capture_id, 'files':{}, 'expires_ns':published+TTL_NS}
            self.entries[capture_id] = entry
            meta = {**{k:control[k] for k in ('run_nonce','episode','api_origin','frontend_origin','source_binding')},
                    'enrollment_generation':control['generation'], 'native_top_context':control['native_top_context'],
                    'schema_version':1, 'capture_id':capture_id,'method':scope['method'], 'status':start['status'],
                    'raw_path_sha256':hashlib.sha256(raw_path).hexdigest(), 'raw_path_length':len(raw_path),
                    'raw_query_sha256':hashlib.sha256(query).hexdigest(), 'raw_query_length':len(query),
                    'body_length':len(body),'body_sha256':hashlib.sha256(body).hexdigest(),
                    'producer_pid':os.getpid(),'producer_start':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
                    'published_ns':str(published),'expires_ns':str(published+TTL_NS)}
            data = json.dumps(meta, separators=(',',':'),sort_keys=True).encode()
            if len(data)>4096: raise Unavailable('CACHE_METADATA_CAP')
            entry['metadata'] = meta
            self._write(entry, '.body', body)
            self._write(entry, '.json', data)
            entry['timer'] = asyncio.get_running_loop().call_later(15, self._expire, capture_id)
            await send({**start,'headers':[*start.get('headers',[]),(CAPTURE,capture_id.encode())]})
            for message in messages: await send(message)
        except BaseException:
            if entry is not None: self._remove(entry)
            raise
        finally:
            self.pending -= 1


def create_app():
    """Uvicorn --factory entry point; caller owns the existing private cache."""
    root = os.environ.get('MTG_RELEASE_BODY_CACHE_ROOT')
    enrollment_path = os.environ.get('MTG_RELEASE_BODY_CACHE_ENROLLMENT')
    if not root or not enrollment_path:
        raise Unavailable('CACHE_ENV_BINDING')
    directory = Path(root)
    # Compare the original strings too: Path normalizes dots and trailing slashes.
    if str(directory) != root or enrollment_path != str(directory / 'enrollment.json'):
        raise Unavailable('CACHE_ENV_BINDING')
    bindings = {'run_nonce':os.environ.get('MTG_BROKER_RUN_NONCE'),
                'source_binding':os.environ.get('MTG_BROKER_SOURCE_BINDING'),
                'api_origin':'http://127.0.0.1:' + os.environ.get('MTG_BUILT_BACKEND_PORT',''),
                'frontend_origin':os.environ.get('MTG_BUILT_PAGE_ORIGIN')}
    try:
        broker = BodyCache(None, directory, bindings)
        if broker._receipt({'id':'enrollment'}, '.json') is None:
            raise Unavailable('CACHE_ENROLLMENT_MISSING')
        broker._control()
    except (OSError, ValueError):
        raise Unavailable('CACHE_BOOTSTRAP') from None
    from tests.current_built_browser_server import app as genuine_app
    broker.upstream = genuine_app
    return broker
