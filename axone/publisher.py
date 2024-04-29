import logging
from typing import Any

from axone.shared_memory_dict import SharedMemoryDict
from axone.utils import generate_uuid, get_timestamp


class Publisher:
    def __init__(
        self,
        topic_name: str,
        rate: float = -1,
    ) -> None:
        self._topic: str = topic_name
        self._rate: float = rate
        self._last_timestamp: float = 0
        self._content: Any = None

        self._topic_uuid = generate_uuid(self._topic)

        # Create a shared memory for the topic
        self._memory = SharedMemoryDict(
            name=self._topic_uuid,
            size=4096,
        )
        logging.info(f"Created publisher for topic {self._topic_uuid}:{self._topic}")

    def __del__(self) -> None:
        self._memory.cleanup()

    @property
    def topic(self) -> str:
        """The topic name of the publisher"""
        return self._topic

    @property
    def rate(self) -> float:
        """The rate at which the topic is published"""
        return self._rate

    @property
    def last_timestamp(self) -> float:
        """The timestamp of the last update of the topic"""
        return self._last_timestamp

    @last_timestamp.setter
    def last_timestamp(self, last_timestamp: float) -> None:
        self._last_timestamp = last_timestamp

    @property
    def content(self) -> Any:
        return self._content

    @content.setter
    def content(self, content: Any) -> None:
        self._content = content

    def publish(self, content: Any, node_source_id) -> None:
        """
        This is the only access to the shared memory within this class.
        It updates the shared memory with the content provided.
        """
        message = content() if callable(content) else content

        # Add properties
        properties = {
            "__s": node_source_id,
            "__t": get_timestamp(),  # TODO: Set timestamp procession from kwargs
        }
        if self.rate is not None:  # Do not add rate if it is published once or rate is unknown
            properties["__r"] = self.rate

        _merge = message | properties

        self._memory.update(_merge)
        logging.debug(f"Updated {self.topic} with {message}")

        self.last_timestamp = get_timestamp()  # Set the last update timestamp

    def shutdown(self) -> None:
        self._memory.cleanup()
        logging.info(f"Publisher for topic {self._topic_uuid}:{self._topic} has been shutdown.")

        # Remove the shared_memory file and its lock
        # Note: Cause too many problems that i can't be bothered to fix right now
        # self._memory.remove()


if __name__ == "__main__":
    p = Publisher("topic_published_rate", 3)
    print(p.topic)
    print(p.rate)
    p.content = {"message": "Hello from topic_published_rate 2"}

    print(p._memory)

    del p
