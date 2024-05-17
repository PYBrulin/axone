import argparse
import logging  # noqa
import time
from typing import NoReturn

from axone.custom_logger import setup_logger
from axone.node import AxoneNode

# from axone.node_process import NodeProcess


class ExampleNodeFinder:
    """
    Example Node to find other connected nodes
    """

    def __init__(self, use_process: bool = False) -> None:
        # Register node
        # if not use_process:
        self.node = AxoneNode(
            name="example_finder",
            centralized_memory_endpoint="ExampleNodeMemory",
        )
        # else:
        #     self.node = NodeProcess(
        #         name="example_subscriber",
        #         memory_endpoint="ExampleNodeMemory",
        #         memory_size=4096,
        #     )

    def run(self) -> NoReturn:
        try:

            # Note start the node after registering the subscribers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            while True:

                print("Node lists:", self.node.list_nodes())
                print(
                    "Searching for example_publisher:",
                    "Found" if self.node.find_node_by_name('example_publisher') is not None else "Not Found",
                )
                print("Services available:", self.node.is_node_advertising_services("example_publisher"))

                time.sleep(1)

        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            # self.node._memory.shm.close()
            self.node.stop()
            del self.node


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--debug", action="store_true")
    argparser.add_argument("-p", "--process", action="store_true")
    args = argparser.parse_args()

    setup_logger(debug=args.debug)
    node = ExampleNodeFinder(use_process=args.process)
    node.run()
