import asyncio
import json
import logging
import os
import socket
import sys
import threading
import time
from collections.abc import Callable

import netifaces

from axone.axone_shm import CentralizedNode, SelfNode
from axone.axone_struct import AxoneStruct, standard_data_decoding, standard_data_encoding
from axone.common import find_free_port, generate_uuid, timeit_if_debug
from axone.encryption import generate_encryption_key, load_encryption_key
from axone.enums import Method
from axone.publisher import Publisher
from axone.service_server import ServiceServer, recv_msg, send_msg
from axone.shared_memory import AxoneSharedMemory
from axone.subscriber import Subscription
from axone.zeroconf_node import ZeroconfNode


class AxoneNode:
    logger = logging.getLogger(__name__)

    def __init__(self, name: str, **kwargs) -> None:
        """Initialize a node for the Axone framework.

        Args:
            TODO
        """
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

        # Try to load the encryption key if specified in the config file or kwargs
        if "encryption_key_path" in kwargs and kwargs["encryption_key_path"] is not None:
            encryption_key_path = kwargs["encryption_key_path"]
            if os.path.exists(encryption_key_path):
                kwargs["encryption_key"] = load_encryption_key(encryption_key_path)
            else:
                logging.error(f"Encryption key specified but file {encryption_key_path} does not exist. Creating one now.")
                kwargs["encryption_key"] = (
                    generate_encryption_key()
                )  # Generate a new encryption key and save it to the default location
        self.encryption_key: str | None = kwargs.get("encryption_key", None)

        # Node parameters
        self.name = name
        self.node_id = generate_uuid(self.name)  # Generate a unique node id
        self.default_method: Method = kwargs.get("method", Method.SOCKET)
        if self.default_method not in Method:
            # Try to understand what the value means.
            # We accept passing strings. Allowed strings are:
            #   ["socket", "shared_memory", "shm"]
            if isinstance(self.default_method, str):
                logging.warning("Trying to check the value of the 'method'")
                match self.default_method:
                    case "socket":
                        self.default_method = Method.SOCKET
                    case "shm" | "shared_memory":
                        self.default_method = Method.SHARED_MEMORY
                    case _:
                        logging.error(
                            f"Invalid method: '{self.default_method}'.\n"
                            + "When setting the 'method' argument using a string, "
                            + "accepted values are: ['socket', 'shared_memory', 'shm']\n"
                            + "Using Method.SOCKET instead."
                        )
                        self.default_method = Method.SOCKET
            else:
                logging.error("Unsupported method. Using Method.SOCKET instead.")
                self.default_method = Method.SOCKET
        else:
            # Or integers which correspond to the enum value.
            if isinstance(self.default_method, int):
                try:
                    self.default_method = Method.from_value(self.default_method)
                except ValueError:
                    logging.error(
                        f"Invalid method value: '{self.default_method}'.\n"
                        + "When setting the 'method' argument using an integer, "
                        + "accepted values are: {0:'socket', 1:'shared_memory'}\n"
                        + "Using Method.SOCKET instead."
                    )
                    self.default_method = Method.SOCKET
            # else...
            # Already a member of Method.

        # if self.default_method is Method.SHARED_MEMORY:
        #     raise NotImplementedError("Regression. Shared Memory are not supported anymore at the moment.")

        # Default publisher parameters
        self.default_publisher_interface = kwargs.get("default_publisher_interface", "lo")
        if self.default_publisher_interface not in netifaces.interfaces():
            logging.error(f"Network interface '{self.default_publisher_interface}' does not exist. Defaulting to 'lo'")
            self.default_publisher_interface = "lo"
        self.default_publisher_address = kwargs.get(
            "default_publisher_address",
            "224.1.1.1" if self.default_publisher_interface != "lo" else "239.255.0.1",
        )
        self.default_publisher_port_range = kwargs.get("default_publisher_port_range", (40000, 45000))

        # Check for required parameters
        if self.name == "":
            raise ValueError("Node name cannot be empty.")

        # Services parameters
        self.service_server = None
        self.service_port = kwargs.get("port", find_free_port())
        self.hide_services = kwargs.get("hide_services", False)
        self._services = kwargs.get("services", None)
        self.setup_service_server()

        if self.default_method is Method.SOCKET:
            # Zeroconf parameters
            self.zeroconf_node = ZeroconfNode(
                name=self.name,
                node_id=self.node_id,
                port=self.service_port,
                interface=self.default_publisher_interface,
                **kwargs,
            )
            self.zeroconf_node.advertise()
        elif self.default_method is Method.SHARED_MEMORY:
            # Create the centralized node
            self.centralized_node = CentralizedNode(self.name, self.node_id, **kwargs)
            self.centralized_node.advertise()

            # Create the "self" node
            self.self_node = SelfNode(
                name=self.name,
                node_id=self.node_id,
                # services_names=self.service_server.services_keys if self.service_server is not None else [],
                # services_server_port=self.service_server.server_port if self.service_server is not None else 0,
                **kwargs,
            )
            self.self_node.advertise()

        # Lists of publishers, subscribers and services
        self._publishers: dict[str, Publisher] = {}
        self._subscriptions: dict[str, Subscription] = {}

    # region Common functions

    @property
    def _timestamp(self) -> int | float:
        return time.time()

    def list_nodes(self) -> list[str]:
        return self._list_nodes()

    def _list_nodes(self) -> list[str]:
        """List all the nodes discovered using zeroconf."""
        if self.default_method is Method.SOCKET:
            return list(self.zeroconf_node.discovered_nodes.keys())
        elif self.default_method is Method.SHARED_MEMORY:
            return self.centralized_node.memory.struct.list_instance_attributes()

    def dict_nodes(self) -> list[str]:
        return self._dict_nodes()

    def _dict_nodes(self) -> list[str]:
        """List all the nodes discovered using zeroconf."""
        ret = dict()
        if self.default_method is Method.SOCKET:
            for node, info in self.zeroconf_node.discovered_nodes.items():
                ret[node.split(info.type, 1)[0][:-1]] = info.decoded_properties
        elif self.default_method is Method.SHARED_MEMORY:
            raise NotImplementedError("SHM")
        return ret

    def find_node_by_name(self, name: str) -> str | None:
        return self._find_node_by_name(name=name)

    def _find_node_by_name(self, name: str) -> str | None:
        """Search a node by name"""
        if self.default_method is Method.SOCKET:
            for node_name, info in self.zeroconf_node.discovered_nodes.items():
                if node_name.split(info.type, 1)[0][:-1] == name:
                    return info.decoded_properties["node_id"]
        elif self.default_method is Method.SHARED_MEMORY:
            return self.centralized_node.memory.struct.list_instance_attributes().get(generate_uuid(name), None)
        return None

    def get_node_configuration(self, name: str, method: Method | None = None):
        return self._get_node_configuration(name=name, method=method)

    def _get_node_configuration(self, name: str, method: Method | None = None):
        """Get the configuration of a node."""
        method = method or self.default_method

        if method is Method.SOCKET:
            for node_name, info in self.zeroconf_node.discovered_nodes.items():
                if node_name.split(info.type, 1)[0][:-1] == name:
                    return info.decoded_properties
            return None
        elif method is Method.SHARED_MEMORY:
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
        return self._list_node_services(name=name)

    def _list_node_services(self, name: str):
        """List the services available for a node."""
        node_struct = self._get_node_configuration(name)
        if node_struct is None:
            # logging.error(f"Could not fetch node struct for {name}", exc_info=True)
            return None
        if self.default_method is Method.SOCKET:
            services = node_struct.get("services", None)
            if services is not None:
                return services.split(',')
        elif self.default_method is Method.SHARED_MEMORY:
            return node_struct.get("services", None)
        return None

    def get_node_services_server_port(self, name: str):
        return self._get_node_services_server_port(name=name)

    def _get_node_services_server_port(self, name: str):
        """List the services available for a node."""
        if self.default_method is Method.SOCKET:
            for node_name, info in self.zeroconf_node.discovered_nodes.items():
                if node_name.split(info.type, 1)[0][:-1] == name:
                    return info.port
        elif self.default_method is Method.SHARED_MEMORY:
            node_struct = self._get_node_configuration(name)
            if node_struct is None:
                return None
            return node_struct.get("services_port", None)
            raise NotImplementedError("SHM")
        return None

    def is_node_advertising_services(self, name: str) -> bool:
        return self._is_node_advertising_services(name=name)

    def _is_node_advertising_services(self, name: str) -> bool:
        """Check if a node is advertising services."""
        services = self._list_node_services(name)
        return services is not None and services != ""

    def get_node_topics(self, name: str) -> list[str]:
        return self._get_node_topics(name=name)

    def _get_node_topics(self, name: str) -> list[str]:
        """List the topics available for a node."""
        node_struct = self._get_node_configuration(name)
        if node_struct is None:
            # logging.error(f"Could not fetch node struct for {name}", exc_info=True)
            return []
        return node_struct.get("topics", [])

    # endregion Common functions

    # region Publisher functions

    @property
    def publishers(self) -> dict[str, Publisher]:
        """Return the node publishers."""
        return self._publishers

    @publishers.setter
    def publishers(self, publishers: dict[str, Publisher]) -> None:
        """Set the node publishers."""
        self._publishers = publishers

    def publish_rate(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
        method: Method | None = None,
        publisher_interface: str | None = None,
        publisher_address: str | None = None,
        publisher_port: int = 0,
        publisher_port_range: tuple | None = None,
    ) -> None:
        """Register a publisher for a topic."""
        method = method or self.default_method

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
            encryption_key=self.encryption_key,
        )
        logging.debug(f"Registered publisher {topic_name} at rate {rate} using {method}.")
        if method is Method.SOCKET:
            self.update_zeroconf_topics()
        elif method is Method.SHARED_MEMORY:
            if topic_name not in self.publishers:  # Check if the topic is registered
                self.self_node.add_topic(topic_name)
        asyncio.run_coroutine_threadsafe(self.update_publishers(), self._loop)

    def _publish_once(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
        method: Method | None = None,
        publisher_interface: str | None = None,
        publisher_address: str | None = None,
        publisher_port: int = 0,
        publisher_port_range: tuple | None = None,
    ) -> None:
        """Publish a message once on a topic."""
        method = method or self.default_method

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
                encryption_key=self.encryption_key,
            )
            if method is Method.SOCKET:
                self.update_zeroconf_topics()
            elif method is Method.SHARED_MEMORY:
                self.self_node.add_topic(topic_name)

        # Publish the message
        self.publishers[topic_name].publish(topic)

    @timeit_if_debug
    def publish_once(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
        method: Method | None = None,
        publisher_interface: str | None = None,
        publisher_address: str | None = None,
        publisher_port: int = 0,
        publisher_port_range: tuple | None = None,
    ) -> None:
        """Publish a message on a topic."""
        method = method or self.default_method

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
        """Function called periodically to publish messages.
        Used by the NodeProcess variant."""
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
        self.zeroconf_node.update_topics(published_topics=topics)

    # endregion Publisher functions

    # region Subscriber functions
    @property
    def subscriptions(self) -> dict[str, Subscription]:
        """Return the node subscriptions dictionary containing the topics as keys and the callbacks as values."""
        return self._subscriptions

    @subscriptions.setter
    def subscriptions(self, subscriptions: dict[str, Subscription]) -> None:
        """Set the node subscriptions."""
        self._subscriptions = subscriptions

    def subscribe(self, topic_name: str, callback: Callable, method: Method | None = None) -> None:
        """Subscribe to a topic."""
        method = method or self.default_method
        return self._subscribe(topic_name, callback, method)

    def _subscribe(self, topic_name: str, callback: Callable, method: Method | None = None) -> None:
        method = method or self.default_method
        # Add the callback to the list of callbacks for this topic
        if topic_name not in list(self.subscriptions):
            # Create a new subscription
            self.subscriptions[topic_name] = Subscription(topic_name, method=method, encryption_key=self.encryption_key)
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

    def _listen_once(self, topic: str, method: Method | None = None) -> AxoneStruct:
        """Listen to a topic once."""
        method = method or self.default_method
        if topic not in self.subscriptions:
            sub = Subscription(topic, method=method, encryption_key=self.encryption_key)
            self.subscriptions[topic] = sub
        else:
            sub = self.subscriptions[topic]
        sub.subscribe()
        return sub._topic

    @timeit_if_debug
    def listen_once(self, topic: str, method: Method | None = None) -> AxoneStruct:
        """Listen to a topic once."""
        method = method or self.default_method
        return self._listen_once(topic, method)

    # endregion Subscriber functions

    # region Services functions

    @property
    def services(self) -> dict[str, Callable]:
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
            method=self.default_method,
            service_interface=self.default_publisher_interface,
            server_port=self.service_port,
        )
        # logging.info(f"Starting service server for node {self.node_id}:{self.name} with {len(self.services)} services.")

    def _call_service(
        self,
        dest_node_id: str | None = None,
        dest_node_name: str | None = None,
        service_name: str = None,
        answer_callback: Callable | None = None,
        **kwargs,
    ):
        """Call a service on a node."""
        if dest_node_id is None and dest_node_name is None:
            self.logger.error("Either dest_node_id or dest_node_name must be specified.")
            return

        if dest_node_id is None and dest_node_name is not None:
            dest_node_id = generate_uuid(dest_node_name)

        if service_name is None:
            self.logger.error("Service name must be specified.")
            return

        services_advertised = self._list_node_services(dest_node_name)
        if services_advertised is None:
            self.logger.error(f"Node {dest_node_name} is not advertising any services.")
            return

        if service_name not in services_advertised:
            self.logger.warning(
                f"No service with name {service_name} has been advertised by "
                + f"node {dest_node_id} to call. However, the node might "
                + "be hiding its services. The call will be made anyway."
            )

        server_port = self._get_node_services_server_port(dest_node_name)

        if self.default_method is Method.SHARED_MEMORY and sys.platform != 'win32':
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

        # Encode and send the message
        message = standard_data_encoding(func=service_name, **kwargs)
        logging.debug(f'sending {message!r}')
        send_msg(sock, message)

        # Look for the response
        data = recv_msg(sock)
        decoded_data = standard_data_decoding(data, **kwargs)
        logging.debug(f'received {decoded_data!r}')

        if answer_callback is not None and callable(answer_callback):
            try:
                answer_callback(**decoded_data.get("out"))
            except Exception as e:
                logging.error(
                    "\n".join(
                        [
                            f"Failed to use callback '{answer_callback.__name__}' using decoded data '{decoded_data}'.",
                            "You should check number of arguments returned or their types.",
                            f"Error: {e}",
                        ]
                    ),
                    exc_info=True,
                )

        self.logger.debug(
            f"Called service {service_name} on node {dest_node_id}.",
        )
        return decoded_data

    def call_service(
        self,
        dest_node_id: str | None = None,
        dest_node_name: str | None = None,
        service_name: str | None = None,
        answer_callback: str | None = None,
        **kwargs,
    ) -> None:
        """Call a service on a node."""
        self._call_service(
            dest_node_id=dest_node_id,
            dest_node_name=dest_node_name,
            service_name=service_name,
            answer_callback=answer_callback,
            **kwargs,
        )

    # endregion Services functions

    def start(self) -> None:
        """
        Start the node server using asyncio.
        """
        logging.info(f"Starting node server for {self.node_id}:{self.name}.")
        self._server_should_run = True
        if self.service_server is not None:
            self.service_server.start()  # Start service server
        self.running_tasks = {}  # Clear running tasks (topics being published)

        # Create and run the event loop in a separate thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._executor = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._executor.start()

        # Schedule periodic tasks directly
        asyncio.run_coroutine_threadsafe(self.update_publishers(), self._loop)

    def stop(self) -> None:
        """
        Stop the node server and clean up resources.
        """
        self._server_should_run = False

        # Stop the service server
        if self.service_server is not None:
            self.service_server.stop()

        # Cancel all running tasks
        for task in self.running_tasks.values():
            task.cancel()
        self.running_tasks.clear()

        # Cleanup the publishers and subscribers of this node
        for publisher in self.publishers.values():
            publisher.stop()
        for subscription in self.subscriptions.values():
            subscription.stop()

        if self.default_method is Method.SOCKET:
            # Stop advertising the node
            self.zeroconf_node.stop_advertising()
        elif self.default_method is Method.SHARED_MEMORY:
            # Unregister the node from the centralized memory
            self.centralized_node.memory[self.node_id] = None

            # Unregister the node from the self memory
            self.self_node.memory.cleanup()

        # Stop the event loop
        if hasattr(self, '_loop'):
            # Schedule loop.stop() from the main thread
            self._loop.call_soon_threadsafe(self._loop.stop)

        # Wait for the thread to finish
        if hasattr(self, '_executor'):
            self._executor.join()

        # Close the event loop
        if hasattr(self, '_loop') and not self._loop.is_closed():
            self._loop.close()

    async def update_publishers(self) -> None:
        """
        Update the publisher list and refresh tasks for new or removed publishers.
        """
        logging.debug("Updating publishers...")

        # Add new publishers
        for topic_name, publisher in self.publishers.items():
            if topic_name not in self.running_tasks and publisher.rate > 0.0:
                # Schedule a new publisher task
                self.running_tasks[topic_name] = asyncio.create_task(self._schedule_publisher(topic_name, publisher))
                self.logger.info(f"Started publishing task for topic {topic_name}.")

        # Remove tasks for publishers that no longer exist
        removed_publishers = [name for name in self.running_tasks if name not in self.publishers]
        for name in removed_publishers:
            task = self.running_tasks.pop(name)
            task.cancel()
            self.logger.info(f"Stopped publishing task for topic {name}.")

    async def _schedule_publisher(self, topic_name: str, publisher: Publisher) -> None:
        """
        Periodically publish messages for a single publisher.
        """
        while self._server_should_run:
            try:
                current_time = self._timestamp
                if current_time > float(1 / publisher.rate) + publisher.last_update:
                    logging.info(f"Publishing topic {topic_name} at rate {publisher.rate}.")
                    self._publish_once(publisher.topic, publisher.rate)

                # Wait for the next interval
                await asyncio.sleep(1 / publisher.rate)

            except Exception as e:
                self.logger.error(
                    f"Error occurred while publishing topic {topic_name}:\n{e}",
                    exc_info=True,
                )
                break
