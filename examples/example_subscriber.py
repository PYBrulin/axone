import argparse
import time
from typing import NoReturn

from axone.axone_struct import AxoneStruct
from axone.custom_logger import setup_logger
from axone.node import AxoneNode
from axone.node_process import AxoneNodeProcess


class ExampleNodeSubscriber:
    """
    Example Node to subscribe to messages incoming from other nodes
    Three subscribers are registered to listen to the topics from the node "example_publisher":
    - topic_published_once : subscribe to a topic published once
    - topic_published_rate : subscribe to a topic published at a fixed rate
    - topic_published_rate_func : subscribe to a topic published at a fixed rate from a callback function
    """

    def __init__(self, use_process: bool = False, use_socket: bool = False) -> None:
        self.use_process = use_process
        self.use_socket = use_socket
        self.method = "shared_memory" if not self.use_socket else "socket"
        # Register node
        NodeClass = AxoneNode if not self.use_process else AxoneNodeProcess
        self.node = NodeClass(
            name="example_subscriber",
            centralized_memory_endpoint="ExampleNodeMemory",
        )
        self.last_message = None

    def print_message(self, topic_struct: AxoneStruct) -> None:
        if topic_struct.get("message") != self.last_message:
            self.last_message = topic_struct.get("message")
        print(topic_struct.get("message"))

    def print_callback(self, topic_struct: AxoneStruct) -> None:
        print(topic_struct.get("message_callback"), topic_struct.get("message_string"))

    def run(self) -> NoReturn:
        try:
            # Note start the node after registering the subscribers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            # Subscribe to rated topics
            if not self.use_process:
                self.node.subscribe("ARatedTopic", callback=self.print_message, method=self.method)
                self.node.subscribe("ARatedCallbackTopic", callback=self.print_callback, method=self.method)

            index = 0
            while True:
                time.sleep(0.1)
                print("listen_once")
                print(self.node.subscriptions)

                # Note : when using NodeProcess the callback print is pickled so the last_message is not updated
                # print("last_message", self.last_message)
                # However, it is possible to get the last message from the shared memory using listen_once
                msg = self.node.listen_once("AStandaloneTopic", method=self.method)

                if msg.get("message"):
                    print(msg)
                    _index = int(msg["message"].split(" ")[-1])

                    if _index == index:
                        print("Node has stopped publishing")
                        exit(1)
                    else:
                        index = _index
                else:
                    print("NO MESSAGE")

                print("INDEX", index)

                if self.use_process:
                    print(self.node.listen_once("ARatedTopic", method=self.method))
                    print(self.node.listen_once("ARatedCallbackTopic", method=self.method))

                # print(self.node.subscriptions)

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
    argparser.add_argument("-s", "--socket", action="store_true")
    args = argparser.parse_args()

    setup_logger(debug=args.debug)
    node = ExampleNodeSubscriber(use_process=args.process, use_socket=args.socket)
    node.run()
