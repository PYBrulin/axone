import argparse
import logging
import time
from typing import NoReturn

# from axone.node_process import NodeProcess
from axone.axone_struct import AxoneTopic
from axone.custom_logger import setup_logger
from axone.node import AxoneNode


class ARatedTopic(AxoneTopic):
    message: str = "Hello from topic_published_rate"


class ARatedCallbackTopic(AxoneTopic):

    def _update_message(self) -> None:
        # self.message_string = f"Hello message_string from topic_published_rate_func {time.time()}"
        return f"Hello message_callback from topic_published_rate_func {2 * time.time()}"

    message_string: int = lambda x: 1 + 1
    message_callback: str = _update_message


class AStandaloneTopic(AxoneTopic):
    message: str = "I am a message that is eventually going to be overwritten by the node. bye."


class ExampleNodePublisher:
    """
    Example Node to publish messages at different rates
    Three publishers are registered:
    - topic_published_once : publish a message once
    - topic_published_rate : publish a message at a fixed rate
    - topic_published_rate_func : publish a message at a fixed rate from a callback function
    """

    def __init__(self, use_process: bool = False) -> None:
        self.use_process = use_process
        # Register node
        # if not self.use_process:
        self.node = AxoneNode(
            name="example_publisher",
            centralized_memory_endpoint="ExampleNodeMemory",
        )
        # else:
        #     self.node = NodeProcess(
        #         name="example_publisher",
        #         memory_endpoint="ExampleNodeMemory",
        #         memory_size=4096,
        #     )

    def run(self) -> NoReturn:
        try:
            # Register a rated publisher
            self.node.publish_rate(ARatedTopic(), rate=3)

            # # Register a rated publisher from a callback function
            self.node.publish_rate(ARatedCallbackTopic(), rate=2)

            # Note start the node after registering the publishers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            a_standalone_topic = AStandaloneTopic()

            counter = 0
            while True:
                a_standalone_topic.message = f"Hello from topic_published_once {counter}"
                self.node.publish_once(a_standalone_topic)
                logging.info(f"Published message to topic_published_once : {a_standalone_topic.message}")

                counter += 1

                # if not self.use_process:
                #     print(f"Memory size : {self.node._memory.size}")

                time.sleep(1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            # if not self.use_process:
            #     self.node._memory.shm.close()
            # else:
            self.node.stop()
            del self.node


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--debug", action="store_true")
    argparser.add_argument("-p", "--process", action="store_true")
    args = argparser.parse_args()

    setup_logger(debug=args.debug)
    node = ExampleNodePublisher(use_process=args.process)
    node.run()
