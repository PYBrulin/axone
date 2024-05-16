import logging
import os
from functools import wraps
from multiprocessing import resource_tracker
from multiprocessing.shared_memory import SharedMemory
from typing import Any, Dict, Optional

from axone.axone_struct import AxoneStruct
from axone.custom_logger import setup_logger

NOT_GIVEN = object()

logger = logging.getLogger(__name__)


def lock(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs) -> Any:
        # Note regarding the use of self in the decorator:
        # Decorator is applied when the function is defined, which is at class
        # creation time, not at instance creation time. To use an instance
        # variable in a decorator, a decorator that can take self as an
        # argument can be used even if self is not used in the function.
        # print("Using this lock:", self._lock.lock_file)
        with self._lock:  # noqa
            return func(self, *args, **kwargs)

    return wrapper


class AxoneSharedMemory:
    _lock = None

    def __init__(
        self,
        name: str,
        struct: Optional[AxoneStruct] = AxoneStruct(),
        size: Optional[int] = None,
        centralized: bool = False,
    ) -> None:
        super().__init__()

        # # Create lock matching shared memory name
        # # This is to prevent multiple processes from accessing the same
        # # lock if they access different shared memory at the same time
        # self._lock = Lock(
        #     os.path.join(
        #         os.path.expanduser("~"),
        #         f".{name}.axone.lock",
        #     )
        # )

        # Use the provided struct as itself
        self._struct = struct

        # Create shared memory block
        self._memory_block = self._get_or_create_memory_block(f"axn_{name}", size, centralized)
        self._ensure_memory_initialization()
        self._size = 0

    @property
    def _shm(self) -> SharedMemory:
        return self._memory_block

    def _ensure_memory_initialization(self) -> None:
        memory_is_not_empty = bytes(self._memory_block.buf) == b""
        if memory_is_not_empty:
            self._save_memory({})

    def _remove_shm_from_resource_tracker(self, name: str) -> None:
        """
        Overwrite the register and unregister functions of the resource_tracker
        to avoid registering the shared memory block with the resource_tracker

        Calls unregister to avoid resource_tracker.py from cleaning up
        the shared memory block when this process exits
        This is necessary because the shared memory block is not
        created by the resource_tracker.py itself but by the
        AxoneShaedMemory class

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

        def fix_register(name, rtype) -> Any | None:
            if rtype == "shared_memory":
                return
            return resource_tracker._resource_tracker.register(self, name, rtype)

        resource_tracker.register = fix_register

        def fix_unregister(name, rtype) -> Any | None:
            if rtype == "shared_memory":
                return
            return resource_tracker._resource_tracker.unregister(self, name, rtype)

        resource_tracker.unregister = fix_unregister

        if "shared_memory" in resource_tracker._CLEANUP_FUNCS:
            del resource_tracker._CLEANUP_FUNCS["shared_memory"]

    def _check_security(self, name: str) -> None:
        """Check if shared memory belongs to and is only read+writeable
        for the current user"""
        if os.name == "nt":
            return

        if "/" in name:
            raise TypeError('Name must not contain "/".')

        shm_file = os.path.join("/dev/shm", name)
        stat = os.stat(shm_file)
        if stat.st_uid != os.getuid() or stat.st_gid != os.getgid() or stat.st_mode != 0o100600:
            os.unlink(shm_file)

    def _get_or_create_memory_block(self, name: str, size: Optional[int], centralized: bool = False) -> SharedMemory:
        """Get or create shared memory block"""
        if centralized:
            self._remove_shm_from_resource_tracker(name)

        try:
            self._check_security(name)
            return SharedMemory(name=name)
        except FileNotFoundError:
            return SharedMemory(
                name=name,
                create=True,
                size=size if size is not None else 0,
            )

    def cleanup(self) -> None:
        if not hasattr(self, "_memory_block"):
            return
        self._memory_block.close()

    # @lock
    # def clear(self) -> None:
    #     self._save_memory({})

    # def popitem(self) -> Any:
    #     with self._modify_db() as db:
    #         return db.popitem()

    # @contextmanager
    # @lock
    # def _modify_db(self) -> Generator:
    #     db = self._read_memory()
    #     yield db
    #     self._save_memory(db)

    # @lock
    # def modify_structure(self, key_list, new_value) -> None:
    #     """Modify the structure of the shared memory object given a list of keys"""
    #     db = self._read_memory()

    #     temp = db
    #     for key in key_list[:-1]:
    #         if key not in temp:
    #             return
    #         temp = temp[key]
    #     temp[key_list[-1]] = new_value

    #     self._save_memory(db)

    # @lock
    # def process_lambda(self, func, *args) -> Any:
    #     """Process a lambda function on the shared memory
    #     The function must alter the object db in-place and either return
    #     nothing or return a value that this function will return in turn.
    #     """
    #     db = self._read_memory()
    #     ans = func(db, *args)
    #     self._save_memory(db)
    #     return ans

    @property
    def struct(self) -> AxoneStruct:
        self._read_memory()
        return self._struct

    def __getitem__(self, key: str) -> Any:
        return self.struct.get(key, None)

    def __setitem__(self, key: str, value: Any) -> None:
        logging.debug(f"Setting '{key}' to '{value}'")
        setattr(self._struct.__class__, key, value)
        self._save_memory()

    def __str__(self) -> str:
        return str(self.struct)

    def __repr__(self) -> str:
        return repr(self.struct)

    def __contains__(self, key: str) -> bool:
        return key in self.struct.__class__

    def _save_memory(self) -> None:
        data = self._struct.encode()
        if len(data) > self._memory_block._size:
            raise ValueError(f"exceeds available storage {len(data)} > {self._memory_block._size}")
        try:
            self._memory_block.buf[: len(data)] = data
            self._memory_block.buf[len(data) :] = b"\0" * (self._memory_block._size - len(data))
            logging.debug(f"Saved {len(data)} bytes to shared memory")
        except ValueError as exc:
            raise ValueError(f"exceeds available storage {self._size} > {self._memory_block._size}") from exc

    def _read_memory(self) -> Dict[str, Any]:
        try:
            return self._struct.decode(self._memory_block.buf.tobytes())
        except Exception:
            logger.exception("Failed to deserialize shared memory")
            # Reset memory
            self._save_memory({})
            return {}


if __name__ == "__main__":
    setup_logger(debug=True)

    asm = AxoneSharedMemory("test", AxoneStruct(), 1000, False)
    print(asm._memory_block)
    asm["testattr"] = "rtyuio"

    asm._struct.list_all_attrs()

    print(asm["testattr"])
