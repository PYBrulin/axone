import logging  # noqa
import os
import time
from typing import NoReturn

from axone.custom_logger import setup_logger
from axone.node import AxoneNode

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
        self.node = AxoneNode(
            name=self.__class__.__name__,
            config_file=os.path.join(
                os.path.dirname(__file__),
                "axone.json",
            ),  # Here we load a config file next to this script
        )

        print("Node registered")
        print("Node name:", self.node.name)
        # print("Node memory endpoint:", self.node.centralized_node.endpoint)

    def run(self) -> NoReturn:
        try:
            # Note start the node after registering the publishers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            time.sleep(1)  # 1Hz
            print("My work here is done.")

        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node.stop()
            del self.node


if __name__ == "__main__":
    ssn = ConfigFileNode()
    ssn.run()
