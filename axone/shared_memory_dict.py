import logging
import os
import sys
from contextlib import contextmanager
from functools import wraps
from multiprocessing import resource_tracker
from multiprocessing.shared_memory import SharedMemory
from typing import (
    Any,
    Dict,
    Generator,
    ItemsView,
    Iterator,
    KeysView,
    Optional,
    ValuesView,
)

from filelock import FileLock as Lock

from .serializers import (
    NULL_BYTE,
    DeserializationError,
    JSONSerializer,
    SharedMemoryDictSerializer,
)

NOT_GIVEN = object()
DEFAULT_SERIALIZER = JSONSerializer()

logger = logging.getLogger(__name__)


def lock(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Note regarding the use of self in the decorator:
        # Decorator is applied when the function is defined, which is at class
        # creation time, not at instance creation time. To use an instance
        # variable in a decorator, a decorator that can take self as an
        # argument can be used even if self is not used in the function.
        # print("Using this lock:", self._lock.lock_file)
        with self._lock:  # noqa
            return func(self, *args, **kwargs)

    return wrapper


class SharedMemoryDict:
    _lock = None

    def __init__(
        self,
        name: str,
        size: int,
        *,
        serializer: SharedMemoryDictSerializer = DEFAULT_SERIALIZER,
    ) -> None:
        super().__init__()
        self._serializer = serializer

        # Create lock matching shared memory name
        # This is to prevent multiple processes from accessing the same
        # lock if they access different shared memory at the same time
        self._lock = Lock(
            os.path.join(
                os.path.expanduser("~"),
                f"{name}.axone.lock",
            )
        )

        # Create shared memory block
        self._memory_block = self._get_or_create_memory_block(
            f"sm_{name}", size
        )
        self._ensure_memory_initialization()
        self._size = 0

    @property
    def size(self) -> int:
        return self._size

    def _ensure_memory_initialization(self):
        memory_is_not_empty = (
            bytes(self._memory_block.buf).split(NULL_BYTE, 1)[0] == b""
        )
        if memory_is_not_empty:
            self._save_memory({})

    def cleanup(self) -> None:
        if not hasattr(self, "_memory_block"):
            return
        self._memory_block.close()

    @lock
    def clear(self) -> None:
        self._save_memory({})

    def popitem(self) -> Any:
        with self._modify_db() as db:
            return db.popitem()

    @contextmanager
    @lock
    def _modify_db(self) -> Generator:
        db = self._read_memory()
        yield db
        self._save_memory(db)

    @lock
    def modify_structure(self, key_list, new_value):
        """Modify the structure of the shared memory object given a list of keys"""
        db = self._read_memory()

        temp = db
        for key in key_list[:-1]:
            if key not in temp:
                return
            temp = temp[key]
        temp[key_list[-1]] = new_value

        self._save_memory(db)

    @lock
    def process_lambda(self, func, *args):
        """Process a lambda function on the shared memory
        The function must alter the object db in-place and either return
        nothing or return a value that this function will return in turn.
        """
        db = self._read_memory()
        ans = func(db, *args)
        self._save_memory(db)
        return ans

    def __getitem__(self, key: str) -> Any:
        return self._read_memory()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        with self._modify_db() as db:
            db[key] = value

    def __len__(self) -> int:
        return len(self._read_memory())

    def __delitem__(self, key: str) -> None:
        with self._modify_db() as db:
            del db[key]

    def __iter__(self) -> Iterator:
        return iter(self._read_memory())

    def __reversed__(self):
        return reversed(self._read_memory())

    def __del__(self) -> None:
        self.cleanup()

    def __contains__(self, key: str) -> bool:
        return key in self._read_memory()

    def __eq__(self, other: Any) -> bool:
        return self._read_memory() == other

    def __ne__(self, other: Any) -> bool:
        return self._read_memory() != other

    if sys.version_info > (3, 8):

        def __or__(self, other: Any) -> Any:
            return self._read_memory() | other

        def __ror__(self, other: Any) -> Any:
            return other | self._read_memory()

        def __ior__(self, other: Any) -> Any:
            with self._modify_db() as db:
                db |= other
                return db

    def __str__(self) -> str:
        return str(self._read_memory())

    def __repr__(self) -> str:
        return repr(self._read_memory())

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self._read_memory().get(key, default)

    def keys(self) -> KeysView[Any]:
        return self._read_memory().keys()

    def values(self) -> ValuesView[Any]:
        return self._read_memory().values()

    def items(self) -> ItemsView:
        return self._read_memory().items()

    def pop(self, key: str, default: Optional[Any] = NOT_GIVEN):
        with self._modify_db() as db:
            if default is NOT_GIVEN:
                return db.pop(key)
            return db.pop(key, default)

    def update(self, other=(), /, **kwds):
        with self._modify_db() as db:
            db.update(other, **kwds)

    def setdefault(self, key: str, default: Optional[Any] = None):
        with self._modify_db() as db:
            return db.setdefault(key, default)

    def _remove_shm_from_resource_tracker(self, name: str) -> None:
        """
        Overwrite the register and unregister functions of the resource_tracker
        to avoid registering the shared memory block with the resource_tracker

        Calls unregister to avoid resource_tracker.py from cleaning up
        the shared memory block when this process exits
        This is necessary because the shared memory block is not
        created by the resource_tracker.py itself but by the
        SharedMemoryDict class

        Important note: This intentionally cause memory leaks when the last
        process is killed without calling cleanup().
        This is required on linux system otherwise, the memory will get cleaned
        regardless if other processes are still using it or not.

        More details at: https://bugs.python.org/issue38119
                         https://stackoverflow.com/a/73885467
        """

        # TODO: Implementing our own resource_tracker.py would be better
        # TODO: than overwriting the functions. We need to clean both the
        # TODO: shared_memory and the lock as well.

        def fix_register(name, rtype):
            if rtype == "shared_memory":
                return
            return resource_tracker._resource_tracker.register(
                self, name, rtype
            )

        resource_tracker.register = fix_register

        def fix_unregister(name, rtype):
            if rtype == "shared_memory":
                return
            return resource_tracker._resource_tracker.unregister(
                self, name, rtype
            )

        resource_tracker.unregister = fix_unregister

        if "shared_memory" in resource_tracker._CLEANUP_FUNCS:
            del resource_tracker._CLEANUP_FUNCS["shared_memory"]

    def _get_or_create_memory_block(
        self, name: str, size: int
    ) -> SharedMemory:
        """Get or create shared memory block"""

        self._remove_shm_from_resource_tracker(name)
        try:
            self.check_security(name)
            return SharedMemory(name=name)
        except FileNotFoundError:
            return SharedMemory(name=name, create=True, size=size)

    def check_security(self, name: str) -> None:
        """Check if shared memory belongs to and is only read+writeable
        for the current user"""
        if os.name == "nt":
            return

        if "/" in name:
            raise TypeError('Name must not contain "/".')

        shm_file = os.path.join("/dev/shm", name)
        stat = os.stat(shm_file)
        if (
            stat.st_uid != os.getuid()
            or stat.st_gid != os.getgid()
            or stat.st_mode != 0o100600
        ):
            os.unlink(shm_file)

    def _save_memory(self, db: Dict[str, Any]) -> None:
        data = self._serializer.dumps(db)
        self._size = len(data)
        try:
            self._memory_block.buf[: len(data)] = data
        except ValueError as exc:
            raise ValueError(
                f"exceeds available storage {self._size} > {self._memory_block._size}"
            ) from exc

    def _read_memory(self) -> Dict[str, Any]:
        try:
            return self._serializer.loads(self._memory_block.buf.tobytes())
        except DeserializationError:
            logger.exception("Failed to deserialize shared memory")
            # Reset memory
            self._save_memory({})
            return {}

    @property
    def shm(self) -> SharedMemory:
        return self._memory_block
