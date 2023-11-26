from axone.node import Node
import time

from typing import NoReturn


class ExampleNode:
    def __init__(self) -> None:
        # Class parameters
        self.a = 1
        self.b = 2
        self.c = 3
        self.parameters = {
            "a": self.a,
            "b": self.b,
            "c": self.c,
        }

        # Class actions/callbacks
        self.actions = {
            "print": {
                "message": str,
            },
        }

        # Register node
        self.node = Node(
            name="example_node",
            memory_endpoint="ExampleNodeMemory",
            memory_size=1024,
            parameters=self.parameters,
            actions=self.actions,
        )

    def print(self, message: str) -> None:
        print(message)

    def wait(self, duration: float) -> None:
        time.sleep(duration)

    def run() -> NoReturn:
        while True:
            time.sleep(1)
