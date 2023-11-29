import logging  # noqa
import math
import os
import time
from typing import NoReturn

from axone.node import Node

os.system("cls||clear")  # Clear the terminal

from custom_logger import setup_logger

setup_logger(debug=False)


class ExampleNodeActuator:
    """
    Example Node to call actions of another node
    This node functions can call the actions of the node "example_performer"
    """

    def __init__(self) -> None:
        # Class actions/callbacks
        actions = {
            self.move_response: {
                "xy": "float",
                "yz": "float",
                "zx": "float",
            },  # A call back response function triggered by the response of the action "move"
        }

        # Register node
        self.node = Node(
            name="example_actuator",
            memory_endpoint="ExampleNodeMemory",
            memory_size=4096,
            actions=actions,
        )

    def move_response(
        self,
        xy: float,
        yz: float,
        zx: float,
    ) -> None:
        """Receive the response of the action "move" which is the sum of the parameters x+y, y+z, z+x"""
        print(
            "Received a response from move: "
            + f"x+y = {xy}, y+z = {yz}, z+x = {zx}"
        )

    def run(self) -> NoReturn:
        try:
            while True:
                # Try to find the node "example_performer" in the network
                target_nodes = self.node.find_node_by_name("example_performer")
                if not target_nodes:
                    print("Target node not found")
                else:  # Found the target node
                    # List the available actions of the target node
                    for target_node in target_nodes:
                        # Call the action "print" of the target node
                        self.node.call_action(
                            dest_node=target_node,
                            action="print",
                            message="Hello from example_actuator",
                        )
                        print("Called action print")
                        time.sleep(1)

                        # Call the action "move" of the target node
                        self.node.call_action(
                            dest_node=target_node,
                            action="move",
                            answer=self.move_response,
                            x=round(
                                math.sin(10 * time.time() * math.pi / 180), 4
                            ),
                            y=round(
                                math.sin(
                                    10 * time.time() * math.pi / 180
                                    + math.pi * 1 / 3
                                ),
                                4,
                            ),
                            z=round(
                                math.sin(
                                    10 * time.time() * math.pi / 180
                                    + math.pi * 2 / 3
                                ),
                                4,
                            ),
                        )
                        print("Called action move")

                        print(
                            f"Parameters of {target_node}: {self.node.get_parameters(target_node)}"
                        )

                    print(f"Memory size : {self.node._memory.size}")

                time.sleep(1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node._memory.shm.close()
            self.node._memory.shm.unlink()  # Call unlink only once to release the shared memory
            del self.node


if __name__ == "__main__":
    node = ExampleNodeActuator()
    node.run()
