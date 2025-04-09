import json
import logging
import os
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional

import netifaces
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
from zeroconf._exceptions import NonUniqueNameException

from axone.axone_struct import AxoneStruct, standard_data_decoding, standard_data_encoding
from axone.enums import Method
from axone.publisher import Publisher
from axone.service_server import ServiceServer, recv_msg, send_msg
from axone.shared_memory import AxoneSharedMemory
from axone.subscriber import Subscription
from axone.utils import find_free_port, generate_uuid, timeit_if_debug

DEFAULT_TIMEOUT = 5
MAX_RETRIES = 10
TIMESTAMP_PRECISION = 0
TIMESTAMP_RANGE = 60 * 60 * 24 * 365  # 1 year


class ZeroconfListener(ServiceListener):
    def __init__(self):
        self.nodes = {}

    def remove_service(self, zeroconf, type, name):
        logging.info(f"Service {name} removed")
        if name in self.nodes:
            del self.nodes[name]

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            logging.info(f"Service {name} added, service info: {info}")
            self.nodes[name] = info

    def update_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            logging.info(f"Service {name} updated, service info: {info}")
            self.nodes[name] = info


class ZeroconfNode:
    def __init__(self, name: str, node_id: str, port: int, interface: str = "lo", **kwargs) -> None:
        self.node_name = name
        self.node_id = node_id
        self.service_port = port
        self.zeroconf = Zeroconf()
        self.listener = ZeroconfListener()
        self.service_type = "_axone._tcp.local."
        self.service_name = f"{self.node_name}.{self.service_type}"
        self.interface = interface
        self.topics = kwargs.get("topics", [])
        new_ip_address = self._get_ip_address(self.interface)
        self.info = ServiceInfo(
            self.service_type,
            self.service_name,
            addresses=[socket.inet_aton(new_ip_address)],
            port=self.service_port,
            properties={"node_id": self.node_id, "topics": ",".join(self.topics)},
        )

    def advertise(self) -> None:
        """Advertise the node using zeroconf."""
        try:
            self.zeroconf.register_service(self.info)
            logging.info(f"Node {self.node_name} advertised on zeroconf")
        except NonUniqueNameException:
            logging.warning(f"Service name {self.service_name} is not unique. Trying a new name.")
            self._handle_non_unique_name_exception()

    def _get_ip_address(self, interface: str) -> str:
        """Get the IP address of a specific network interface."""
        logging.debug(f"Getting IP address for interface {interface}")
        addresses = netifaces.ifaddresses(interface)
        logging.debug(f"Addresses: {addresses}")
        return addresses[netifaces.AF_INET][0]['addr']

    def _handle_non_unique_name_exception(self) -> None:
        """Handle NonUniqueNameException by modifying the service name to make it unique."""
        counter = 1
        while True:
            new_service_name = f"{self.node_name}-{counter}.{self.service_type}"
            new_ip_address = self._get_ip_address(self.interface)
            new_info = ServiceInfo(
                self.service_type,
                new_service_name,
                addresses=[socket.inet_aton(new_ip_address)],
                port=self.service_port,
                properties={"node_id": self.node_id, "topics": ",".join(self.topics)},
            )
            try:
                self.zeroconf.register_service(new_info)
                self.service_name = new_service_name
                self.info = new_info
                logging.info(f"Node {self.node_name} advertised with new name {self.service_name} on zeroconf")
                break
            except NonUniqueNameException:
                counter += 1

    def stop_advertising(self) -> None:
        """Stop advertising the node using zeroconf."""
        self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()
        logging.info(f"Node {self.node_name} stopped advertising on zeroconf")

    def update_topics(self, topics: list[str]) -> None:
        """Update the topics in the zeroconf properties."""
        self.topics = topics
        self.info.properties["topics"] = ",".join(self.topics).encode("utf-8")
        logging.info(f"Updating service with new topics: {self.info.properties['topics']}")
        self.zeroconf.update_service(self.info)
        logging.info(f"Updated topics for node {self.node_name} on zeroconf: {self.topics}")

    def discover_nodes(self) -> Dict[str, ServiceInfo]:
        """Discover nodes using zeroconf."""
        ServiceBrowser(self.zeroconf, self.service_type, self.listener)
        time.sleep(2)  # Wait for discovery
        return self.listener.nodes


class AxoneNode:
    logger = logging.getLogger(__name__)

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

        # Default publisher parameters
        self.default_publisher_interface = kwargs.get("default_publisher_interface", "lo")
        if self.default_publisher_interface not in netifaces.interfaces():
            logging.error(f"Network interface '{self.default_publisher_interface}' does not exist. Defaulting to 'lo'")
            self.default_publisher_interface = "lo"
        self.default_publisher_address = kwargs.get("default_publisher_address", "224.1.1.1")
        self.default_publisher_port_range = kwargs.get("default_publisher_port_range", (40000, 45000))

        # Check for required parameters
        if self.name == "":
            raise ValueError("Node name cannot be empty.")

        # Zeroconf parameters
        self.service_port = kwargs.get("port", find_free_port())

        # Create the zeroconf node
        self.zeroconf_node = ZeroconfNode(
            name=self.name,
            node_id=self.node_id,
            port=self.service_port,
            interface=self.default_publisher_interface,
            **kwargs,
        )
        self.zeroconf_node.advertise()

        # Services parameters
        self.service_server = None
        self._services = kwargs.get("services", None)
        self.setup_service_server()

        # Lists of publishers, subscribers and services
        self._publishers: Dict[str, Publisher] = {}
        self._subscriptions: Dict[str, Subscription] = {}

    # region Common functions

    @property
    def _timestamp(self) -> int | float:
        return time.time()

    def list_nodes(self) -> list[str]:
        """List all the nodes discovered using zeroconf."""
        nodes = self.zeroconf_node.discover_nodes()
        return list(nodes.keys())

    def find_node_by_name(self, name: str) -> Optional[str]:
        """Search a node by name"""
        nodes = self.zeroconf_node.discover_nodes()
        for node_name, info in nodes.items():
            if node_name == name:
                return info.properties.get("node_id")
        return None

    def get_node_configuration(self, name: str):
        """Get the configuration of a node."""
        node_id = self.find_node_by_name(name)
        if node_id is None:
            logging.debug(f"Node {name} does not exist.")
            return None

        # Connect to the requested node memory
        try:
            with AxoneSharedMemory(name=node_id, centralized=False) as node_memory:
                logging.debug(f"Node {name} has the attribute services.")
                return node_memory.struct.list_instance_attributes()
        except ValueError:
            logging.error(f"Node {name} does not have a memory. It might be offline.")
            return None

    def list_node_services(self, name: str):
        """List the services available for a node."""
        node_struct = self.get_node_configuration(name)
        if node_struct is None:
            return None
        return node_struct.get("services", None)

    def get_node_services_server_port(self, name: str):
        """List the services available for a node."""
        node_struct = self.get_node_configuration(name)
        if node_struct is None:
            return None
        return node_struct.get("services_port", None)

    def is_node_advertising_services(self, name: str) -> bool:
        """Check if a node is advertising services."""
        services = self.list_node_services(name)
        return services is not None and services != ""

    def get_node_topics(self, name: str) -> list[str]:
        """List the topics available for a node."""
        node_struct = self.get_node_configuration(name)
        if node_struct is None:
            return []
        return node_struct.get("topics", [])

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

    def publish_rate(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
        method: Method = Method.SOCKET,
        publisher_interface: Optional[str] = None,
        publisher_address: Optional[str] = None,
        publisher_port: int = 0,
        publisher_port_range: Optional[tuple] = None,
    ) -> None:
        """Register a publisher for a topic."""

        # Use instance variables if parameters are None
        if publisher_interface is None:
            publisher_interface = self.default_publisher_interface
        if publisher_address is None:
            publisher_address = self.default_publisher_address
        if publisher_port_range is None:
            publisher_port_range = self.default_publisher_port_range

        # Create a new publisher
        topic_name = topic.__class__.__name__
        self.publishers[topic_name] = Publisher(
            topic,
            rate=rate,
            source=self.node_id,
            method=method,
            publisher_interface=publisher_interface,
            publisher_address=publisher_address,
            publisher_port=publisher_port,
            publisher_port_range=publisher_port_range,
        )
        logging.debug(f"Registered publisher {topic_name} at rate {rate} using {method}.")
        self.update_zeroconf_topics()

    def _publish_once(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
        method: Method = Method.SOCKET,
        publisher_interface: Optional[str] = None,
        publisher_address: Optional[str] = None,
        publisher_port: int = 0,
        publisher_port_range: Optional[tuple] = None,
    ) -> None:
        """Publish a message once on a topic."""

        # Use instance variables if parameters are None
        if publisher_interface is None:
            publisher_interface = self.default_publisher_interface
        if publisher_address is None:
            publisher_address = self.default_publisher_address
        if publisher_port_range is None:
            publisher_port_range = self.default_publisher_port_range

        topic_name = topic.__class__.__name__
        # Check if the topic is registered
        if topic_name not in self.publishers:
            self.publishers[topic_name] = Publisher(
                topic,
                rate=rate,
                source=self.node_id,
                method=method,
                publisher_interface=publisher_interface,
                publisher_address=publisher_address,
                publisher_port=publisher_port,
                publisher_port_range=publisher_port_range,
            )
            self.update_zeroconf_topics()

        # Publish the message
        self.publishers[topic_name].publish(topic)

    @timeit_if_debug
    def publish_once(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
        method: Method = Method.SOCKET,
        publisher_interface: Optional[str] = None,
        publisher_address: Optional[str] = None,
        publisher_port: int = 0,
        publisher_port_range: Optional[tuple] = None,
    ) -> None:
        """Publish a message on a topic."""

        # Use instance variables if parameters are None
        if publisher_interface is None:
            publisher_interface = self.default_publisher_interface
        if publisher_address is None:
            publisher_address = self.default_publisher_address
        if publisher_port_range is None:
            publisher_port_range = self.default_publisher_port_range

        self._publish_once(
            topic,
            rate,
            method,
            publisher_interface=publisher_interface,
            publisher_address=publisher_address,
            publisher_port=publisher_port,
            publisher_port_range=publisher_port_range,
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

    def update_zeroconf_topics(self) -> None:
        """Update the topics in the zeroconf properties."""
        topics = {name: pub._publisher_port for name, pub in self.publishers.items()}
        self.zeroconf_node.update_topics(topics)

    # endregion Publisher functions

    # region Subscriber functions
    @property
    def subscriptions(self) -> Dict[str, Subscription]:
        """Return the node subscriptions dictionary containing the topics as keys and the callbacks as values."""
        return self._subscriptions

    @subscriptions.setter
    def subscriptions(self, subscriptions: Dict[str, Subscription]) -> None:
        """Set the node subscriptions."""
        self._subscriptions = subscriptions

    def subscribe(self, topic_name: str, callback: Callable, method: Method = Method.SOCKET) -> None:
        """Subscribe to a topic."""
        return self._subscribe(topic_name, callback, method)

    def _subscribe(self, topic_name: str, callback: Callable, method: Method = Method.SOCKET) -> None:
        # Add the callback to the list of callbacks for this topic
        if topic_name not in list(self.subscriptions):
            # Create a new subscription
            self.subscriptions[topic_name] = Subscription(topic_name, method=method)
            self.subscriptions[topic_name].callbacks.append(callback)
            logging.info(f"Registering subscription {topic_name} for node {self.node_id}:{self.name} using {method}.")
        else:
            # Add the callback to the existing subscription
            self.subscriptions[topic_name].callbacks.append(callback)
            logging.info(f"Adding callback to subscription {topic_name} for node {self.node_id}:{self.name}.")

    def _listen_subscriptions(self) -> None:
        """Function called periodically to listen to topics."""
        for topic_name in list(self.subscriptions):
            # Do not listen to topics that need to be requested manually
            if self.subscriptions[topic_name].rate <= 0.0:
                continue

            # Check if it is time to listen
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

    def _listen_once(self, topic: str, method: Method = Method.SOCKET) -> AxoneStruct:
        """Listen to a topic once."""
        if topic not in self.subscriptions:
            sub = Subscription(topic, method=method)
            self.subscriptions[topic] = sub
            sub.subscribe()
        else:
            sub = self.subscriptions[topic]
        return sub._topic

    @timeit_if_debug
    def listen_once(self, topic: str, method: Method = Method.SOCKET) -> AxoneStruct:
        """Listen to a topic once."""
        return self._listen_once(topic, method)

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
        **kwargs,
    ) -> None:
        """Call a service on a node."""
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
            input_port = int(server_port) if server_port is not None else 0
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
        **kwargs,
    ) -> None:
        """Call a service on a node."""
        self._call_service(
            dest_node_id=dest_node_id,
            dest_node_name=dest_node_name,
            service_name=service_name,
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

        # Wait for the server to stop
        self._executor.shutdown(wait=True)

        # Stop advertising the node
        self.zeroconf_node.stop_advertising()

        # Cleanup the publishers and subscribers of this node
        for publisher in self.publishers.values():
            publisher.stop()
        for subscription in self.subscriptions.values():
            subscription.stop()

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
        # if self.subscriptions:
        #     self._listen_subscriptions()

        if self.publishers:
            self._publish_loop()
