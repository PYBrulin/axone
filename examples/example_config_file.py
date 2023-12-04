import json
import logging  # noqa
import os
import time
from typing import NoReturn

from custom_logger import setup_logger

from axone.node import Node

setup_logger(debug=False)


class ConfigFileNode:
    """
    Simple server example which shows how to load a config file to connect a
    communication endpoint. It eases the configuration of all nodes in a
    network without having to change the source code of each node individually.

    Note that this example actually connects to the same endpoint as the other
    examples. This is just to show how to load a config file.
    """

    def __init__(self) -> None:
        # Register node
        self.node = Node(
            name=self.__class__.__name__,
            config_file=os.path.join(
                os.path.dirname(__file__),
                "axone.json",
            ),  # Here we load a config file next to this script
        )

        print("Node registered")
        print("Node name:", self.node.name)
        print("Node memory endpoint:", self.node.memory_endpoint)
        print("Node memory size:", self.node.memory_size)

    def run(self) -> NoReturn:
        try:
            # No need to run forever for this example
            # Read the memory content three times and then exit
            for _ in range(3):
                print("Memory content :")
                print(
                    json.dumps(
                        dict(self.node._memory),
                        sort_keys=True,
                        indent=4,
                    )
                )
                time.sleep(1)  # 1Hz

        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node._memory.shm.close()
            self.node._memory.shm.unlink()  # Call unlink only once to release the shared memory
            del self.node


if __name__ == "__main__":
    ssn = ConfigFileNode()
    ssn.run()
