import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Union

from axone.axone_struct import AxoneStruct
from axone.custom_logger import setup_logger
from axone.publisher import Publisher
from axone.shared_memory import AxoneSharedMemory
from axone.utils import generate_uuid

# from axone.subscription import Subscription

DEFAULT_TIMEOUT = 5
MAX_RETRIES = 10
TIMESTAMP_PRECISION = 0
TIMESTAMP_RANGE = 60 * 60 * 24 * 365  # 1 year


class AxoneNode:
    logger = logging.getLogger(__name__)

    class CentralizedNode:
        """
        class to handle the centralized node

        Updates when the node becomes available or unavailable to the network
        and provide the list of available nodes when requested
        """

        def __init__(self, name: str, node_id: str, **kwargs) -> None:
            self.node_name = name
            self.node_id = node_id

            self.endpoint = kwargs.get("centralized_memory_endpoint", "")
            self.size = kwargs.get("centralized_memory_size", 1024)
            if self.endpoint == "":
                raise ValueError("Memory endpoint cannot be empty.")

            self.memory = AxoneSharedMemory(
                name=self.endpoint,
                size=self.size,
                centralized=True,
            )

        def advertise(self) -> None:
            """Advertise the node to the centralized memory."""

            # Check if the node is already registered
            print(self.node_id)

            if self.memory[self.node_id] is not None:
                logging.warning(f"Node {self.node_name} is already registered.")

            self.memory[self.node_id] = self.node_name

    class SelfNode:
        """Class to handle the node used to advertise itself

        Updates periodically to advertise itself:
        - name
        - timestamp
        - services
        - parameters
        - ? subscriptions
        """

        class NodeStatus(AxoneStruct):
            name: str
            timestamp: float
            # services: List[str]
            # parameters: Dict[str, Any]

        def __init__(self, name: str, node_id: str, **kwargs) -> None:
            self.node_name = name
            self.node_id = node_id

            self.node_status = self.NodeStatus()

            self.memory = AxoneSharedMemory(
                name=self.node_id,
                size=1024,
                struct=self.node_status,
                centralized=False,  # Only this node has write access
            )

        def advertise(self) -> None:
            """Advertise the node to the centralized memory."""
            self.memory['name'] = self.node_name
            self.memory['timestamp'] = time.time()
            # self.memory['services'] = []
            # self.memory['parameters'] = {}
            # self.memory['topics'] = []

    def __init__(self, name: str, **kwargs) -> None:
        """Initialize a node for the Axone framework."""
        self.config_file = kwargs.get("config_file", None)
        if self.config_file is not None:
            # Load the config file
            if os.path.exists(self.config_file):
                with open(self.config_file) as f:
                    try:
                        # Merge the config file with the kwargs
                        kwargs = {**kwargs, **json.load(f)}
                    except Exception:
                        raise ValueError(f"Config file {self.config_file} is not a valid json file.")
            else:
                raise FileNotFoundError(f"Config file {self.config_file} does not exist.")

        # Node parameters
        self.name = name
        self.node_id = generate_uuid(self.name)  # Generate a unique node id

        # Check for required parameters
        if self.name == "":
            raise ValueError("Node name cannot be empty.")

        # Create the centralized node
        self.centralized_node = self.CentralizedNode(self.name, self.node_id, **kwargs)
        self.centralized_node.advertise()

        # Create the self node
        self.self_node = self.SelfNode(self.name, self.node_id, **kwargs)
        self.self_node.advertise()

        # Lists of publishers, subscribers and services
        self._publishers: Dict[str, Publisher] = {}
        # self._subscriptions: Dict[str, Subscription] = {}
        # self._services_map: Dict[str, Callable] = {}

        self._last_federation_time = 0  # The time at which the memory was last federated.

    # region Common functions
    @property
    def _timestamp(self) -> int | float:
        return self.get_timestamp()

    def get_timestamp(self) -> int | float:
        """Output a formatted timestamp."""
        # TODO:Limit the range of the timestamp.
        # TODO:Currently Assume that the timestamp can not be older than 1 year.
        # TODO:This will prevent the timestamp from taking too much space in the memory.
        # Idea base the timestamp on the oldest node in the memory.
        # And reduce the floating point precision to 3 digits
        return round(
            time.time(),  # TODO: % self._timestamp_range,
            (
                self._timestamp_precision if self._timestamp_precision > 0 else None
            ),  # Note: If ndigits is None round() converts to int directly
        )

    # endregion Common functions

    # region Publisher functions

    @property
    def publishers(self) -> Dict[str, Publisher]:
        """Return the node publishers."""
        return self._publishers

    @publishers.setter
    def publishers(self, publishers: Dict[str, Publisher]) -> None:
        """Set the node publishers."""
        self._publishers = publishers
        # self.kwargs["publishers"] = publishers

    def publish_rate(
        self,
        topic: AxoneStruct,
        rate: float = 1.0,
    ) -> None:
        """Register a publisher for a topic."""
        # Create a new publisher
        self.publishers[topic.__class__.__name__] = Publisher(topic, rate)
        logging.debug(f"Registered publisher {self.publishers[-1].name} at rate {rate}.")

    def _publish_once(
        self,
        topic: AxoneStruct,
        rate: Optional[Union[int, float]] = None,
    ) -> None:
        """Publish a message once on a topic."""
        # Check if the topic is registered
        if topic.__class__.__name__ not in self.publishers:
            raise ValueError(f"Topic {topic} is not registered.")

        # Publish the message
        self.publishers[topic].publish()

    def publish_once(
        self,
        topic: AxoneStruct,
        rate: Optional[Union[int, float]] = None,
    ) -> None:
        """Publish a message on a topic."""
        self._publish_once(
            topic,
            rate,
        )

    def _publish_loop(self) -> None:
        """Function called periodically to publish messages."""
        for topic in self.publishers:
            # Check if it is time to publish
            if self._timestamp > float(1 / self.publishers[topic].rate) + self.publishers[topic].last_update:
                # Publish the message
                self._publish_once(
                    topic,
                    self.publishers[topic].rate,
                )

    # endregion

    def start(self) -> None:
        # Initialize a Thread to listen to the memory events
        # Initialize a Thread to cleanup the memory periodically
        self._server_should_run = True
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._executor.submit(self._server)

    def stop(self) -> None:
        self._server_should_run = False

    def _server(self) -> None:
        """
        Periodic server functions
        """
        while self._server_should_run:
            try:
                self._server_exec()
            except Exception as e:
                self.logger.error(
                    f"Error occured when listening for node {self.node_id}:{self.name}:\n{e}",
                    exc_info=True,
                )
                break
        logging.info("Node server stopped")

    def _server_exec(self) -> None:
        if time.time() - self._last_federation_time > 1:
            logging.debug("Update execution")
            # TODO: Group this in a dedicated function
            self._last_federation_time = time.time()

            # TODO:
            # self.self_node.update_timestamp()

        # if self.services is not None:
        #     if time.perf_counter() - self._last_services_time > self.service_server_rate:
        #         self._last_services_time = time.perf_counter()
        #         self._listen_service()

        # if self.subscriptions:
        #     self._listen_subscriptions()

        if self.publishers:
            self._publish_loop()


if __name__ == "__main__":
    setup_logger(debug=True)
    node = AxoneNode("test_node_to_central", centralized_memory_endpoint="test")
    node.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
