import logging
import time
from multiprocessing.shared_memory import SharedMemory
from typing import Any, Callable, List

from axone.axone_struct import AxoneStruct
from axone.utils import generate_uuid


class Subscription:
    def __init__(
        self,
        topic_name: str = "",
        rate: float = 1.0,
    ) -> None:
        self._name: str = topic_name
        self._rate: float = rate
        self._last_update: float = 0
        self._last_fetch: float = 0

        self._topic = AxoneStruct()

        self._callbacks = []

        self._uuid = generate_uuid(topic_name)

        # Connect to the shared memory of the topic
        try:
            self._memory = SharedMemory(
                name=self._uuid,
                create=False,
            )
        except FileNotFoundError:
            logging.error(f"Shared memory {self._uuid} not found")
            self._memory = None

        # TODO : Implement unlink, close, etc for the SHM

    @property
    def topic(self) -> str:
        """The string representation of the topic"""
        return str(self._topic)

    @property
    def name(self) -> str:
        """The topic name of the publisher"""
        return self._name

    @property
    def rate(self) -> float:
        """The rate at which the topic is subscribed"""
        return self._rate

    @property
    def last_update(self) -> float:
        """The timestamp of the last update of the topic"""
        return self._last_update

    @property
    def last_fetch(self) -> float:
        return self._last_fetch

    @property
    def callbacks(self) -> List[Callable]:
        """The list of callbacks to call when a new message is received"""
        return self._callbacks

    def call(self, topic_struct) -> None:
        for callback in self._callbacks:
            callback(topic_struct)

    def subscribe(self) -> Any:
        """Get the latest message from the topic"""
        self._last_fetch = time.time()

        # Check that the memory is not empty
        if self._memory is None:
            return None
        if self._memory.buf is None:
            return None

        # Get the message from the shared memory
        encoded = bytes(self._memory.buf[:])

        self._topic.decode(encoded)

        self._last_update = self._topic.timestamp_  # This comes from the topic itself
        self._rate = self._topic.rate_  # This comes from the topic itself

        # Note: Calling the callbacks is done in the main loop not here
