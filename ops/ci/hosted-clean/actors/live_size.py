"""Logical-byte metrics only. No link following, deletion or ownership authority."""
import os
from pathlib import Path
import stat


def directory_identity(value):
    assert stat.S_ISDIR(value.st_mode) and value.st_uid == os.getuid()
    return value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid


def live_size(root, *, live=False):
    root = Path(root)
    assert root.is_absolute() and root.resolve(strict=True) == root
    original = root.lstat()
    expected = directory_identity(original)

    def metadata(value):
        return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
                value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

    def walk(fd, identity):
        before = os.fstat(fd)
        assert directory_identity(before) == identity
        total = 0
        with os.scandir(fd) as entries:
            for entry in entries:
                # Cached type identifies an enumerated entry; it grants no follow/delete authority.
                kind = (stat.S_IFREG if entry.is_file(follow_symlinks=False) else
                        stat.S_IFDIR if entry.is_dir(follow_symlinks=False) else
                        stat.S_IFLNK if entry.is_symlink() else None)
                try:
                    value = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    assert directory_identity(os.fstat(fd)) == identity
                    if live and kind is not None:
                        continue
                    raise
                assert kind is not None and stat.S_IFMT(value.st_mode) == kind
                if not live:
                    assert entry.inode() == value.st_ino
                if stat.S_ISREG(value.st_mode):
                    assert value.st_uid == os.getuid()
                    total += value.st_size  # Charge every pathname, including hardlinks/recreated leaves.
                elif stat.S_ISDIR(value.st_mode):
                    child_identity = directory_identity(value)
                    try:
                        child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                    except FileNotFoundError:
                        assert directory_identity(os.fstat(fd)) == identity
                        if live:
                            continue
                        raise
                    try:
                        total += walk(child, child_identity)
                        try:
                            after = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                        except FileNotFoundError:
                            assert directory_identity(os.fstat(fd)) == identity
                            assert directory_identity(os.fstat(child)) == child_identity
                            if not live:
                                raise
                        else:
                            assert directory_identity(after) == child_identity
                            if not live:
                                assert metadata(after) == metadata(value)
                    finally:
                        os.close(child)
                if not live and not stat.S_ISDIR(value.st_mode):
                    assert metadata(os.stat(entry.name, dir_fd=fd, follow_symlinks=False)) == metadata(value)
        assert directory_identity(os.fstat(fd)) == identity
        if not live:
            assert metadata(os.fstat(fd)) == metadata(before)
        return total

    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        total = walk(fd, expected)
        assert directory_identity(root.lstat()) == expected
        if not live:
            assert metadata(root.lstat()) == metadata(original)
        return total
    finally:
        os.close(fd)
