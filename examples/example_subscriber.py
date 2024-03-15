import argparse
import logging  # noqa
import time
from typing import NoReturn

from custom_logger import setup_logger

from axone.node import Node
from axone.node_process import NodeProcess


class ExampleNodeSubscriber:
    """
    Example Node to subscribe to messages incoming from other nodes
    Three subscribers are registered to listen to the topics from the node "example_publisher":
    - topic_published_once : subscribe to a topic published once
    - topic_published_rate : subscribe to a topic published at a fixed rate
    - topic_published_rate_func : subscribe to a topic published at a fixed rate from a callback function
    """

    def __init__(self, use_process: bool = False) -> None:
        # Register node
        if not use_process:
            self.node = Node(
                name="example_subscriber",
                memory_endpoint="ExampleNodeMemory",
                memory_size=4096,
            )
        else:
            self.node = NodeProcess(
                name="example_subscriber",
                memory_endpoint="ExampleNodeMemory",
                memory_size=4096,
            )
        self.last_message = None

    def print(self, message: str) -> None:
        if message.get("message") != self.last_message:
            self.last_message = message.get("message")
        print(message.get("message"))

    def run(self) -> NoReturn:
        try:
            self.node.subscribe("topic_published_once", callback=self.print)
            self.node.subscribe("topic_published_rate", callback=self.print)
            self.node.subscribe("topic_published_rate_func", callback=self.print)

            # Note start the node after registering the subscribers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            while True:
                time.sleep(1)

                # Note : when using NodeProcess the callback print is pickled so the last_message is not updated
                print("last_message", self.last_message)
                # However, it is possible to get the last message from the shared memory using listen_once
                print(self.node.listen_once("topic_published_once"))
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node._memory.shm.close()
            del self.node


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--debug", action="store_true")
    argparser.add_argument("-p", "--process", action="store_true")
    args = argparser.parse_args()

    setup_logger(debug=args.debug)
    node = ExampleNodeSubscriber(use_process=args.process)
    node.run()
