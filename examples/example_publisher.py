import argparse
import logging
import os
import random
import time
from typing import NoReturn

from axone.axone_struct import AxoneTopic
from axone.custom_logger import setup_logger
from axone.enums import Method
from axone.node import AxoneNode
from axone.node_process import AxoneNodeProcess


class ARatedTopic(AxoneTopic):
    message: str = "Hello from topic_published_rate"


class ARatedCallbackTopic(AxoneTopic):

    def _update_message(self) -> None:
        # self.message_string = f"Hello message_string from topic_published_rate_func {time.time()}"
        return f"Hello message_callback from topic_published_rate_func {2 * time.time()}"

    message_string: int = lambda x: random.randint(0, 100) + random.randint(0, 100)
    message_callback: str = _update_message


class AStandaloneTopic(AxoneTopic):
    message: str = "I am a message that is eventually going to be overwritten by the node. bye."


class ExampleNodePublisher:
    """Example Node to publish messages at different rates.

    Three publishers are registered:
    - topic_published_once : publish a message once
    - topic_published_rate : publish a message at a fixed rate
    - topic_published_rate_func : publish a message at a fixed rate from a callback function
    """

    def __init__(self, use_process: bool = False, use_shared_memory: bool = False, use_encryption: bool = False) -> None:
        self.use_process = use_process
        self.use_shared_memory = use_shared_memory
        self.use_encryption = use_encryption
        self.method = Method.SOCKET if not self.use_shared_memory else Method.SHARED_MEMORY
        # Register node
        NodeClass = AxoneNode if not self.use_process else AxoneNodeProcess
        self.node = NodeClass(
            name="example_publisher",
            method=self.method,
            centralized_memory_endpoint="ExampleNodeMemory",
            # Here we load a config file next to this script
            config_file=os.path.join(os.path.dirname(__file__), "axone.json"),
            encryption_key_path=os.path.join(os.path.dirname(__file__), "encryption.key") if self.use_encryption else None,
        )

    def run(self) -> NoReturn:
        try:
            # Note start the node before registering the publishers.
            # This is a requirement for the AxoneNodeProcess variant.
            # If using the standard AxoneNode variant, the node can be started
            # after registering the publishers which is more flexible.
            self.node.start()

            # Register a rated publisher
            self.node.publish_rate(ARatedTopic(), rate=3, method=self.method)

            # Register a rated publisher from a callback function
            self.node.publish_rate(ARatedCallbackTopic(), rate=2, method=self.method)

            a_standalone_topic = AStandaloneTopic()
            # a_standalone_topic_dict = AStandaloneTopic()

            counter = 0
            while True:
                a_standalone_topic.message = f"Hello from topic_published_once {counter}"
                self.node.publish_once(a_standalone_topic, method=self.method)
                logging.info(f"Published message to topic_published_once : {a_standalone_topic.message}")

                # a_standalone_topic_dict.update(
                #     {
                #         "message": f"Hello from a_standalone_topic_dict {counter}",
                #         "counter": counter,
                #     }
                # )
                # self.node.publish_once(a_standalone_topic_dict)
                # logging.info(f"Published message to a_standalone_topic_dict : {a_standalone_topic_dict.message}")

                counter += 1

                time.sleep(0.1)

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
    argparser.add_argument("-e", "--encryption", action="store_true")
    args = argparser.parse_args()

    setup_logger(debug=args.debug)
    node = ExampleNodePublisher(use_process=args.process, use_shared_memory=args.shared_memory, use_encryption=args.encryption)
    node.run()
