import logging
import os
import time
from typing import NoReturn

from axone.node import Node

os.system("cls||clear")  # Clear the terminal
logging.basicConfig(level=logging.INFO)


class ExampleNodePerformer:
    """
    Example Node to register actions and parameters
    This node functions can be called by the node "example_actuator"
    """

    def __init__(self) -> None:
        # Class parameters
        self.x = 1
        self.y = 2
        self.z = 3
        self.parameters = {
            "x": self.x,
            "y": self.y,
            "z": self.z,
        }

        # Class actions/callbacks
        self.actions = {
            self.print: {
                "message": "str",
            },
            self.move: {
                "x": "float",
                "y": "float",
                "z": "float",
            },
            # self.stop: {},
        }

        # Register node
        self.node = Node(
            name="example_performer",
            memory_endpoint="ExampleNodeMemory",
            memory_size=4096,
            parameters=self.parameters,
            actions=self.actions,
        )

    # region action callbacks
    def print(self, message: str) -> None:
        print(message)

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ) -> None:
        self.x = x
        self.y = y
        self.z = z
        print(f"Moving around {x}, {y}, {z}")

    def stop(self) -> None:
        print(f"Stopping")

    # endregion

    def run(self) -> NoReturn:
        # Actions are already pre-registered in the node
        # There is nothing to do here except wait for a call
        try:
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
    node = ExampleNodePerformer()
    node.run()
