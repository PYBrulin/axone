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
            name="example_pub",
            memory_endpoint="ExampleNodeMemory",
            memory_size=1024,
            parameters=self.parameters,
            actions=self.actions,
        )

    def print(self, message: str) -> None:
        print(message)

    def wait(self, duration: float) -> None:
        time.sleep(duration)

    def publish_actualization(self) -> None:
        return {
            "message": f"Hello from topic_published_rate_fc {time.time()}"
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
                "topic_published_rate_fc",
                message=self.publish_actualization,
                rate=2,
            )

            counter = 0
            while True:
                self.node.publish_once(
                    "topic_published_once",
                    {"message": f"Hello from topic_published_once {counter}"},
                    rate=1,
                )
                logging.info(f"Published message to topic_published_once : {counter}")
                counter += 1
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
