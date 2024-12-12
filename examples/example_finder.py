import argparse
import time
from typing import NoReturn

from axone.custom_logger import setup_logger
from axone.node import AxoneNode
from axone.node_process import AxoneNodeProcess


class ExampleNodeFinder:
    """
    Example Node to find other connected nodes
    """

    def __init__(self, use_process: bool = False) -> None:
        # Register node
        NodeClass = AxoneNode if not use_process else AxoneNodeProcess
        self.node = NodeClass(
            name="example_finder",
            centralized_memory_endpoint="ExampleNodeMemory",
        )

    def run(self) -> NoReturn:
        try:
            # Note start the node after registering the subscribers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            while True:
                print("=" * 50)
                node_list = self.node.list_nodes()
                print("Node lists:\n\t" + "\n\t".join(f"{k}: {v}" for k, v in node_list.items()))
                # print(
                #     "Searching for example_publisher:",
                #     "Found" if self.node.find_node_by_name('example_publisher') is not None else "Not Found",
                # )
                # print("Services available:", self.node.is_node_advertising_services("example_publisher"))

                for node_id, node_name in node_list.items():
                    print()
                    print("ID:", node_id, "Node:", node_name)
                    node_config = self.node.get_node_configuration(node_name)
                    print("Configuration:", "\n\t".join(f"{k}: {v}" for k, v in node_config.items()))
                    print("Services available:", self.node.is_node_advertising_services(node_name))
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
    args = argparser.parse_args()

    setup_logger(debug=args.debug)
    node = ExampleNodeFinder(use_process=args.process)
    node.run()
