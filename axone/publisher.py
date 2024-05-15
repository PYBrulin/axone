from multiprocessing.shared_memory import SharedMemory
from typing import Any

from axone.axone_struct import AxoneMessage
from axone.utils import generate_uuid


class Publisher:
    def __init__(
        self,
        topic: AxoneMessage,
        rate: float,
    ) -> None:
        # Ensure that the topic is an instance of AxoneMessage or that it has inherited from it
        if not isinstance(topic, AxoneMessage):
            raise ValueError("The topic should be an instance of AxoneMessage")

        self._topic: AxoneMessage = topic
        self._name: str = self._topic.__class__.__name__
        self._rate: float = float(rate)
        self._last_update: float = 0
        self._content: Any = None

        self._uuid = generate_uuid(self._name)

        # Create a shared memory for the topic
        self._memory = SharedMemory(
            name=self._uuid,
            create=True,
            size=topic.get_approximate_size(),
        )

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
        """The rate at which the topic is published"""
        return self._rate

    @property
    def last_update(self) -> float:
        """The timestamp of the last update of the topic"""
        return self._last_update

    @last_update.setter
    def last_update(self, last_update: float) -> None:
        self._last_update = last_update

    @property
    def content(self) -> Any:
        return self._topic.__attributes__

    @content.setter
    def content(self, content: Any) -> None:
        for key, value in content.items():
            self._topic[key] = value


if __name__ == "__main__":

    class ACustomMessage(AxoneMessage):
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
