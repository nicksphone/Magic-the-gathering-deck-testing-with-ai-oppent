"""Owned real-main browser fixture transport; never run without a reviewed lease."""
import ast
import stat
import asyncio.base_events
import asyncio.selector_events
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import sys
import threading

SOURCE = Path(__file__).resolve().parents[2]
ROOT = SOURCE.parent
OWNED_ROOT = os.environ['MTG_BROWSER_OWNED_ROOT']
QUALIFIED_COMMIT = os.environ['MTG_BROWSER_QUALIFIED_COMMIT']
assert Path(OWNED_ROOT).is_absolute() and str(Path(OWNED_ROOT)) == OWNED_ROOT
assert str(Path(OWNED_ROOT).resolve()) == OWNED_ROOT
assert str(ROOT) == OWNED_ROOT
assert re.fullmatch('[0-9a-f]{40}', QUALIFIED_COMMIT)
OUT = ROOT / 'evidence/native-browser'
DB = ROOT / 'runtime/sql/api.db'
INITIAL_DATABASE = not DB.exists()
PORT = int(os.environ['MTG_BUILT_BACKEND_PORT'])
LEDGER = len(sys.argv) == 3 and sys.argv[1] == '--closed-ledger'
STARTUP_CANARY = sys.argv[1:] == ['--startup-closed-canary']
GRANT = json.loads((ROOT / 'runner/EXECUTION-GRANT.json').read_text())
assert GRANT == {'root': str(ROOT), 'source': str(SOURCE),
                 'commit': QUALIFIED_COMMIT,
                 'scope': 'one-real-app-startup-closedbackup' if STARTUP_CANARY else 'built-app-40paid-3recovery-3BO3-4origin',
                 'explicit_parent_grant': True, 'seconds': 120 if STARTUP_CANARY else 2400}
assert (ROOT / '.built-browser-owned').read_text() == str(SOURCE)
assert not (SOURCE / '.git').exists()
assert SOURCE.resolve() == SOURCE and DB.resolve() == DB
assert all(not p.is_symlink() for p in (SOURCE, *SOURCE.parents))
TOKEN = (ROOT / 'runner/fixture-token').read_text().strip()
assert re.fullmatch('[0-9a-f]{64}', TOKEN)
DENIALS = []
RECORDS = []
CANARIES = []
MEDIA = SOURCE / 'backend/card_data/image_cache'
MEDIA_PATHS = {path.resolve() for path in MEDIA.glob('*.svg')}
STARTUP_MEDIA = json.loads((ROOT / 'runner/startup-media-pins.json').read_text())
STARTUP_WRITES = {}


def deny(event):
    DENIALS.append(event)
    raise PermissionError('Owned built-browser IO denied: ' + event)


def in_constructor(code):
    frame = sys._getframe()
    while frame:
        if frame.f_code is code:
            return True
        frame = frame.f_back
    return False


def accepted_owned_listener():
    frame = sys._getframe()
    while frame:
        if frame.f_code is socket.socket.accept.__code__:
            listener = frame.f_locals.get('self')
            return listener is not None and listener.getsockname() == ('127.0.0.1', PORT)
        frame = frame.f_back
    return False


OWNER_LOCK = Path(str(DB) + '.capacity-owner.lock')
STORAGE_OWNER = None
STORAGE_ATTEMPTS = {}


def storage_regular(path, *, absent=False):
    if path.resolve() != path or path.is_symlink():
        deny('storage-noncanonical-path')
    try:
        info = path.lstat()
    except FileNotFoundError:
        if absent:
            return None
        raise
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        deny('storage-nonregular-or-linked-file')
    return info


def storage_frame(code):
    frame = sys._getframe()
    while frame:
        if frame.f_code is code:
            return frame
        frame = frame.f_back
    return None


def storage_owner(*, acquiring=False):
    module, app = sys.modules.get('persistence.capacity'), sys.modules.get('main')
    if LEDGER or module is None or app is None:
        return None
    code = module.DatabaseOwner.acquire.__code__ if acquiring else module.DatabaseOwner.backup.__code__
    frame = storage_frame(code)
    if frame is None:
        return None
    owner = frame.f_locals.get('self')
    if (type(owner) is not module.DatabaseOwner or owner.engine is not app.engine
            or owner.path != DB or owner.lock_path != OWNER_LOCK or owner.pid != os.getpid()
            or not re.fullmatch('[0-9a-f]{32}', owner.epoch)
            or owner.engine.dialect.name != 'sqlite' or owner.engine.url.database != str(DB)
            or owner.engine.url.query or owner.path.resolve() != DB
            or code.co_filename != str(SOURCE / 'backend/persistence/capacity.py')):
        deny('storage-owner-binding')
    if acquiring:
        if owner.fd is not None or module._OWNERS.get(owner.engine) is not None:
            deny('storage-acquire-not-fresh')
    else:
        if (module._OWNERS.get(owner.engine) is not owner or owner.fd is None
                or owner.engine.pool is not owner.pool):
            deny('storage-backup-not-registered')
        info, descriptor = storage_regular(OWNER_LOCK), os.fstat(owner.fd)
        if (not stat.S_ISREG(descriptor.st_mode) or descriptor.st_nlink != 1
                or (info.st_dev, info.st_ino) != owner.identity
                or (descriptor.st_dev, descriptor.st_ino) != owner.identity):
            deny('storage-backup-lock-identity')
        database = storage_regular(DB)
        if owner.database_identity != (database.st_dev, database.st_ino):
            deny('storage-backup-database-identity')
    return owner


def storage_backup():
    owner = storage_owner()
    if owner is None:
        return None
    module, app = sys.modules.get('scripts.verify_storage_restore'), sys.modules['main']
    if module is None:
        return None
    frame = storage_frame(module._backup_validated_database.__code__)
    capacity = sys.modules['persistence.capacity']
    initializer = storage_frame(capacity.initialize_capacity.__code__)
    # The async lifespan is executing its bootstrap here, not its suspended yield.
    lifespan = storage_frame(app.lifespan.__wrapped__.__code__)
    backup = DB.with_name(DB.name + '.before-capacity-' + owner.epoch + '.db')
    if (frame is None or initializer is None or lifespan is None
            or lifespan.f_locals.get('owner') is not owner
            or lifespan.f_locals.get('backup') != backup
            or initializer.f_locals.get('owner') is not owner
            or initializer.f_locals.get('backup_path') != backup
            or frame.f_locals.get('source') != DB
            or frame.f_locals.get('destination') != backup):
        deny('storage-backup-producer-binding')
    return owner, backup, frame


def storage_open(path, flags):
    global STORAGE_OWNER
    if path == OWNER_LOCK:
        owner = storage_owner(acquiring=True)
        if owner is None or flags != os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC:
            deny('storage-lock-open-contract')
        info = storage_regular(path, absent=True)
        if info is not None and info.st_size != 0:
            deny('storage-lock-content')
        if STORAGE_OWNER is not None and STORAGE_OWNER is not owner:
            deny('storage-multiple-owner-in-process')
        STORAGE_OWNER = owner
        RECORDS.append({'event': 'storage-acquire-attempt', 'epoch': owner.epoch, 'path': str(path)})
        publish_storage('acquire-attempt')
        return True
    context = storage_backup()
    if context is None:
        return False
    owner, backup, frame = context
    if path != backup or flags not in {os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                                      os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC}:
        return False
    if owner.epoch in STORAGE_ATTEMPTS or frame.f_locals.get('reserved') is not False:
        deny('storage-backup-repeat')
    for suffix in ('', '-wal', '-shm', '-journal'):
        if Path(str(backup) + suffix).exists():
            deny('storage-backup-occupied')
    if storage_regular(DB).st_size > 128 * 1024 * 1024:
        deny('storage-backup-source-byte-bound')
    STORAGE_ATTEMPTS[owner.epoch] = {'path': str(backup), 'reserved_attempt': True}
    RECORDS.append({'event': 'storage-backup-reserve-attempt', 'epoch': owner.epoch, 'path': str(backup)})
    publish_storage('backup-reserve-attempt')
    return True


def storage_cleanup(path):
    context = storage_backup()
    if context is None:
        return False
    owner, backup, frame = context
    if (frame.f_locals.get('reserved') is not True or sys.exception() is None
            or owner.epoch not in STORAGE_ATTEMPTS
            or path not in {Path(str(backup) + suffix) for suffix in ('', '-wal', '-shm', '-journal')}):
        return False
    RECORDS.append({'event': 'storage-failed-backup-cleanup', 'path': str(path),
                    'epoch': owner.epoch, 'exception_type': type(sys.exception()).__name__})
    return True


def storage_sql(raw):
    context = storage_backup()
    if context is None:
        return False
    owner, backup, frame = context
    allowed = {DB.as_uri() + '?mode=ro', str(backup), backup.as_uri() + '?mode=ro'}
    if owner.epoch not in STORAGE_ATTEMPTS or raw not in allowed:
        return False
    storage_regular(backup)
    RECORDS.append({'event': 'storage-backup-sql', 'epoch': owner.epoch, 'path': raw})
    return True


def publish_storage(stage):
    owner = STORAGE_OWNER
    if owner is None:
        return
    module = sys.modules['persistence.capacity']
    lock = storage_regular(OWNER_LOCK, absent=True)
    identity = [lock.st_dev, lock.st_ino] if lock else None
    fd = owner.fd
    descriptor = os.fstat(fd) if fd is not None else None
    registered = module._OWNERS.get(owner.engine) is owner
    paths = []
    for attempt in STORAGE_ATTEMPTS.values():
        backup = Path(attempt['path'])
        info = storage_regular(backup, absent=True)
        if info is not None and info.st_size > 128 * 1024 * 1024:
            deny('storage-backup-byte-bound')
        paths.append({**attempt, 'exists': info is not None,
                      'bytes': info.st_size if info else None,
                      'sha256': hashlib.sha256(backup.read_bytes()).hexdigest()
                          if info is not None and stage in ('ready', 'closed') else None,
                      'verified_by_successful_lifespan': attempt.get('verified_by_successful_lifespan', False) or stage == 'ready',
                      'sidecars': {suffix: Path(str(backup) + suffix).exists()
                                   for suffix in ('-wal', '-shm', '-journal')}})
    if stage == 'ready':
        for attempt in STORAGE_ATTEMPTS.values():
            attempt['verified_by_successful_lifespan'] = True
        assert registered and fd is not None and owner.ready and owner.admissions_open
        assert descriptor and identity == list(owner.identity) == [descriptor.st_dev, descriptor.st_ino]
        assert len(paths) == 1 and paths[0]['exists'] and not any(paths[0]['sidecars'].values())
    if stage == 'closed':
        assert not registered and fd is None and not owner.ready
        assert not owner.admissions_open and not owner.producers
    if stage == 'ready':
        for backup in paths:
            STORAGE_ATTEMPTS[owner.epoch]['ready_sha256'] = backup['sha256']
    if stage == 'closed':
        for backup in paths:
            assert backup['sha256'] == STORAGE_ATTEMPTS[owner.epoch].get('ready_sha256')
    proc_stat = Path('/proc/self/stat').read_text()
    start_ticks = int(proc_stat[proc_stat.rfind(')') + 2:].split()[19])
    receipt = {'pid': os.getpid(), 'start_ticks': start_ticks, 'epoch': owner.epoch, 'stage': stage,
               'lock': {'path': str(OWNER_LOCK), 'identity': identity,
                        'bytes': lock.st_size if lock else None},
               'owner_fd': fd, 'registered': registered, 'ready': owner.ready,
               'admissions_open': owner.admissions_open, 'producers': len(owner.producers),
               'backups': paths, 'records': [r for r in RECORDS if r['event'].startswith('storage-')]}
    target = OUT / ('storage-owner-' + str(os.getpid()) + '-' + owner.epoch + '.json')
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(receipt, indent=2))
    os.replace(temporary, target)


def startup_media_write(path, flags, producer, data_bytes):
    app = sys.modules.get('main')
    life_function = getattr(app, 'lifespan', None)
    life = storage_frame(life_function.__wrapped__.__code__) if life_function is not None else None
    if life is None:
        return
    if producer.f_code.co_name != 'ensure_placeholder_image':
        deny('startup-noncanonical-placeholder-producer')
    modules = {name: sys.modules.get(name) for name in (
        'decks.bootstrap', 'card_data.hydration', 'card_data.display',
        'card_data.placeholders', 'card_data.fallback_cards', 'decks.expansion_top_decks',
        'persistence.capacity')}
    if any(module is None for module in modules.values()):
        deny('startup-missing-bound-module')
    placeholders, fallback = modules['card_data.placeholders'], modules['card_data.fallback_cards']
    stack = []
    frame = sys._getframe()
    while frame:
        stack.append(frame)
        frame = frame.f_back
    roles = {'life': app.lifespan.__wrapped__, 'producer': placeholders.ensure_placeholder_image,
             'display': modules['card_data.display'].select_display_image_uri,
             'hydrate': modules['card_data.hydration'].hydrate_deck_cards,
             'builtin_bootstrap': modules['decks.bootstrap'].ensure_builtin_decks,
             'expansion_bootstrap': modules['decks.bootstrap'].ensure_expansion_top_decks,
             'builtin_wrapper': app._ensure_builtin_decks, 'expansion_wrapper': app._ensure_expansion_top_decks}
    found = {}
    for name, function in roles.items():
        module = sys.modules[function.__module__]
        if (function.__globals__ is not vars(module)
                or Path(function.__code__.co_filename).resolve() != Path(module.__file__).resolve()):
            deny('startup-function-global-binding')
        found[name] = next((i for i, frame in enumerate(stack)
            if frame.f_code is function.__code__ and frame.f_globals is function.__globals__), None)
    writing = next((i for i, frame in enumerate(stack) if frame.f_code is Path.write_text.__code__), None)
    chain = None
    for branch in ('builtin', 'expansion'):
        indices = [writing, found['producer'], found['display'], found['hydrate'],
                   found[branch + '_bootstrap'], found[branch + '_wrapper'], found['life']]
        if all(i is not None for i in indices) and indices == sorted(set(indices)):
            chain = indices
            break
    if chain is None:
        deny('startup-ordered-actual-frame-chain')
    writer, actual, display, hydrated, bootstrap, wrapper, life = [stack[i] for i in chain]
    owner, repo = life.f_locals.get('owner'), life.f_locals.get('repo')
    capacity = modules['persistence.capacity']
    hydration_repo = hydrated.f_locals.get('repo')
    if (type(owner) is not capacity.DatabaseOwner or owner is not STORAGE_OWNER
            or capacity._OWNERS.get(app.engine) is not owner or owner.engine is not app.engine
            or owner.path != DB or owner.fd is None or owner.admissions_open is not False
            or repo is None or repo is not bootstrap.f_locals.get('repo')
            or repo is not wrapper.f_locals.get('repo') or repo.session.bind is not app.engine
            or not (hydration_repo is repo or getattr(hydration_repo, 'repo', None) is repo)):
        deny('startup-live-owner-closed-admission-repository')
    lock = storage_regular(OWNER_LOCK)
    fd = os.fstat(owner.fd)
    if (lock.st_dev, lock.st_ino) != owner.identity or (fd.st_dev, fd.st_ino) != owner.identity:
        deny('startup-live-owner-fd-identity')
    for relative, expected in STARTUP_MEDIA['source_module_pins'].items():
        if hashlib.sha256((SOURCE / relative).read_bytes()).hexdigest() != expected:
            deny('startup-source-pin')
    structural = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    if (structural(fallback.FALLBACK_CARD_DATA) != STARTUP_MEDIA['seed_cards_structural_sha256']
            or structural(modules['decks.bootstrap'].BUILTIN_DECKS) != STARTUP_MEDIA['builtin_decks_structural_sha256']
            or structural(modules['decks.expansion_top_decks'].EXPANSION_TOP_DECKS) != STARTUP_MEDIA['expansion_decks_structural_sha256']):
        deny('startup-structural-global-pins')
    expected = STARTUP_MEDIA['startup_media'].get(path.name)
    args = actual.f_locals
    name, type_line = args.get('name'), args.get('type_line')
    if (expected is None or type(name) is not str or type(type_line) is not str
            or args.get('token') is not False or display.f_locals.get('token') is not False
            or name != expected['name'] or type_line != expected['type_line']
            or name != hydrated.f_locals.get('name') or name != hydrated.f_locals.get('item', {}).get('card_name')
            or type_line != str(hydrated.f_locals.get('out', {}).get('type_line') or '')
            or display.f_locals.get('name') != name or display.f_locals.get('type_line') != type_line
            or structural(fallback.fallback_card_payload(name)) != expected['seed_row_sha256']):
        deny('startup-canonical-row-characteristics')
    family = placeholders._family(type_line=type_line, token=False)
    filename = 'placeholder-' + family + '-' + placeholders._slug(name, type_line or family) + '.svg'
    content = placeholders._svg_for(family, name=name, type_line=type_line, token=False)
    if (path.parent != MEDIA or path.name != filename or args.get('path') != path
            or writer.f_locals.get('self') != path or writer.f_locals.get('data') != content
            or writer.f_locals.get('encoding') != 'utf-8' or content != expected['content']
            or data_bytes != content.encode('utf-8') or hashlib.sha256(data_bytes).hexdigest() != expected['sha256']
            or flags != os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC
            or path.exists() or path.name in STARTUP_WRITES):
        deny('startup-absent-once-exact-UTF8-flags')
    storage_regular(path, absent=True)
    STARTUP_WRITES[path.name] = expected['sha256']
    RECORDS.append({'event': 'startup-placeholder-prewrite-admitted', 'path': str(path),
                    'epoch': owner.epoch, 'sha256': expected['sha256'],
                    'completion': 'not proven until terminal physical bytes'})


def artifact_write(value, flags=None):
    try:
        raw = Path(os.fspath(value))
        path = raw.resolve()
    except (TypeError, ValueError, OSError):
        deny('unknown-write-path')
    if LEDGER or raw.is_symlink():
        deny('ledger-or-symlink-write')
    if path.is_relative_to(OUT):
        return
    if str(path) in {str(DB) + suffix for suffix in ('', '-journal', '-wal', '-shm')}:
        return
    if storage_open(path, flags):
        return
    frame = sys._getframe()
    producer = None
    while frame:
        if (frame.f_code.co_filename == str(SOURCE / 'backend/card_data/placeholders.py')
                and frame.f_code.co_name in {'ensure_generic_token_image', 'ensure_placeholder_image'}):
            producer = frame
            break
        frame = frame.f_back
    if (path.parent != MEDIA or path.suffix != '.svg' or producer is None
            or not (path.name == 'generic-token-creature.svg' or path.name.startswith('placeholder-'))):
        deny('write-outside-declared-artifacts')
    # Enforce generated SVG bytes at the actual write_text producer, before truncation.
    frame = sys._getframe()
    data = None
    while frame:
        if frame.f_code is Path.write_text.__code__ and isinstance(frame.f_locals.get('self'), Path):
            if frame.f_locals['self'].resolve() == path:
                data = frame.f_locals.get('data')
                break
        frame = frame.f_back
    if path.name == 'generic-token-creature.svg':
        frame = sys._getframe()
        shipped = SOURCE / 'backend/card_data/assets/generic-token-creature.svg'
        while frame:
            if (frame.f_code is shutil.copyfile.__code__
                    and Path(frame.f_locals.get('src', '')).resolve() == shipped
                    and Path(frame.f_locals.get('dst', '')).resolve() == path):
                data = shipped.read_bytes()
                break
            frame = frame.f_back
    data_bytes = data.encode('utf-8') if isinstance(data, str) else data
    if not isinstance(data_bytes, bytes) or len(data_bytes) > 65536:
        deny('undeclared-media-write-or-byte-bound')
    startup_media_write(path, flags, producer, data_bytes)
    MEDIA_PATHS.add(path)
    if len(MEDIA_PATHS) > 512:
        deny('media-count-bound')
    RECORDS.append({'event': 'owned-media-write', 'path': str(path),
                    'bytes': len(data_bytes), 'producer': producer.f_code.co_name})


def audit(event, args):
    if (event == 'open' and len(args) > 2 and isinstance(args[2], int)
            and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
        artifact_write(args[0], args[2])
    elif event == 'os.mkdir':
        if args[2] != -1:
            deny('dir-fd-mkdir')
        path = Path(os.fspath(args[0])).resolve()
        if LEDGER or not (path.is_relative_to(OUT) or path == MEDIA):
            deny('mkdir-outside-declared-artifacts')
    elif event in {'os.remove', 'os.rmdir', 'os.rename'}:
        paths = args[:2] if event == 'os.rename' else args[:1]
        dir_fds = args[2:] if event == 'os.rename' else args[1:]
        if LEDGER or any(fd != -1 for fd in dir_fds):
            deny('ledger-or-dir-fd-path-mutation')
        for value in paths:
            path = Path(os.fspath(value)).resolve()
            if not (path.is_relative_to(OUT)
                    or str(path) in {str(DB) + suffix for suffix in ('-journal', '-wal', '-shm')}
                    or event == 'os.remove' and storage_cleanup(path)):
                deny('path-mutation-outside-declared-artifacts')
    elif event in {'os.symlink', 'os.link', 'os.truncate', 'os.chmod', 'os.chown'}:
        deny('undeclared-path-operation:' + event)
    elif event == 'sqlite3.connect':
        if not in_constructor(GUARDED_CONNECT_CODE):
            deny('sqlite-constructor-outside-return-guard')
        raw = os.fspath(args[0])
        allowed = raw == (f'file:{DB}?mode=ro' if LEDGER else str(DB))
        if not allowed and not LEDGER:
            allowed = storage_sql(raw)
        if not allowed or DB.is_symlink() or DB.resolve() != DB:
            deny(event)
        RECORDS.append({'event': event, 'path': raw, 'role': 'ledger' if LEDGER else 'server'})
    elif event == 'sqlite3.connect/handle':
        if not in_constructor(GUARDED_CONNECT_CODE):
            deny('sqlite-handle-outside-return-guard')
        RECORDS.append({'event': event, 'handle_id': id(args[0])})
    elif event == 'socket.__new__':
        family, kind = args[1:3]
        pipe = family == socket.AF_UNIX and kind == socket.SOCK_STREAM and in_constructor(
            asyncio.selector_events.BaseSelectorEventLoop._make_self_pipe.__code__)
        listener = family == socket.AF_INET and kind == socket.SOCK_STREAM and in_constructor(
            asyncio.base_events.BaseEventLoop.create_server.__code__)
        accepted = family == socket.AF_INET and kind == socket.SOCK_STREAM and accepted_owned_listener()
        if LEDGER or (STARTUP_CANARY and not pipe) or not (pipe or listener or accepted):
            deny(event)
        RECORDS.append({'event': event, 'role': 'self-pipe' if pipe else 'owned-listener' if listener else 'accepted-owned-client'})
    elif event == 'socket.bind':
        if LEDGER or STARTUP_CANARY or args[1] != ('127.0.0.1', PORT):
            deny(event)
    elif event == 'socket.getaddrinfo':
        if LEDGER or STARTUP_CANARY or args[:2] != ('127.0.0.1', PORT):
            deny(event)
    elif event == 'socket.connect' or event in {
            'subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty',
            'os.posix_spawn', 'os.exec', 'pty.spawn'}:
        deny(event)


def verify_storage_pins():
    pins = json.loads((ROOT / 'runner/storage-ABI-pins.json').read_text())
    for relative, item in pins['inputs'].items():
        data = (SOURCE / relative).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item['file_sha256'], relative
        lines = data.decode().splitlines(keepends=True)
        nodes = {}
        for node in ast.parse(data).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nodes[node.name] = node
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        nodes[node.name + '.' + member.name] = member
        for name, expected in item['functions'].items():
            node = nodes[name]
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            body = ''.join(lines[start-1:node.end_lineno]).encode()
            assert hashlib.sha256(body).hexdigest() == expected['sha256'], (relative, name)


# Static candidate pins must be re-reviewed against the eventual published HEAD.
verify_storage_pins()

def guarded_connect(native):
    def authorize(operation, *unused):
        return sqlite3.SQLITE_DENY if operation in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK

    def connect(*args, **kwargs):
        factory = args[5] if len(args) > 5 else kwargs.get('factory', sqlite3.Connection)
        if factory is not sqlite3.Connection:
            deny('sqlite-custom-factory-before-authorizer')
        value = args[0] if args else kwargs.get('database')
        try:
            filename = os.fspath(value)
        except TypeError:
            deny('sqlite-unsupported-path-type')
        if isinstance(filename, str) and filename.startswith('file:'):
            uri = kwargs.get('uri', args[7] if len(args) > 7 else False)
            if uri is not True:
                deny('URI-requires-explicit-uri-True')
        connection = native(*args, **kwargs)
        try:
            connection.set_authorizer(authorize)
        except BaseException:
            connection.close()
            raise
        RECORDS.append({'event': 'sqlite-authorizer-installed', 'handle_id': id(connection)})
        return connection
    return connect


GUARDED_CONNECT_CODE = None
sys.addaudithook(audit)
import sqlite3.dbapi2
import _sqlite3
_SQLITE_ALIASES = (sqlite3, sqlite3.dbapi2, _sqlite3)
_ORIGINAL_CONNECTS = [module.connect for module in _SQLITE_ALIASES]
for _module, _native in zip(_SQLITE_ALIASES, _ORIGINAL_CONNECTS):
    _module.connect = guarded_connect(_native)
    GUARDED_CONNECT_CODE = _module.connect.__code__
if LEDGER:
    mid = sys.argv[2]
    assert re.fullmatch('[a-z0-9-]+', mid)
    connection = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    try:
        row = connection.execute(
            'SELECT state_json, controller_json FROM activematchrecord WHERE id=?', (mid,)).fetchone()
        assert row
        saved = json.loads(row[1])
        decks = {key: {pid: [{'quantity': card['quantity'], 'card_name': card['card_name']}
                            for card in deck] for pid, deck in saved[key].items()}
                 for key in ('mainboards', 'sideboards')}
        print(json.dumps({**decks, 'id': mid, 'state': json.loads(row[0]),
                          'controller': saved,
                          'game_number': saved['game_number'],
                          'controllers': saved['controllers'],
                          'match_complete': saved['match_complete'],
                          'revision': saved['revision'],
                          'state_json_sha256': hashlib.sha256(row[0].encode()).hexdigest(),
                          'controller_json_sha256': hashlib.sha256(row[1].encode()).hexdigest(),
                          'state_SHA256': hashlib.sha256(row[0].encode()).hexdigest(),
                          'controller_SHA256': hashlib.sha256(row[1].encode()).hexdigest()}))
    finally:
        connection.close()
    raise SystemExit(0)

# Denials are intentional pre-import controls, not unexpected application denials.
for label, attempt in [('memory-sql', lambda: sqlite3.connect(':memory:')),
                       ('foreign-sql', lambda: sqlite3.connect(str(ROOT / 'outside.db'))),
                       ('bare-socket', socket.socket)]:
    try:
        attempt()
    except PermissionError:
        CANARIES.append(label)
    else:
        raise AssertionError('Pre-import control escaped: ' + label)
assert len(DENIALS) == 3
DENIALS.clear()
assert not (ROOT / 'outside.db').exists()
sys.path[:0] = [str(SOURCE / 'audit/gate2-domain-compiler'),
               str(SOURCE / 'audit/gate2-march-cost'),
               str(SOURCE / 'audit/gate2-suncleanser'),
               str(SOURCE / 'audit/brainstorm')]
os.environ['ADMISSION_PHASE'] = 'built-owned'
import main
from fastapi import Header, HTTPException
from sqlmodel import Session
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import DATABASE_PATH, engine, init_db
from persistence.repository import Repository
from card_data.sync import ScryfallSyncService
import test_suncleanser_desired as sunc
import test_brainstorm_desired as brain
import test_march_pitch_paid as march
import inventory
from tests import test_archangel_pair_paid_desired as pair
from tests import test_kicker as single

assert DATABASE_PATH == DB and Path(main.__file__).resolve() == SOURCE / 'backend/main.py'
assert os.environ['MTG_TRUSTED_ORIGINS'] == os.environ['MTG_BUILT_PAGE_ORIGIN']
# Preserve the original R9 sourced metadata bootstrap, once for the fresh owned DB.
# Never repeat it during cold restoration or substitute a gameplay effect.
if INITIAL_DATABASE:
    raw_path = SOURCE / 'backend/tests/fixtures/human_transform_audit/canonical.json'
    provenance = json.loads(raw_path.with_name('provenance.json').read_text())
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == provenance['canonical_sha256']
    assert provenance['facts_modified'] is False
    raw = json.loads(raw_path.read_text())['Shock']
    assert raw['id'] == provenance['ids']['Shock']['id']
    assert raw['oracle_id'] == provenance['ids']['Shock']['oracle_id']
    init_db()
    with Session(engine) as session:
        Repository(session).upsert_card(ScryfallSyncService._normalize_payload(raw, None))
    (OUT / 'INITIAL-R9-METADATA.json').write_text(json.dumps({
        'canonical_sha256': provenance['canonical_sha256'],
        'id': raw['id'], 'oracle_id': raw['oracle_id'], 'fresh_DB_only': True,
        'scope': 'unchanged R9 bootstrap metadata; no gameplay mutation'}, indent=2))
PAID_CASES = json.loads((ROOT / 'runner/cohort.json').read_text())
RECOVERY_CASES = json.loads((ROOT / 'runner/recovery-fixtures.json').read_text())
assert len(PAID_CASES) == 40 and len(RECOVERY_CASES) == 2
CASES = {row['id']: row for row in PAID_CASES + RECOVERY_CASES}
assert len(CASES) == 42
FIXTURES = {}
MARCH_FACTS = None


def token(value):
    if value != TOKEN:
        raise HTTPException(403, 'Owned fixture permission required')


def sunc_facts():
    proof = json.loads((sunc.HERE / 'provenance.json').read_text())
    facts = {}
    for name, row in proof['cards'].items():
        raw = json.loads((sunc.HERE / row['file']).read_text())
        assert raw['name'] == name and raw['id'] == row['id']
        assert sunc.digest(raw) == row['canonical_hash']
        facts[name] = raw
    return facts


def make_position(case):
    global MARCH_FACTS
    seat, kind = case['seat'], case['kind']
    if kind == 'sunc':
        facts = sunc_facts()
        state, target = sunc.prepare(facts, seat, case['mode'])
        source = sunc.g.add(state, facts, 'Suncleanser', seat, Zone.HAND)
        state.players[seat].mana_pool = {'C': 1, 'W': 1}
        if case['mode'] == 'creature':
            followup = sunc.g.add(state, facts, 'Battlegrowth', seat, Zone.HAND)
            state.players[seat].mana_pool['G'] = 1
        else:
            followup = None
        meta = {'source': source, 'target': target, 'followup': followup,
                'name': 'Suncleanser', 'original_counter': sunc.count(state, case['mode'], target)}
    elif kind == 'brain':
        state = brain.position(seat)
        brain.add(state, 'Counterspell', seat, Zone.HAND)
        source = brain.add(state, 'Brainstorm', seat, Zone.HAND)
        state.players[seat].mana_pool = {'U': 1}
        meta = {'source': source, 'name': 'Brainstorm'}
    elif kind == 'march':
        if MARCH_FACTS is None:
            seed, selected, proof = inventory.load_inputs()
            MARCH_FACTS = {name: selected[row['scryfall_id']] for name, row in seed.items()}
            (OUT / ('canonical-input-' + str(os.getpid()) + '.json')).write_text(json.dumps(proof, indent=2))
        amount = {'empty': 0, 'one': 1, 'two-reverse-click': 2}[case['pitch']]
        state, action, whites, red, foreign = march.setup(MARCH_FACTS, seat, 4, amount)
        meta = {'source': action['card_id'], 'target': action['targets']['target_card_id'],
                'name': march.MARCH, 'whites': whites, 'red': red, 'foreign': foreign,
                'pitch_count': amount, 'mana_spent': max(0, 4-2*amount)+1}
    elif kind == 'pair':
        state, source = pair.setup(seat)
        state.players[seat].mana_pool = {'C': 2, 'W': 2, 'B': 1, 'R': 1}
        meta = {'source': source, 'name': 'Archangel of Wrath',
                'count': next(row[1] for row in pair.CHOICES if row[0] == case['choice'])}
    else:
        assert kind == 'single'
        state, source, target = single.setup('Shivan Fire', seat)
        meta = {'source': source.id, 'target': target.id, 'name': 'Shivan Fire',
                'mana_spent': 5 if case['choice'] == 'kicker' else 1}
    # Declared ordinary non-snow starting positions, not a mutation after payment.
    for player in state.players.values():
        player.snow_mana_pool.clear()
    return state, meta


@main.app.post('/__built__/setup/{case_id}')
def setup(case_id: str, x_owned_test_token: str = Header(default='')):
    token(x_owned_test_token)
    consumed_path = OUT / 'consumed-fixtures.json'
    consumed = json.loads(consumed_path.read_text()) if consumed_path.exists() else []
    if case_id not in CASES or case_id in consumed:
        raise HTTPException(409, 'Unknown or consumed fixture')
    case = CASES[case_id]
    state, meta = make_position(case)
    deck = [{'quantity': 60, 'card_name': 'Forest'}]
    archetype = main.guess_archetype(deck)
    ai = {pid: main.AIAgent(difficulty='master', archetype=archetype,
                           opponent_archetype=archetype) for pid in (1, 2)}
    match = main.MatchController(state=state, rules=sunc.g.RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai=ai, mode='human_vs_human',
        deck_ids=(None, None), mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = match
    with Session(engine) as session:
        main._persist_active_match(Repository(session), match)
    result = {'id': state.id, 'case': case, **meta}
    FIXTURES[case_id] = result
    consumed.append(case_id)
    consumed_path.write_text(json.dumps(consumed))
    (OUT / ('fixture-' + case_id + '.json')).write_text(json.dumps({
        'declared_start_only': True, 'metadata': result,
        'initial': serialize_match_snapshot(state)}, indent=2))
    return result


@main.app.get('/__built__/snapshot/{mid}')
def snapshot(mid: str, x_owned_test_token: str = Header(default='')):
    token(x_owned_test_token)
    with Session(engine) as session:
        match = main._load_saved_match(mid, Repository(session))
    if match is None:
        raise HTTPException(404, 'Unknown owned match')
    with match.mutation_lock:
        owner = main.owner_for_engine(main.engine)
        assert owner is STORAGE_OWNER and owner.path == DB and owner.pid == os.getpid()
        state = serialize_match_snapshot(match.state)
        controller = main._controller_snapshot(match)
        connection = sqlite3.connect(str(DB))
        try:
            sql = list(connection.iterdump())
            capacity_rows = connection.execute('SELECT * FROM resourcecapacity').fetchall()
            columns = [row[1] for row in connection.execute('PRAGMA table_info(resourcecapacity)')]
        finally:
            connection.close()
        assert columns == ['id', 'version', 'durable_bytes', 'snapshot_rows',
                           'reserved_bytes', 'reserved_snapshot_rows', 'owner_epoch']
        assert len(capacity_rows) == 1 and capacity_rows[0][-1] == owner.epoch
        receipt = json.loads((OUT / ('storage-owner-' + str(owner.pid) + '-' + owner.epoch + '.json')).read_text())
        assert receipt['stage'] == 'ready' and receipt['epoch'] == owner.epoch
        assert receipt['pid'] == owner.pid and receipt['registered'] and receipt['ready']
        assert receipt['owner_fd'] == owner.fd and receipt['lock']['identity'] == list(owner.identity)
        result = {'state': state, 'controller': controller, 'SQL': sql}
        snapshot_sha = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        proof = {'snapshot': result, 'owner': receipt, 'database': str(DB),
                 'columns': columns, 'capacity_row': capacity_rows[0]}
        (OUT / ('snapshot-owner-' + owner.epoch + '-' + snapshot_sha + '.json')).write_text(json.dumps(proof))
    return result


def raw_resources():
    fds = {}
    for path in Path('/proc/self/fd').iterdir():
        try:
            fds[path.name] = os.readlink(path)
        except FileNotFoundError:
            pass
    return {'fds': fds,
            'threads': [{'name': thread.name, 'ident': thread.ident,
                         'native_id': thread.native_id, 'daemon': thread.daemon}
                        for thread in threading.enumerate()],
            'kernel_tasks': sorted(path.name for path in Path('/proc/self/task').iterdir()),
            'direct_children': Path('/proc/self/task/' + str(os.getpid()) + '/children').read_text()}


class OwnedRealApp:
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            completed = False
            before = raw_resources()

            async def observe(message):
                nonlocal completed
                if message['type'] == 'lifespan.startup.complete':
                    publish_storage('ready')
                await send(message)
                if message['type'] == 'lifespan.shutdown.complete':
                    completed = True
            try:
                await main.app(scope, receive, observe)
            finally:
                if STORAGE_OWNER is not None:
                    publish_storage('closed' if completed and STORAGE_OWNER.fd is None
                                    else 'shutdown-unproven')
                status = engine.pool.status()
                (OUT / ('server-closure-' + str(os.getpid()) + '.json')).write_text(json.dumps({
                    'pid': os.getpid(), 'canaries': CANARIES, 'denials': DENIALS,
                    'jobs': {k: v.get('status') for k, v in main.SIM_JOBS.items()},
                    'workers_empty': not main.SIM_JOB_WORKERS,
                    'shutdown_admission_closed': main.SIM_SHUTTING_DOWN,
                    'shutdown_complete': completed, 'pool_status': status,
                    'raw_before': before, 'raw_after': raw_resources(),
                    'resource_boundary': 'raw lifespan observations; final process/thread closure independently required',
                    'zero_checkouts': engine.pool.checkedout() == 0,
                    'ordinary_pool_disposed': 'Connections in pool: 0' in status,
                    'no_emergency_dispose': True, 'records': RECORDS}, indent=2))
        elif scope['type'] == 'http':
            method, path = scope['method'], scope['path']
            get = (path in {'/health', '/cards/completeness', '/decks', '/decks/builtin',
                            '/decks/expansion-top', '/decks/completeness', '/matches'}
                   or path == '/diagnostics/runs' and scope.get('query_string') == b'limit=20'
                   or re.fullmatch(r'/decks/\d+/card-completeness', path)
                   or re.fullmatch(r'/matches/[a-z0-9-]+(?:/legal-moves)?', path)
                   or re.fullmatch(r'/__built__/snapshot/[a-z0-9-]+', path)
                   or path.startswith('/card-images/'))
            post = (path in {'/decks/import', '/simulate/batch/preflight', '/matches/start'}
                    or re.fullmatch(r'/matches/[a-z0-9-]+/(action|sideboard|next-game)', path)
                    or path in {'/__built__/setup/' + case_id for case_id in CASES})
            if path.endswith('/autoplay') and method == 'POST':
                post = scope.get('query_string') == b'ticks=1'
            allowed = method == 'OPTIONS' or method == 'GET' and get or method == 'POST' and post
            if not allowed:
                deny('undeclared-http-route:' + method + ':' + path)
            # Genuine main middleware, including Origin validation, still handles each request.
            await main.app(scope, receive, send)
        else:
            deny('undeclared-asgi-scope:' + scope['type'])


app = OwnedRealApp()
