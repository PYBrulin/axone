import logging  # noqa
import os
import time
from typing import Dict, NoReturn

from axone.node import Node

os.system("cls||clear")  # Clear the terminal


from custom_logger import setup_logger

setup_logger(debug=False)


class ExampleNodePerformer:
    """
    Example Node to register services and parameters
    This node functions can be called by the node "example_actuator"
    """

    def __init__(self) -> None:
        # Class parameters
        self.parameters = {
            "x": 1,
            "y": 2,
            "z": 3,
        }

        # Class services/callbacks
        services = {
            self.print: {
                "message": "str",
            },
            self.move: {
                "x": "float",
                "y": "float",
                "z": "float",
            },
            self.stop: {},
        }

        # Register node
        self.node = Node(
            name="example_performer",
            memory_endpoint="ExampleNodeMemory",
            memory_size=4096,
            parameters=self.parameters,
            services=services,
            # hide_services=True,
        )

    # region service callbacks
    def print(self, message: str) -> None:
        print(message)

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ) -> Dict[str, float]:
        self.parameters["x"] = x
        self.parameters["y"] = y
        self.parameters["z"] = z
        print(f"Moving around {x}, {y}, {z}")
        # Return an answer to the caller
        return {
            "xy": x * y,
            "yz": y * z,
            "zx": z * x,
        }

    def stop(self) -> None:
        print(f"Stopping")

    # endregion

    def run(self) -> NoReturn:
        # services are already pre-registered in the node
        # There is nothing to do here except wait for a call
        try:
            while True:
                self.node.update_parameters(
                    self.parameters
                )  # Update the parameters displayed in the node info
                time.sleep(1)

        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node._memory.shm.close()
            del self.node


if __name__ == "__main__":
    node = ExampleNodePerformer()
    node.run()
