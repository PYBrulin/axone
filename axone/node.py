import json
import logging
import os
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional

from axone.axone_struct import AxoneStruct, standard_data_decoding, standard_data_encoding
from axone.publisher import Publisher
from axone.service_server import ServiceServer, recv_msg, send_msg
from axone.shared_memory import AxoneSharedMemory
from axone.subscriber import Subscription
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
            assert self.endpoint != self.node_id, "Memory endpoint cannot be the same as the node id."
            self.size = kwargs.get("centralized_memory_size", 1024)
            if self.endpoint == "":
                raise ValueError("Memory endpoint cannot be empty.")

            self.memory = AxoneSharedMemory(
                name=generate_uuid(self.endpoint),
                size=self.size,
                centralized=True,
            )

        def advertise(self) -> None:
            """Advertise the node to the centralized memory."""

            # Check if the node is already registered
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
            services: list[str]
            services_server_port: int | str
            # parameters: Dict[str, Any]

        def __init__(self, name: str, node_id: str, **kwargs) -> None:
            self.node_name = name
            self.node_id = node_id

            self.services_names = kwargs.get("services_names", [])  # String representation of the available services
            self.services_names = ",".join(self.services_names) if self.services_names else ""
            self.services_server_port = (
                0 if not self.services_names else kwargs.get("services_server_port", 0)
            )  # Port to access the services

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
            self.memory['services'] = self.services_names
            self.memory['services_port'] = self.services_server_port
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

        # services parameters
        self.service_server = None
        self._services = kwargs.get("services", None)
        # self._hide_services = kwargs.get("hide_services", False)
        self.setup_service_server()

        # Lists of publishers, subscribers and services
        self._publishers: Dict[str, Publisher] = {}
        self._subscriptions: Dict[str, Subscription] = {}

        # Create the "self" node
        self.self_node = self.SelfNode(
            name=self.name,
            node_id=self.node_id,
            services_names=self.service_server.services_keys if self.service_server is not None else [],
            services_server_port=self.service_server.server_port if self.service_server is not None else 0,
            **kwargs,
        )
        self.self_node.advertise()

        self._last_federation_time = 0  # The time at which the memory was last federated.

    # region Common functions
    @property
    def _timestamp(self) -> int | float:
        return time.time()
        # return self.get_timestamp()

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
                TIMESTAMP_PRECISION if TIMESTAMP_PRECISION > 0 else None
            ),  # Note: If ndigits is None round() converts to int directly
        )

    def list_nodes(self) -> list[str]:
        """
        List all the attributes in the centralized memory.
        This is really simple as the centralized memory only contains the nodes ID and names.
        """
        return self.centralized_node.memory.struct.list_instance_attributes()

    def find_node_by_name(self, name: str) -> Optional[str]:
        """
        Search a node by name.
        """
        return self.centralized_node.memory.struct.list_instance_attributes().get(generate_uuid(name), None)

    def get_node_configuration(self, name: str):
        """List the services available for a node."""
        node = self.find_node_by_name(name)
        if node is None:
            logging.debug(f"Node {name} does not exist.")
            return None

        # Connect to the requested node memory
        with AxoneSharedMemory(name=generate_uuid(node), centralized=False) as node_memory:
            # Check if the node as the attribute services
            logging.debug(f"Node {name} has the attribute services.")
            return node_memory.struct.list_instance_attributes()

    def list_node_services(self, name: str):
        """List the services available for a node."""
        node_struct = self.get_node_configuration(name)
        if node_struct is None:
            return None
        return node_struct.get("services", None)

    def get_node_services_server_port(self, name: str):
        """List the services available for a node."""
        node_struct = self.get_node_configuration(name)
        print(name, node_struct)
        if node_struct is None:
            return None
        return node_struct.get("services_port", None)

    def is_node_advertising_services(self, name: str) -> bool:
        """Check if a node is advertising services."""
        return self.list_node_services(name) is not None

    # def _is_service_advertised(self, node_id: str, service: str) -> bool:
    #     """Check if an service is advertised by a node."""
    #     return self._memory.get("__nds", {}).get(node_id, {}).get("__s", {}).get(service, {}) != {}

    # def is_service_advertised(self, node_id: str, service: str) -> bool:
    #     """Check if an service is advertised by a node."""
    #     return self._is_service_advertised(node_id, service)
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
        rate: float = -1.0,
    ) -> None:
        """Register a publisher for a topic."""
        # Create a new publisher
        topic_name = topic.__class__.__name__
        self.publishers[topic_name] = Publisher(topic, rate=rate, source=self.node_id)
        logging.debug(f"Registered publisher {topic_name} at rate {rate}.")

    def _publish_once(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
    ) -> None:
        """Publish a message once on a topic."""
        topic_name = topic.__class__.__name__
        # Check if the topic is registered
        if topic_name not in self.publishers:
            self.publishers[topic_name] = Publisher(topic, rate=rate, source=self.node_id)

        # Publish the message
        self.publishers[topic_name].publish(topic)

    def publish_once(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
    ) -> None:
        """Publish a message on a topic."""
        self._publish_once(
            topic,
            rate,
        )

    def _publish_loop(self) -> None:
        """Function called periodically to publish messages."""
        for topic in list(self.publishers.keys()):
            if self.publishers[topic].rate < 0.0:
                continue
            # Check if it is time to publish
            if self._timestamp > float(1 / self.publishers[topic].rate) + self.publishers[topic].last_update:
                # Publish the message
                self._publish_once(
                    self.publishers[topic].topic,
                    self.publishers[topic].rate,
                )

    # endregion Publisher functions

    # region Subscriber functions
    @property
    def subscriptions(self) -> Dict[str, Subscription]:
        """Return the node subscriptions dictionnary containing the topics as keys and the callbacks as values."""
        return self._subscriptions

    @subscriptions.setter
    def subscriptions(self, subscriptions: Dict[str, Subscription]) -> None:
        """Set the node subscriptions."""
        self._subscriptions = subscriptions
        # self.kwargs["subscriptions"] = subscriptions

    def subscribe(self, topic_name: str, callback: Callable) -> None:
        """Subscribe to a topic."""
        # Add the callback to the list of callbacks for this topic
        if topic_name not in self.subscriptions:
            # Create a new subscription
            self.subscriptions[topic_name] = Subscription(topic_name)
            self.subscriptions[topic_name].callbacks.append(callback)
            logging.debug(f"Registering subscription {topic_name} for node {self.node_id}:{self.name}.")
        else:
            # Add the callback to the existing subscription
            self.subscriptions[topic_name].callbacks.append(callback)
            logging.debug(f"Adding callback to subscription {topic_name} for node {self.node_id}:{self.name}.")

    def _listen_subscriptions(self) -> None:
        """Function called periodically to listen to topics."""
        for topic_name in self.subscriptions:
            # Do not listen to topics that need to be requested manually
            if self.subscriptions[topic_name].rate <= 0.0:
                continue

            # Check if it is time to listen
            # TODO: Limit rate if the topic is not published
            if time.time() - self.subscriptions[topic_name].last_timestamp > float(1 / self.subscriptions[topic_name].rate):
                topic_struct = self._listen_for_topic(topic_name)
                if topic_struct is not None:
                    logging.debug(f"Received topic {topic_name}.")
                    self.subscriptions[topic_name].call(topic_struct)

    def _listen_for_topic(self, topic_name: str) -> AxoneStruct:
        """Listen to a topic."""
        if topic_name not in self.subscriptions:
            return None
        self.subscriptions[topic_name].subscribe()
        return self.subscriptions[topic_name]._topic

    def _listen_once(self, topic: str) -> AxoneStruct:
        """Listen to a topic once."""
        sub = Subscription(topic)
        sub.subscribe()
        return sub._topic

    def listen_once(self, topic: str) -> AxoneStruct:
        """Listen to a topic once."""
        return self._listen_once(topic)

    # endregion Subscriber functions

    # region Services functions
    @property
    def services(self) -> Dict[str, Callable]:
        """Return the node services."""
        return self._services

    def setup_service_server(self) -> None:
        """Setup the service server."""
        if self.services is None:
            return

        # Create and start the service server
        self.service_server = ServiceServer(
            services=self.services,
            node_uuid=self.node_id,
        )
        logging.info(f"Starting service server for node {self.node_id}:{self.name} with {len(self.services)} services.")

    def _call_service(
        self,
        dest_node_id: Optional[str] = None,
        dest_node_name: Optional[str] = None,
        service_name: str = None,
        # answer: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Call an service on a node."""
        # Check if the service is available
        # We need to check if the node is available first, otherwise the service
        #  buffer will get congested with inexistent service calls
        # Note: This fnction used to check if the service was registered on the
        #  destination node. However, it is now possible to hide services from
        #  the memory. Therefore, the destination node will be the only one
        #  responsible for checking if the service is available or not.

        if dest_node_id is None and dest_node_name is None:
            self.logger.error("Either dest_node_id or dest_node_name must be specified.")
            return

        if dest_node_id is None and dest_node_name is not None:
            dest_node_id = generate_uuid(dest_node_name)

        if service_name is None:
            self.logger.error("Service name must be specified.")
            return

        services_advertised = self.list_node_services(dest_node_name)
        if services_advertised is None:
            self.logger.error(f"Node {dest_node_name} is not advertising any services.")
            return

        if service_name not in services_advertised:
            # service is not available
            # No need to call the service
            self.logger.warning(
                f"No service with name {service_name} has been advertised by "
                + f"node {dest_node_id} to call. However, the node might "
                + "be hiding its services. The call will be made anyway."
            )

        server_port = self.get_node_services_server_port(dest_node_name)

        if sys.platform != 'win32':
            family = socket.AF_UNIX
            server_address = f'/tmp/{server_port}_socket'
        else:
            family = socket.AF_INET
            input_port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
            if input_port == 0:
                raise ValueError("Please provide a port number")
            server_address = ('localhost', input_port)
        try:
            # Create a socket
            sock = socket.socket(family, socket.SOCK_STREAM)

            # Connect the socket to the port where the server is listening
            logging.info(f'Connecting to {server_address}')
            sock.connect(server_address)
        except OSError as err:
            logging.error(f'Socket error: {err}')
            sock.close()
            return

        # Encode the message
        message = standard_data_encoding(
            func=service_name,
            **kwargs,
        )

        logging.info(f'sending {message!r}')
        send_msg(sock, message)

        # Look for the response
        data = recv_msg(sock)
        logging.info(f'received {standard_data_decoding(data)!r}')

        self.logger.debug(
            f"Called service {service_name} on node {dest_node_id}.",
        )

    def call_service(
        self,
        dest_node_id: Optional[str] = None,
        dest_node_name: Optional[str] = None,
        service_name: Optional[str] = None,
        # answer: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Call an service on a node."""
        self._call_service(
            dest_node_id=dest_node_id,
            dest_node_name=dest_node_name,
            service_name=service_name,
            # answer=answer,
            **kwargs,
        )

    # endregion Services functions

    def start(self) -> None:
        # Initialize a Thread to listen to the memory events
        # Initialize a Thread to cleanup the memory periodically
        self._server_should_run = True
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._executor.submit(self._server)

        if self.services is not None:
            self.service_server.start()

    def stop(self) -> None:
        self._server_should_run = False
        if self.service_server is not None:
            self.service_server.stop()

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
            # logging.debug("Update execution")
            # TODO: Group this in a dedicated function
            self._last_federation_time = time.time()

            # TODO:
            # self.self_node.update_timestamp()

        # if self.services is not None:
        #     if time.time() - self._last_services_time > self.service_server_rate:
        #         self._last_services_time = time.time()
        #         self._listen_service()

        if self.subscriptions:
            self._listen_subscriptions()

        if self.publishers:
            self._publish_loop()
