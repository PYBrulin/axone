import logging
import os
import time
from typing import NoReturn

from axone.node import Node

os.system("cls||clear")  # Clear the terminal


from custom_logger import setup_logger

setup_logger(debug=False)


class ExampleNodePublisher:
    """
    Example Node to publish messages at different rates
    Three publishers are registered:
    - topic_published_once : publish a message once
    - topic_published_rate : publish a message at a fixed rate
    - topic_published_rate_func : publish a message at a fixed rate from a callback function
    """

    def __init__(self) -> None:
        # Register node
        self.node = Node(
            name="example_publisher",
            memory_endpoint="ExampleNodeMemory",
            memory_size=4096,
        )

    def publish_actualization(self) -> None:
        return {
            "message": f"Hello from topic_published_rate_func {time.time()}"
        }  # Return a dictionary

    def run(self) -> NoReturn:
        try:
            # Register a rated publisher
            self.node.register_publish(
                "topic_published_rate",
                message={"message": f"Hello from topic_published_rate"},
                rate=3,
            )

            # Register a rated publisher from a callback function
            self.node.register_publish(
                "topic_published_rate_func",
                message=self.publish_actualization,
                rate=2,
            )

            counter = 0
            while True:
                self.node.publish_once(
                    "topic_published_once",
                    {"message": f"Hello from topic_published_once {counter}"},
                )
                logging.info(
                    f"Published message to topic_published_once : {counter}"
                )
                counter += 1

                print(f"Memory size : {self.node._memory.size}")

                time.sleep(1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node._memory.shm.close()
            del self.node


if __name__ == "__main__":
    node = ExampleNodePublisher()
    node.run()
