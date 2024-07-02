import argparse
import logging
import time
from typing import NoReturn

from axone.axone_struct import AxoneTopic
from axone.custom_logger import setup_logger
from axone.node import AxoneNode
from axone.node_process import AxoneNodeProcess


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
        NodeClass = AxoneNode if not self.use_process else AxoneNodeProcess
        self.node = NodeClass(
            name="example_publisher",
            centralized_memory_endpoint="ExampleNodeMemory",
        )

    def run(self) -> NoReturn:
        try:
            # Note start the node before registering the publishers.
            # This is a requirement for the AxoneNodeProcess variant.
            # If using the standard AxoneNode variant, the node can be started
            # after registering the publishers which is more flexible.
            self.node.start()

            a_standalone_topic = AStandaloneTopic()

            ns_times = []

            for i in range(100):
                a_standalone_topic.message = f"Hello from topic_published_once {i}"
                start_time = time.perf_counter_ns()
                self.node.publish_once(a_standalone_topic)
                end_time = time.perf_counter_ns()
                logging.debug(f"Time to publish_once: {end_time - start_time} ns")
                ns_times.append(end_time - start_time)

                time.sleep(0.1)

            logging.info(
                f"Average time to publish_once: {sum(ns_times) / len(ns_times)} ns => {sum(ns_times) / len(ns_times) / 1e6} ms"
            )

        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node.stop()
            del self.node


class ExampleNodeSubscriber:
    """
    Example Node to subscribe to messages incoming from other nodes
    Three subscribers are registered to listen to the topics from the node "example_publisher":
    - topic_published_once : subscribe to a topic published once
    - topic_published_rate : subscribe to a topic published at a fixed rate
    - topic_published_rate_func : subscribe to a topic published at a fixed rate from a callback function
    """

    def __init__(self, use_process: bool = False) -> None:
        self.use_process = use_process
        # Register node
        NodeClass = AxoneNode if not self.use_process else AxoneNodeProcess
        self.node = NodeClass(
            name="example_publisher",
            centralized_memory_endpoint="ExampleNodeMemory",
        )

    def run(self) -> NoReturn:
        try:
            # Note start the node after registering the subscribers
            # Which is a requirement for the NodeProcess variant
            self.node.start()

            ns_times = []

            for i in range(100):
                # Note : when using NodeProcess the callback print is pickled so the last_message is not updated
                # print("last_message", self.last_message)
                # However, it is possible to get the last message from the shared memory using listen_once
                start_time = time.perf_counter_ns()
                self.node.listen_once("AStandaloneTopic")
                end_time = time.perf_counter_ns()
                logging.debug(f"Time to publish_once: {end_time - start_time} ns")
                ns_times.append(end_time - start_time)

                time.sleep(0.1)

            logging.info(
                f"Average time to listen_once: {sum(ns_times) / len(ns_times)} ns => {sum(ns_times) / len(ns_times) / 1e6} ms"
            )

        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node.stop()
            del self.node


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--debug", action="store_true")
    args = argparser.parse_args()

    setup_logger(debug=args.debug)

    # pub
    pub = ExampleNodePublisher(use_process=False)
    pub.run()

    pub = ExampleNodePublisher(use_process=True)
    pub.run()

    # sub
    pub = ExampleNodePublisher(use_process=False)
    pub.node.start()
    a_standalone_topic = AStandaloneTopic()
    a_standalone_topic.message = "Hello from topic_published_once"
    pub.node.publish_once(a_standalone_topic)

    sub = ExampleNodeSubscriber(use_process=False)
    sub.run()

    sub = ExampleNodeSubscriber(use_process=True)
    sub.run()

    pub.node.stop()
