import logging
import math
import os
import time
from typing import NoReturn

from axone.node import Node

os.system("cls||clear")  # Clear the terminal
logging.basicConfig(level=logging.INFO)


class ExampleNodeActuator:
    """
    Example Node to call actions of another node
    This node functions can call the actions of the node "example_performer"
    """

    def __init__(self) -> None:
        # Register node
        self.node = Node(
            name="example_actuator",
            memory_endpoint="ExampleNodeMemory",
            memory_size=4096,
        )

    def print(self, message: str) -> None:
        print(message.get("message"))

    def run(self) -> NoReturn:
        try:
            while True:
                # Try to find the node "example_performer" in the network
                target_nodes = self.node.find_node_by_name("example_performer")
                if not target_nodes:
                    print("Target node not found")
                else:
                    print("Target node found", target_nodes)

                    # List the available actions of the target node
                    for target_node in target_nodes:
                        #     print(
                        #         f"Available actions {target_node}: {self.node.list_node_actions(target_node)}"
                        #     )

                        # Call the action "print" of the target node
                        self.node.call_action(
                            dest_node=target_node,
                            action="print",
                            message="Hello from example_actuator",
                        )
                        print("Called action print")
                        time.sleep(1)

                        self.node.call_action(
                            dest_node=target_node,
                            action="move",
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
