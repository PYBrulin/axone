from typing import Any, Callable, List

from axone.utils import generate_uuid


class Subscription:
    def __init__(
        self,
        topic_name: str = "",
        rate: float = -1,
    ) -> None:
        self._topic: str = topic_name
        self._rate: float = rate
        self._last_message = None
        self._last_update: float = 0
        self._callbacks = []

        self._topic_uuid = generate_uuid(self._topic)

    @property
    def topic(self) -> str:
        """The topic name of the subscription"""
        return self._topic

    @topic.setter
    def topic(self, topic: str) -> None:
        self._topic = topic
        self._topic_uuid = generate_uuid(self._topic)

    @property
    def rate(self) -> float:
        """The rate at which the topic is subscribed"""
        return self._rate

    @rate.setter
    def rate(self, rate: float) -> None:
        self._rate = rate

    @property
    def last_message(self) -> Any | None:
        """The content of the last update of the topic"""
        return self._last_message

    @last_message.setter
    def last_message(self, message) -> None:
        if message is not None and message != self._last_message:
            self._last_message = message
            message = {
                key: value for key, value in message.items() if not key.startswith("__")
            }  # Remove internal data structures

    @property
    def last_update(self) -> float:
        """The timestamp of the last update of the topic"""
        return self._last_update

    @last_update.setter
    def last_update(self, last_update: float) -> None:
        self._last_update = last_update

    @property
    def callbacks(self) -> List[Callable]:
        """The list of callbacks to call when a new message is received"""
        return self._callbacks

    def call(self, message) -> None:
        for callback in self._callbacks:
            callback(message)
