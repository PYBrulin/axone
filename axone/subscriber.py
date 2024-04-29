import logging
import os
from typing import Any, Callable, List

from axone.shared_memory_dict import SharedMemoryDict
from axone.utils import generate_uuid


class Subscription:
    def __init__(
        self,
        topic_name: str = "",
        subscribe_rate: float = 1,
    ) -> None:
        self._topic: str = topic_name
        self._subscribe_rate: float = subscribe_rate
        self._message = None
        self._last_message = None
        self._timestamp = 0
        self._last_timestamp = 0
        self._source_id = None
        self._last_source_id = None
        self._callbacks = []

        # Get the uuid of the topic which is a reproducible random string based
        # on the topic name
        self._topic_uuid = generate_uuid(self._topic)

        # Find the shared memory for the topic
        try:
            self._memory = SharedMemoryDict(name=self._topic_uuid)
            logging.info(f"Created subscriber for topic {self._topic_uuid}:{self._topic}")
        except (ValueError, FileNotFoundError):
            logging.error(f"Topic {self._topic} does not exist. Please create a publisher for this topic first.")
            self._memory = None

    @property
    def topic(self) -> str:
        """The topic name of the subscription"""
        return self._topic

    @topic.setter
    def topic(self, topic: str) -> None:
        self._topic = topic
        self._topic_uuid = generate_uuid(self._topic)

        del self._memory
        # Reset the shared memory for the topic
        # Note: If the topic does not already exist, the following wil require
        try:
            self._memory = SharedMemoryDict(name=self._topic_uuid)
            logging.info(f"Created subscriber for topic {self._topic_uuid}:{self._topic}")
        except (ValueError, FileNotFoundError):
            self._memory = None

    @property
    def subscribe_rate(self) -> float:
        """The subscribe_rate at which the topic is subscribed"""
        return self._subscribe_rate

    @subscribe_rate.setter
    def subscribe_rate(self, subscribe_rate: float) -> None:
        self._subscribe_rate = subscribe_rate

    @property
    def message(self) -> Any | None:
        """The content of the last update of the topic"""
        return self._message

    @property
    def last_message(self) -> Any | None:
        """The content of the last update of the topic"""
        return self._last_message

    @last_message.setter
    def last_message(self, last_message: Any) -> None:
        self._last_message = last_message

    @property
    def last_timestamp(self) -> float:
        """The timestamp of the last update of the topic"""
        return self._last_timestamp

    @last_timestamp.setter
    def last_timestamp(self, last_timestamp: float) -> None:
        self._last_timestamp = last_timestamp

    @property
    def last_source_id(self) -> float:
        """The source node id of the last update of the topic"""
        return self._last_source_id

    def listen(self) -> None:
        """
        This is the only access to the shared memory within this class.
        It reads the shared memory and updates the message attribute.
        """
        if self._memory is None:
            # Try to reconnect to the topic
            self.topic = self._topic
            return
        else:  # Validate the existance of the lock
            if not os.path.exists(self._memory._lock.lock_file):
                logging.error(f"Lock for topic {self._topic} does not exist. Please create a publisher for this topic first.")
                self._memory = None
                return

        db = dict(self._memory)
        # Dispatch gathered data
        self._message = {k: v for k, v in db.items() if not k.startswith("__")}
        self._timestamp = db.get("__t")
        self._source_id = db.get("__s")
        self.subscribe_rate = db.get("__r", self.subscribe_rate)

    @property
    def callbacks(self) -> List[Callable]:
        """The list of callbacks to call when a new message is received"""
        return self._callbacks

    def call(self, message) -> None:
        for callback in self._callbacks:
            callback(message)


if __name__ == "__main__":
    # Try to subscribe to the topic "topic_published_rate"
    s = Subscription("topic_published_once", 3)
    print(s._memory)

    s = Subscription("topic_published_rate", 3)
    print(s._memory)

    s = Subscription("topic_published_rate_func", 3)
    print(s._memory)
