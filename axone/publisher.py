import logging
import time
from multiprocessing.shared_memory import SharedMemory
from typing import Optional

from axone.axone_struct import AxoneStruct
from axone.utils import generate_uuid, timeit_if_debug


class Publisher:

    def __init__(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
        source: Optional[str] = None,
    ) -> None:
        # Ensure that the topic is an instance of AxoneStruct or that it has inherited from it
        if not isinstance(topic, AxoneStruct):
            raise ValueError("The topic should be an instance of AxoneStruct")

        self._topic: AxoneStruct = topic
        self._name: str = self._topic.__class__.__name__
        self._source: str = source if source is not None else "unknown"
        self._rate: float = float(rate)
        self._last_update: float = 0

        self._uuid = generate_uuid(self._name)

        # Prepare common fields for the topic
        self._topic.source_ = self._source
        self._topic.rate_ = self._rate
        self._topic.timestamp_ = time.time()

        # Create a shared memory for the topic
        self.has_created_shared_memory = False
        try:
            self._memory = SharedMemory(
                name=self._uuid,
                create=True,
                size=topic.get_approximate_size(),
            )
            self.has_created_shared_memory = True
        except FileExistsError:
            logging.warning(f"Shared memory {self._uuid} already exists")
            # Try to open the shared memory if it already exists
            self._memory = SharedMemory(name=self._uuid, create=False)

        # TODO : Implement unlink, close, etc for the SHM

    @property
    def topic(self) -> str:
        """The string representation of the topic"""
        return self._topic

    @property
    def name(self) -> str:
        """The topic name of the publisher"""
        return self._name

    @property
    def rate(self) -> float:
        """The rate at which the topic is published"""
        return self._rate

    @property
    def last_update(self) -> float:
        """The timestamp of the last update of the topic"""
        return self._last_update

    @timeit_if_debug
    def publish(self, topic: AxoneStruct = None) -> None:
        """Update the topic"""
        if topic is not None:
            # This will update the topic for the next publish
            self._topic: AxoneStruct = topic

        logging.debug(f"Publishing topic {self._name}")
        self._last_update = time.time()
        # Append specific fields to the topic
        self._topic.source_ = self._source
        self._topic.rate_ = self._rate
        self._topic.timestamp_ = time.time()
        logging.debug(f"Topic {self._topic}")
        encoded = self._topic.encode()
        self._memory.buf[: len(encoded)] = bytes(encoded)

    def stop(self) -> None:
        if self.has_created_shared_memory:
            self._memory.unlink()
        else:
            self._memory.close()
        logging.debug(f"Publisher {self._name} stopped")


if __name__ == "__main__":

    class ACustomMessage(AxoneStruct):
        a: int = 987654321
        b: str = "Hello"
        c: float = 12.345

    my_custom_message = ACustomMessage()

    p = Publisher(my_custom_message, 3)
    print("topic", p.topic)
    print("rate", p.rate)
    print("last_update", p.last_update)
    p.last_update = 1.0
    print("last_update", p.last_update)
    p.content = {"b": "Hello from topic_published_rate"}
    print("content", p.content)
    print("topic", p.topic)

    p.content = {"b": "Hello AGAIN"}
    print("content", p.content)
    print("topic", p.topic)

    print(p._memory.size)
