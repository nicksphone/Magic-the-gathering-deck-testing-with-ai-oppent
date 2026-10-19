"""Archive only a declared, closed module fixture lifetime before releasing it."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import tarfile


def _canonical(value):
    path = Path(value)
    if (not path.is_absolute() or path.resolve() != path or not path.is_dir()
            or any(part.is_symlink() for part in (path, *path.parents))):
        raise RuntimeError('HTTP_RUNTIME_ROOT_NOT_CANONICAL')
    return path


def _inventory(roots):
    result = {}
    for label, root in roots.items():
        nodes = {}
        pending = [root]
        while pending:
            path = pending.pop()
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                kind, digest = 'directory', None
                pending.extend(path.iterdir())
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                kind = 'file'
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            else:
                raise RuntimeError('HTTP_RUNTIME_UNSUPPORTED_MEMBER')
            nodes[path.relative_to(root).as_posix()] = [kind, info.st_dev, info.st_ino,
                info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns, digest]
        result[label] = nodes
    return result


def _verify_archive(archive, roots, inventory):
    expected = {label if name == '.' else label + '/' + name: (label, name, facts)
                for label, nodes in inventory.items() for name, facts in nodes.items()}
    manifest = json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()
    with tarfile.open(archive, 'r:gz') as tar:
        seen = set()
        for member in tar:
            name = member.name
            if name in seen:
                raise RuntimeError('HTTP_RUNTIME_ARCHIVE_DUPLICATE')
            seen.add(name)
            if name == 'OWNED_INVENTORY.json':
                if not member.isfile() or tar.extractfile(member).read() != manifest:
                    raise RuntimeError('HTTP_RUNTIME_ARCHIVE_MANIFEST')
                continue
            if name not in expected:
                raise RuntimeError('HTTP_RUNTIME_ARCHIVE_FOREIGN_MEMBER')
            label, relative, facts = expected[name]
            if facts[0] == 'directory':
                if not member.isdir():
                    raise RuntimeError('HTTP_RUNTIME_ARCHIVE_KIND')
                continue
            if not member.isfile() or member.size != facts[4]:
                raise RuntimeError('HTTP_RUNTIME_ARCHIVE_KIND')
            with tar.extractfile(member) as archived, (roots[label] / relative).open('rb') as original:
                while True:
                    a, b = archived.read(1024 * 1024), original.read(1024 * 1024)
                    if a != b:
                        raise RuntimeError('HTTP_RUNTIME_ARCHIVE_BYTES')
                    if not a:
                        break
        if seen != expected.keys() | {'OWNED_INVENTORY.json'}:
            raise RuntimeError('HTTP_RUNTIME_ARCHIVE_MISSING_MEMBER')


def _archive_pin(path):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise RuntimeError('HTTP_RUNTIME_CHANGED')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    fields = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    if fields(before) != fields(opened) or fields(before) != fields(path.lstat()):
        raise RuntimeError('HTTP_RUNTIME_CHANGED')
    return fields(before), digest


def archive_closed_http_runtime(server, *, runtime, data, evidence_root):
    """No discovery or cleanup at restart: caller has already ended the scope."""
    runtime, evidence = _canonical(runtime), _canonical(evidence_root)
    if runtime != server.root or (runtime / '.git').exists():
        raise RuntimeError('HTTP_RUNTIME_FOREIGN_ROOT')
    if (runtime / '.private-choice-owned').read_text() != server.token:
        raise RuntimeError('HTTP_RUNTIME_OWNER_MISMATCH')
    roots = {'runtime': runtime}
    if data is not None:
        data = _canonical(data)
        if data != server.data or data != runtime.parent / 'cold-restart-data' / runtime.name:
            raise RuntimeError('HTTP_RUNTIME_FOREIGN_DATA')
        roots['data'] = data
    elif hasattr(server, 'data'):
        raise RuntimeError('HTTP_RUNTIME_DATA_REQUIRED')
    if any(evidence.is_relative_to(root) or root.is_relative_to(evidence) for root in roots.values()):
        raise RuntimeError('HTTP_RUNTIME_ARCHIVE_ROOT_OVERLAP')
    proc = server.proc
    code = proc.poll() if proc is not None else None
    if type(code) is not int or code not in (0, -signal.SIGTERM) or proc.wait(timeout=0) != code:
        raise RuntimeError('HTTP_RUNTIME_NOT_CLOSED')
    if data is not None:
        try:
            row = json.loads((data / f'closure-{proc.pid}.json').read_text())
        except (FileNotFoundError, ValueError) as exc:
            raise RuntimeError('HTTP_RUNTIME_CLOSURE_RECEIPT') from exc
        if any(type(row.get(key)) is not int or row[key] != value for key, value in
               {'pid': proc.pid, 'registered_owners': 0, 'pool_checkedout': 0}.items()):
            raise RuntimeError('HTTP_RUNTIME_CLOSURE_RECEIPT')
    inventory = _inventory(roots)
    parent = evidence / 'closed-http-runtime'
    parent.mkdir(mode=0o700, exist_ok=True)
    _canonical(parent)
    destination = parent / runtime.name
    destination.mkdir(mode=0o700)
    archive = destination / 'private-runtime.tar.gz'
    manifest = json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()
    with archive.open('xb') as stream:
        os.chmod(archive, 0o600)
        with tarfile.open(fileobj=stream, mode='w:gz') as tar:
            for label, root in roots.items():
                tar.add(root, arcname=label)
            member = tarfile.TarInfo('OWNED_INVENTORY.json')
            member.size = len(manifest)
            member.mode = 0o600
            tar.addfile(member, io.BytesIO(manifest))
    archive_pin = _archive_pin(archive)
    _verify_archive(archive, roots, inventory)
    if _inventory(roots) != inventory or _archive_pin(archive) != archive_pin:
        raise RuntimeError('HTTP_RUNTIME_CHANGED')
    receipt = {'archive': str(archive), 'archive_sha256': archive_pin[1],
               'byte_member_inode_verified': True,
               'closure_kind': 'native-owner-and-process' if data is not None else 'terminal-process',
               'roots': {label: str(root) for label, root in roots.items()},
               'original_root_inodes': {label: inventory[label]['.'][1:3] for label in roots},
               'members': sum(len(nodes) for nodes in inventory.values())}
    receipt_path = destination / 'VERIFIED.json'
    receipt_path.write_text(json.dumps(receipt, sort_keys=True) + '\n')
    if (json.loads(receipt_path.read_text()) != receipt or _inventory(roots) != inventory
            or _archive_pin(archive) != archive_pin):
        raise RuntimeError('HTTP_RUNTIME_CHANGED')
    # All declared trees are closed and proved before the first removal begins.
    for root in roots.values():
        shutil.rmtree(root)
    return receipt
