import logging
import time
from multiprocessing.shared_memory import SharedMemory
from typing import Any, Callable, List

from axone.axone_struct import AxoneStruct
from axone.utils import generate_uuid, timeit_if_debug


class Subscription:
    def __init__(
        self,
        topic_name: str = "",
        rate: float = 1.0,
    ) -> None:
        self._name: str = topic_name
        self._request_rate: float = rate
        self._topic_rate: float = None
        self._timestamp: float = 0
        self._last_timestamp: float = 0

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
        """The rate at which the topic should be subscribed"""
        return (
            self._request_rate
            if (self._request_rate is not None and self._topic_rate is None)
            else (self._request_rate if (self._request_rate > self._topic_rate) else self._topic_rate)
        )

    @rate.setter
    def rate(self, value: float) -> None:
        # Change the request rate of the topic not the rate of the topic itself
        self._request_rate = value

    @property
    def timestamp(self) -> float:
        """The timestamp of the last update of the topic"""
        return self._timestamp

    @property
    def last_timestamp(self) -> float:
        return self._last_timestamp

    @property
    def callbacks(self) -> List[Callable]:
        """The list of callbacks to call when a new message is received"""
        return self._callbacks

    def call(self, topic_struct) -> None:
        for callback in self._callbacks:
            if callable(callback):
                callback(topic_struct)

    @timeit_if_debug
    def subscribe(self) -> Any:
        """Get the latest message from the topic"""
        logging.debug(f"Subscribing to {self._name}")
        self._last_timestamp = time.time()

        # Check that the memory is not empty
        if self._memory is None:
            return None
        if self._memory.buf is None:
            return None

        # Get the message from the shared memory
        encoded = bytes(self._memory.buf[:])

        self._topic.decode(encoded)

        self._timestamp = self._topic.timestamp_  # This comes from the topic itself
        self._new_message = self._timestamp != self._last_timestamp
        self._last_timestamp = self._timestamp

        self._topic_rate = self._topic.rate_  # This comes from the topic itself

        # Note: Calling the callbacks is done in the main loop not here

    def stop(self) -> None:
        if self._memory is not None:
            try:
                self._memory.close()
            except FileNotFoundError:
                logging.error(f"Shared memory {self._uuid} not found")
        else:
            logging.debug(f"Shared memory {self._uuid} is None")
        logging.debug(f"Subscription {self._name} deleted")
