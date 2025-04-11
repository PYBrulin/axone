import argparse
import os
import time
from typing import NoReturn

from axone.custom_logger import setup_logger
from axone.enums import Method
from axone.node import AxoneNode
from axone.node_process import AxoneNodeProcess


class ExampleNodePerformer:
    """Example Node to register services and parameters.

    This node is able to receive call made by the node "example_actuator".
    Four services are listed in this example, which take several arguments and
    can, depending on the function, return a value.
    """

    def __init__(self, use_process: bool = False, use_shared_memory: bool = False) -> None:
        self.use_process = use_process
        self.use_shared_memory = use_shared_memory
        self.method = Method.SOCKET if not self.use_shared_memory else Method.SHARED_MEMORY

        # Class parameters
        self.parameters = {"x": 1, "y": 2, "z": 3}

        # Class services/callbacks
        services = {
            self.print: {"message": "str"},
            self.move: {"x": "float", "y": "float", "z": "float"},
            self.stop: {},
            self.simple_addition: ["a", "b"],
        }

        # Register node
        NodeClass = AxoneNode if not self.use_process else AxoneNodeProcess
        self.node = NodeClass(
            name="example_performer",
            method=self.method,
            centralized_memory_endpoint="ExampleNodeMemory",
            parameters=self.parameters,
            services=services,
            # hide_services=True,
            # Here we load a config file next to this script
            config_file=os.path.join(os.path.dirname(__file__), "axone.json"),
        )

    # region service callbacks

    def print(self, message: str) -> None:
        print(f"\n{message}")

    def move(self, x: float, y: float, z: float) -> dict[str, float]:
        self.parameters["x"] = x
        self.parameters["y"] = y
        self.parameters["z"] = z
        print(f"Moving around {x}, {y}, {z}")
        # Return an answer to the caller
        return {"xy": x * y, "yz": y * z, "zx": z * x}

    def stop(self) -> None:
        print("Stopping")

    def simple_addition(self, a, b):
        return a + b

    # endregion service callbacks

    def run(self) -> NoReturn:
        # services are already pre-registered in the node
        # There is nothing to do here except wait for a call
        try:
            # Note start the node after registering the publishers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            while True:
                # self.node.update_parameters(self.parameters)  # Update the parameters displayed in the node info
                time.sleep(1)

        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node.stop()
            del self.node


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--debug", action="store_true")
    argparser.add_argument("-p", "--process", action="store_true")
    argparser.add_argument("-shm", "--shared-memory", action="store_true")
    args = argparser.parse_args()

    setup_logger(debug=args.debug)
    node = ExampleNodePerformer(use_process=args.process)
    node.run()
