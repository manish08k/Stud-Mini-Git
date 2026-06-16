import contextlib
import os
import sys
import time
from pathlib import Path
from typing import Optional

from .exceptions import LockTimeoutError

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class FileLock:
    """Cross-platform exclusive file lock backed by a lock file."""

    def __init__(self, path: Path, timeout: Optional[float] = 10.0, poll_interval: float = 0.05):
        self.path = Path(path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._fd: Optional[int] = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()

        while True:
            fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR)
            try:
                self._lock_fd(fd)
                self._fd = fd
                os.ftruncate(fd, 0)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                return
            except (BlockingIOError, OSError):
                os.close(fd)
                if self.timeout is not None and (time.monotonic() - start) >= self.timeout:
                    raise LockTimeoutError(f"timed out acquiring lock: {self.path}")
                time.sleep(self.poll_interval)

    def _lock_fd(self, fd: int) -> None:
        if sys.platform == "win32":
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_fd(self, fd: int) -> None:
        if sys.platform == "win32":
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            self._unlock_fd(self._fd)
        finally:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    @property
    def locked(self) -> bool:
        return self._fd is not None


class LockManager:
    """Manages named locks under a lock directory."""

    def __init__(self, lock_dir: Path):
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def lock(self, name: str, timeout: Optional[float] = 10.0) -> FileLock:
        return FileLock(self.lock_dir / f"{name}.lock", timeout=timeout)

    @contextlib.contextmanager
    def acquire(self, name: str, timeout: Optional[float] = 10.0):
        lk = self.lock(name, timeout=timeout)
        try:
            lk.acquire()
            yield lk
        finally:
            lk.release()
