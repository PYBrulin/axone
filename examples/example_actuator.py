import argparse
import logging  # noqa
import math
import time
from typing import NoReturn

from axone.custom_logger import setup_logger
from axone.node import Node
from axone.node_process import NodeProcess


class ExampleNodeActuator:
    """
    Example Node to call services of another node
    This node functions can call the services of the node "example_performer"
    """

    def __init__(self, use_process: bool = False) -> None:
        self.use_process = use_process
        # Class services/callbacks
        services = {
            self.move_response: {
                "xy": "float",
                "yz": "float",
                "zx": "float",
            },  # A call back response function triggered by the response of the service "move"
        }

        # Register node
        if not self.use_process:
            self.node = Node(
                name="example_actuator",
                memory_endpoint="ExampleNodeMemory",
                memory_size=4096,
                services=services,
            )
        else:
            self.node = NodeProcess(
                name="example_actuator",
                memory_endpoint="ExampleNodeMemory",
                memory_size=4096,
                services=services,
            )

    def move_response(
        self,
        xy: float,
        yz: float,
        zx: float,
    ) -> None:
        """Receive the response of the service "move" which is the sum of the parameters x+y, y+z, z+x"""
        print("Received a response from move: " + f"x+y = {xy}, y+z = {yz}, z+x = {zx}")

    def run(self) -> NoReturn:
        try:
            # Note start the node after registering the publishers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            while True:
                # Try to find the node "example_performer" in the network
                target_node_id = self.node.find_node_by_name("example_performer")
                if not target_node_id:
                    print("Target node not found")
                else:  # Found the target node
                    # List the available services of the target node
                    print(f"Available services of {target_node_id}: {self.node.list_node_services(target_node_id)}")
                    # Call the service "print" of the target node
                    print("Calling service print")
                    self.node.call_service(
                        dest_node_id=target_node_id,
                        service="print",
                        message="Hello from example_actuator",
                    )
                    print("Called service print")
                    time.sleep(1)

                    # Call the service "move" of the target node
                    if not self.use_process:
                        # Note : the service "move" declare an answer callback function which is
                        # triggered when the service is done.  However it is currently not possible
                        # to use the callback function with the NodeProcess variant.
                        print("Calling service move")
                        self.node.call_service(
                            dest_node_id=target_node_id,
                            service="move",
                            answer=self.move_response,
                            x=round(math.sin(10 * time.time() * math.pi / 180), 4),
                            y=round(
                                math.sin(10 * time.time() * math.pi / 180 + math.pi * 1 / 3),
                                4,
                            ),
                            z=round(
                                math.sin(10 * time.time() * math.pi / 180 + math.pi * 2 / 3),
                                4,
                            ),
                        )
                        print("Called service move")

                    print(f"Parameters of {target_node_id}: {self.node.get_parameters(target_node_id)}")

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
    node = ExampleNodeActuator(use_process=args.process)
    node.run()
