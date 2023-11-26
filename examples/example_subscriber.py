import logging
import os
import time
from typing import NoReturn

from axone.node import Node

os.system("cls||clear")  # Clear the terminal
logging.basicConfig(level=logging.INFO)


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
            name="example_sub",
            memory_endpoint="ExampleNodeMemory",
            memory_size=1024,
            parameters=self.parameters,
            actions=self.actions,
        )

    def print(self, message: str) -> None:
        print(message.get("message"))

    def wait(self, duration: float) -> None:
        time.sleep(duration)

    def run(self) -> NoReturn:
        try:
            self.node.register_subscribe("topic_published_once", callback=self.print)
            self.node.register_subscribe("topic_published_rate", callback=self.print)
            self.node.register_subscribe("topic_published_rate_fc", callback=self.print)
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node._memory.shm.close()
            self.node._memory.shm.unlink()  # Call unlink only once to release the shared memory
            del self.node


if __name__ == "__main__":
    node = ExampleNode()
    node.run()
