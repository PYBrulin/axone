import logging
import os
import socket
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
        method: str = "shared_memory",
    ) -> None:
        # Ensure that the topic is an instance of AxoneStruct or that it has inherited from it
        if not isinstance(topic, AxoneStruct):
            raise ValueError("The topic should be an instance of AxoneStruct")

        self._topic: AxoneStruct = topic
        self._name: str = self._topic.__class__.__name__
        self._source: str = source if source is not None else "unknown"
        self._rate: float = float(rate)
        self._last_update: float = 0
        self._method: str = method
        self._socket_path: str = f"/tmp/{self._name}_socket"

        self._uuid = generate_uuid(self._name)

        # Prepare common fields for the topic
        self._topic.source_ = self._source
        self._topic.rate_ = self._rate
        self._topic.timestamp_ = time.time()

        if self._method == "shared_memory":
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
        elif self._method == "socket":
            self._create_socket()

        # TODO : Implement unlink, close, etc for the SHM

    def _create_socket(self) -> None:
        if os.path.exists(self._socket_path):
            os.remove(self._socket_path)
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._socket.bind(self._socket_path)
        logging.debug(f"UDP socket created at {self._socket_path}")

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

        if self._method == "shared_memory":
            self._memory.buf[: len(encoded)] = bytes(encoded)
        elif self._method == "socket":
            self._publish_socket(encoded)

    def _publish_socket(self, encoded: bytes) -> None:
        retries = 0
        max_retries = 5
        while retries < max_retries:
            try:
                self._socket.sendto(encoded, self._socket_path)
                return
            except OSError as e:
                logging.error(f"Failed to send message to socket {self._socket_path}: {e}")
                retries += 1
                time.sleep(0.1)  # Wait a bit before retrying
        logging.error(f"Failed to send message to socket {self._socket_path} after {max_retries} attempts")

    def stop(self) -> None:
        if self._method == "shared_memory":
            if self.has_created_shared_memory:
                self._memory.unlink()
            else:
                self._memory.close()
        elif self._method == "socket":
            self._socket.close()
            if os.path.exists(self._socket_path):
                os.remove(self._socket_path)
        logging.debug(f"Publisher {self._name} stopped")


if __name__ == "__main__":

    class ACustomMessage(AxoneStruct):
        a: int = 987654321
        b: str = "Hello"
        c: float = 12.345

    my_custom_message = ACustomMessage()

    p = Publisher(my_custom_message, 3, method="socket")
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
