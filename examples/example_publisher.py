import argparse
import logging
import time
from typing import NoReturn

from custom_logger import setup_logger

from axone.node import Node
from axone.node_process import NodeProcess


class ExampleNodePublisher:
    """
    Example Node to publish messages at different rates
    Three publishers are registered:
    - topic_published_once : publish a message once
    - topic_published_rate : publish a message at a fixed rate
    - topic_published_rate_func : publish a message at a fixed rate from a callback function
    """

    def __init__(self, use_process: bool = False) -> None:
        self.use_process = use_process
        # Register node
        if not self.use_process:
            self.node = Node(
                name="example_publisher",
                memory_endpoint="ExampleNodeMemory",
                memory_size=4096,
            )
        else:
            self.node = NodeProcess(
                name="example_publisher",
                memory_endpoint="ExampleNodeMemory",
                memory_size=4096,
            )

    def publish_actualization(self) -> None:
        return {"message": f"Hello from topic_published_rate_func {time.time()}"}  # Return a dictionary

    def run(self) -> NoReturn:
        try:
            # Register a rated publisher
            self.node.publish_rate(
                "topic_published_rate",
                message={"message": "Hello from topic_published_rate"},
                rate=3,
            )

            # Register a rated publisher from a callback function
            self.node.publish_rate(
                "topic_published_rate_func",
                message=self.publish_actualization,
                rate=2,
            )

            # Note start the node after registering the publishers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            counter = 0
            while True:
                self.node.publish_once(
                    "topic_published_once",
                    {"message": f"Hello from topic_published_once {counter}"},
                )
                logging.info(f"Published message to topic_published_once : {counter}")

                counter += 1

                if not self.use_process:
                    print(f"Memory size : {self.node._memory.size}")

                time.sleep(1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            if not self.use_process:
                self.node._memory.shm.close()
            else:
                self.node.stop()
            del self.node


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--debug", action="store_true")
    argparser.add_argument("-p", "--process", action="store_true")
    args = argparser.parse_args()

    setup_logger(debug=args.debug)

    node = ExampleNodePublisher(use_process=args.process)
    node.run()
