import logging  # noqa
import os
import time
from typing import NoReturn

from axone.node import Node

os.system("cls||clear")  # Clear the terminal


from custom_logger import setup_logger

setup_logger(debug=False)


class ExampleNodeSubscriber:
    """
    Example Node to subscribe to messages incoming from other nodes
    Three subscribers are registered to listen to the topics from the node "example_publisher":
    - topic_published_once : subscribe to a topic published once
    - topic_published_rate : subscribe to a topic published at a fixed rate
    - topic_published_rate_func : subscribe to a topic published at a fixed rate from a callback function
    """

    def __init__(self) -> None:
        # Register node
        self.node = Node(
            name="example_subscriber",
            memory_endpoint="ExampleNodeMemory",
            memory_size=4096,
        )

    def print(self, message: str) -> None:
        print(message.get("message"))

    def run(self) -> NoReturn:
        try:
            self.node.register_subscribe(
                "topic_published_once", callback=self.print
            )
            self.node.register_subscribe(
                "topic_published_rate", callback=self.print
            )
            self.node.register_subscribe(
                "topic_published_rate_func", callback=self.print
            )
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node._memory.shm.close()
            del self.node


if __name__ == "__main__":
    node = ExampleNodeSubscriber()
    node.run()
