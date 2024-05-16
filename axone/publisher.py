import time
from multiprocessing.shared_memory import SharedMemory

from axone.axone_struct import AxoneStruct
from axone.utils import generate_uuid


class Publisher:
    def __init__(
        self,
        topic: AxoneStruct,
        rate: float,
    ) -> None:
        # Ensure that the topic is an instance of AxoneStruct or that it has inherited from it
        if not isinstance(topic, AxoneStruct):
            raise ValueError("The topic should be an instance of AxoneStruct")

        self._topic: AxoneStruct = topic
        self._name: str = self._topic.__class__.__name__
        self._rate: float = float(rate)
        self._last_update: float = 0

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

    def publish(self) -> None:
        """Update the topic"""
        self._last_update = time.time()
        encoded = self._topic.encode()
        self._memory.buf[: len(encoded)] = bytes(encoded)


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
