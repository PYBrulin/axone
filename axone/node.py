import json
import logging
import os
import random
import string
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Union

from .shared_memory_dict import SharedMemoryDict

DEFAULT_TIMEOUT = 5
MAX_RETRIES = 10
TIMESTAMP_PRECISION = 3
TIMESTAMP_RANGE = 60 * 60 * 24 * 365  # 1 year


class Node:
    logger = logging.getLogger(__name__)

    def __init__(self, name: str, **kwargs) -> None:
        """Initialize a node for the Axone framework.

        Args:
            name (str): The name of the node. Defaults to "".
            memory_endpoint (str, optional): The name of the shared memory. Defaults to "".
            memory_size (Optional[int], optional): The size of the shared memory. Defaults to None.
            parameters (Optional[Dict[str, Any]], optional): The parameters of the node. Defaults to None.
            services (Optional[Dict[str, Any]], optional): The services of the node. Defaults to None.
            config_file (Optional[str], optional): The path to a config file which Can be used to load a common set of
                parameters for all nodes on the same system from a json file. Defaults to None.
            service_server_rate (float, optional): The rate at which the service server is checked for new services.
                Defaults to 10Hz.
            hide_services (bool, optional): Whether to advertise or hide the services from the memory.
                Useful if the full system architecture is known in advance. Defaults to False.
            timestamp_precision (int, optional): The precision of the timestamp. Defaults to 3.
            timestamp_range (int, optional): The range of the timestamp. Defaults to 60 * 60 * 24 * 365 (1 year).

        Raises:
            ValueError: Whether a required parameter is missing.
            FileNotFoundError: if the config file is specified but does not exist.
        """
        self.config_file = kwargs.get("config_file", None)
        if self.config_file is not None:
            # Load the config file
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    try:
                        # Merge the config file with the kwargs
                        kwargs = {**kwargs, **json.load(f)}
                    except Exception as e:
                        raise ValueError(
                            f"Config file {self.config_file} is not a valid json file."
                        )
            else:
                raise FileNotFoundError(
                    f"Config file {self.config_file} does not exist."
                )

        # Node parameters
        self._name = name
        self._memory_endpoint = kwargs.get("memory_endpoint", "")
        self._memory_size = kwargs.get("memory_size", None)

        # Check for required parameters
        if self.name == "":
            raise ValueError("Node name cannot be empty.")
        if self.memory_endpoint == "":
            raise ValueError("Memory endpoint cannot be empty.")

        # Parameters parameters
        self._parameters = kwargs.get("parameters", None)

        # services parameters
        self._services = kwargs.get("services", None)
        self._service_server_rate = 1 / float(
            kwargs.get("service_server_rate", 10)
        )
        self._hide_services = kwargs.get("hide_services", False)

        # Timestamp parameters
        self._timestamp_precision = kwargs.get(
            "timestamp_precision", TIMESTAMP_PRECISION
        )
        self._timestamp_range = kwargs.get("timestamp_range", TIMESTAMP_RANGE)

        # Store the kwargs for later use
        # In case of a node restart, the node will be reinitialized with the same kwargs
        self.kwargs = kwargs

        # Initialize the shared memory
        self._memory = SharedMemoryDict(
            name=self.memory_endpoint, size=self.memory_size
        )

        # Generate a unique node id
        self._node_id = self._get_node_id()

        self._publishers = {}
        self._subscriptions = {}

        self._services_map = {}

        # Register node on the memory
        self._register_node()

        # Initialize a Thread to listen to the memory events
        # Initialize a Thread to cleanup the memory periodically
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._executor.submit(self._federated_server)

    @property
    def node_id(self) -> str:
        """Return the node id."""
        return self._node_id

    @property
    def name(self) -> str:
        """Return the node name."""
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        """Set the node name."""
        self._name = name
        self.kwargs["name"] = name

    @property
    def memory_endpoint(self) -> str:
        """Return the memory endpoint."""
        return self._memory_endpoint

    @memory_endpoint.setter
    def memory_endpoint(self, memory_endpoint: str) -> None:
        """Set the memory endpoint."""
        self._memory_endpoint = memory_endpoint
        self.kwargs["memory_endpoint"] = memory_endpoint

    @property
    def memory_size(self) -> Optional[int]:
        """Return the memory size."""
        return self._memory_size

    @memory_size.setter
    def memory_size(self, memory_size: Optional[int]) -> None:
        """Set the memory size."""
        self._memory_size = memory_size
        self.kwargs["memory_size"] = memory_size

    @property
    def parameters(self) -> Optional[Dict[str, Any]]:
        """Return the node parameters."""
        return self._parameters

    @parameters.setter
    def parameters(self, parameters: Optional[Dict[str, Any]]) -> None:
        """Set the node parameters."""
        self._parameters = parameters
        self.kwargs["parameters"] = parameters

    @property
    def publishers(self) -> Optional[Dict[str, Any]]:
        """Return the node publishers."""
        return self._publishers

    @publishers.setter
    def publishers(self, publishers: Optional[Dict[str, Any]]) -> None:
        """Set the node publishers."""
        self._publishers = publishers
        self.kwargs["publishers"] = publishers

    @property
    def subscriptions(self) -> Optional[Dict[str, Any]]:
        """Return the node subscriptions dictionnary containing the topics as keys and the callbacks as values."""
        return self._subscriptions

    @subscriptions.setter
    def subscriptions(self, subscriptions: Optional[Dict[str, Any]]) -> None:
        """Set the node subscriptions."""
        self._subscriptions = subscriptions
        self.kwargs["subscriptions"] = subscriptions

    @property
    def services(self) -> Optional[Dict[str, Any]]:
        """Return the node services."""
        return self._services

    @services.setter
    def services(self, services: Optional[Dict[str, Any]]) -> None:
        """Set the node services."""
        self._services = services
        self.kwargs["services"] = services

    @property
    def service_server_rate(self) -> float:
        """Return the service server rate."""
        return self._service_server_rate

    @property
    def hide_services(self) -> bool:
        """Return the service server rate."""
        return self._hide_services

    @property
    def _timestamp(self) -> int | float:
        return self._get_timestamp()

    def _get_node_id(self) -> str:
        """Generate a unique node id."""
        return "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )

    def _get_timestamp(self) -> int | float:
        """Output a formatted timestamp."""
        # TODO:Limit the range of the timestamp.
        # TODO:Currently Assume that the timestamp can not be older than 1 year.
        # TODO:This will prevent the timestamp from taking too much space in the memory.
        # Idea base the timestamp on the oldest node in the memory.
        # And reduce the floating point precision to 3 digits
        return round(
            time.time(),  # TODO: % self._timestamp_range,
            self._timestamp_precision
            if self._timestamp_precision > 0
            else None,  # If ndigits is None round() converts to int
        )

    def _register_node(self) -> None:
        """Register node on the memory."""
        # TODO:  https://stackoverflow.com/questions/16676177/setting-an-item-in-nested-dictionary-with-setitem

        # Register node within __nds if not already registered
        while self.node_id in self._memory.get("__nds", default={}):
            self.logger.warning(
                f"Node {self.node_id} already registered on the memory."
            )
            self._node_id = self._get_node_id()

        _db = self._memory.get("__nds", default={})

        self.logger.info(f"Registering node {self.node_id} on the memory.")
        _db[self.node_id] = {
            "__n": self.name,
            "__t": self._timestamp,
        }

        # Register node parameters
        if self.parameters is not None:
            _db[self.node_id]["__p"] = self.parameters

        # Register node services
        self._setup_services(_db)

        # Write back to memory
        self._memory["__nds"] = _db

    def restart(self) -> None:
        """Restart the node."""
        self.logger.info(f"Restarting node {self.node_id}:{self.name}.")

        # Restart the node
        self._memory.shm.close()  # Close connection to the shared memory for this node only
        # self._memory.shm.unlink()  # Call unlink only once to release the shared memory

        # Reinitialize the node
        self.__init__(**self.kwargs)  # ?

    def shutdown(self) -> None:
        """Restart the node."""
        self.logger.info(f"Stopping node {self.node_id}:{self.name}.")

        # Close connection to the shared memory for this node only
        self._memory.shm.close()

    # region Federated server functions

    def _federated_server(self) -> None:
        """
        Cleanup the structure periodically.
        All nodes should call this function periodically to clean up the memory

        As nodes act as a federated system, it is important to have a
        common and shared cleanup mechanism accross all nodes to avoid memory
        leaks. All nodes are responsible for maintaining the common master
        memory structure. The cleanup mechanism is based on the following
        assumptions:
            1. All nodes are responsible for cleaning up the shared memory
            2. Every node might get disconnected from the shared memory at any
                time
            3. Rated topics should be used within their timespan to avoid memory
                leaks
            4. Topics published only once should be used within a limited
                timespan to avoid memory leaks
            5. Services should be executed as soon as possible to avoid memory
                leaks
            6. Nodes should be updated periodically to avoid memory leaks
            7. Nodes should be removed from the memory if they are not updated
                within a certain timespan to avoid memory leaks
        """
        _iter_time = time.time()

        _last_federation_time = (
            0  # The time at which the memory was last federated.
        )
        _last_services_time = (
            0  # The time at which the services were last checked.
        )
        _last_subscription_time = {}

        _cleanup_time = 0  # The time at which the memory was last cleaned up.
        # Setting it to 0 will force the memory to be cleaned up instantly on
        # the first iteration of the loop
        while True:
            if time.time() - _last_federation_time > 1:
                _last_federation_time = time.time()

                # Update the heartbeat in the Node structure
                self._memory.modify_structure(
                    ["__nds", self.node_id, "__t"],
                    self._timestamp,
                )

                self.logger.debug(
                    f"Updating heartbeat for node {self.node_id}:{self.name}."
                )

                if self._timestamp > _cleanup_time:
                    _cleanup_time = self._timestamp + DEFAULT_TIMEOUT

                    self.logger.debug("Cleaning up memory.")

                    # Ensure this node is still registered
                    if self.node_id not in self._memory.get("__nds", {}):
                        logging.critical(
                            f"Node {self.node_id}:{self.name} has been disconnected from the memory. Re-registering the node."
                        )
                        self._register_node()

                    # Cleanup unused topics
                    self._memory.process_lambda(self._clear_stale_nodes)

                    # Cleanup unused topics
                    self._memory.process_lambda(self._clear_stale_topics)

                    # Cleanup unused services
                    self._memory.process_lambda(self._clear_stale_services)

            if self.services is not None:
                if (
                    time.time() - _last_services_time
                    > self.service_server_rate
                ):
                    self._listen_service()
                    _last_services_time = time.time()

            if self.subscriptions:
                for topic in self.subscriptions:
                    if (
                        time.time() - _last_subscription_time.get(topic, 0)
                        > self.subscriptions[topic]["rate"]
                    ):
                        message = self._listen_subscription(topic)
                        if (
                            message
                            and message
                            != self.subscriptions[topic]["last_message"]
                        ):
                            self.subscriptions[topic]["last_message"] = message
                            message = {
                                key: value
                                for key, value in message.items()
                                if not key.startswith("__")
                            }  # Remove internal data structures
                            for callback in self.subscriptions[topic][
                                "callbacks"
                            ]:
                                callback(message)
                        _last_subscription_time[topic] = time.time()

            if self.publishers:
                for topic in self.publishers:
                    # Check if it is time to publish
                    if (
                        self._timestamp
                        > float(1 / self.publishers[topic]["rate"])
                        + self.publishers[topic]["last_time"]
                    ):
                        # Publish the message
                        self._publish(
                            topic,
                            self.publishers[topic]["content"],
                            self.publishers[topic]["rate"],
                        )
                        self.publishers[topic]["last_time"] = time.time()
                        print("published", topic)

                        print(self.publishers[topic]["last_time"])

    def _clear_stale_nodes(self, db: Dict[str, Any]) -> None:
        """
        Clear stale nodes.
        Lambda function to be used with the process_lambda function.
        Modifies the db object in place.
        """
        nodes = db.get("__nds", {})
        nodes = {
            node_id: node
            for node_id, node in nodes.items()
            if node.get("__t", 0) + DEFAULT_TIMEOUT > self._timestamp
        }
        db["__nds"] = nodes

    def _clear_stale_topics(self, db: Dict[str, Any]) -> None:
        """
        Clear stale topics.
        Lambda function to be used with the process_lambda function.
        Modifies the db object in place.
        """
        to_remove = []
        for topic, message in db.items():
            if topic.startswith("__"):
                # Skip internal data strtuctures
                continue
            if message.get("__s", None) not in db.get("__nds", {}).keys() or (
                message.get("__t", float("inf"))
                + 1 / float(message.get("__r", 1))
                + DEFAULT_TIMEOUT
                < self._timestamp
            ):
                # Remove the topic
                self.logger.debug(f"Removing topic {topic} from the memory.")
                to_remove.append(topic)
        for topic in to_remove:
            db.pop(topic)

    def _clear_stale_services(self, db: Dict[str, Any]) -> None:
        """
        Clear stale services.
        Lambda function to be used with the process_lambda function.
        Modifies the db object in place.
        """
        # Note: services should only be cleared based on the timestamp
        # In the future, we might want services to be broadcasted to multiple nodes
        # So there won't be any destination node in this case
        services = db.get("__srv", [])
        if not services:
            return db
        services = [
            service
            for service in services
            if service.get("__t", float('inf')) + DEFAULT_TIMEOUT
            > self._timestamp
        ]

        # If services is empty, then remove the __srv key from the memory
        if not services:
            db.pop("__srv")
        else:
            # Else, update the __srv key
            db["__srv"] = services

    # endregion

    # region Publisher functions
    def publish_once(
        self,
        topic: str,
        message: Any,
        rate: Optional[Union[int, float]] = None,
    ) -> None:
        """Publish a message once on a topic."""
        # Ensure the topic is available
        # Compare the topic source with the node id
        # If the topic source is the node id, then the topic is available to this node
        # Else, the topic is not available to this node, then check if the topic hs reached a timeout
        # If the topic has reached a timeout, then the topic is available to this node
        # Else, the topic is not available to this node

        # Add properties
        properties = {
            "__s": self.node_id,
            "__t": self._timestamp,
        }
        if (
            rate is not None
        ):  # Do not add rate if it is published once or rate is unknown
            properties["__r"] = rate

        # Check if the topic is available
        if self._memory.get(topic, default={}).get("__s") == self.node_id:
            # Topic is available
            self._memory[topic] = message | properties
        elif (
            self._memory.get(topic, default={}).get("__t", 0)
            + self._memory.get(topic, default={}).get("__r", 0)
            < self._timestamp + DEFAULT_TIMEOUT
        ):
            # Topic is available after timeout
            self._memory[topic] = message | properties
        else:
            # Topic is not available
            self.logger.error(
                f"Topic {topic} is not available for node {self.node_id}:{self.name} to publish."
            )

    def publish_rate(self, topic: str, message: Any, rate: float = 0) -> None:
        """Publish a message on a topic."""
        logging.debug("Registering publisher", topic, message, rate)
        # Initialize a Thread to publish to the topic periodically
        # self._executor.submit(self._publish, topic, message, rate)
        self.publishers[topic] = {
            "content": message,
            "rate": rate,
            "last_time": 0,
        }

    def _publish(self, topic: str, message: Any, rate: float = 0) -> None:
        """Publish a message on a topic."""
        logging.debug(
            "Publishing",
            topic,
            message if not callable(message) else message(),
            rate,
        )
        self.publish_once(
            topic,
            message if not callable(message) else message(),
            rate,
        )

    # endregion

    # region Subscriber functions
    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic."""
        # Add the callback to the list of callbacks for this topic
        if topic not in self.subscriptions:
            self.subscriptions[topic] = {
                "rate": -1,
                "last_message": None,
                "callbacks": [callback],
            }
            logging.debug(
                f"Registering subscription {topic} for node {self.node_id}:{self.name}."
            )
        else:
            self.subscriptions[topic]["callbacks"].append(callback)
            logging.debug(
                f"Adding callback to subscription {topic} for node {self.node_id}:{self.name}."
            )

    def _listen_subscription(self, topic: str) -> None:
        """Listen to a topic."""
        # while True:
        db = self._memory.get(topic, default={})

        # return the db without the internal data structures
        return db

    # endregion

    # region services: Services: Request/Response functions

    # services are specific calls that can be made to the underlying program that runs the node
    # The services are registered as a dictionary of key-value pairs
    # The key is the name of the service
    # The value is a dictionary of the arguments name and type of the service
    # Example: Two services are registered for a node : "move" and "stop"
    # services = {
    #     "move": {
    #         "x": ArgumentType.FLOAT,
    #         "y": ArgumentType.FLOAT,
    #         "z": ArgumentType.FLOAT,
    #     },
    #     "stop": {},
    # }
    # The available services for each nodes are registered on the __nds dictionary under the key "__s" for each node
    # Example:
    # __nds = {
    #     "node_id": {
    #         "__n": "node_name",
    #         "__s": {
    #             "move": {
    #                 "x": ArgumentType.FLOAT,
    #                 "y": ArgumentType.FLOAT,
    #                 "z": ArgumentType.FLOAT,
    #             },
    #             "stop": {},
    #         },
    #     },
    # }

    def _setup_services(
        self,
        database: Optional[Dict[str, Any]],
    ) -> None:
        """Register node services."""

        if self.services is not None:
            # Initialize a Thread to listen to the services
            self._service_executor.submit(self._listen_service)

            # format the services dictionary
            self._services_map = {}
            _services = {}
            for service in self.services.keys():
                if callable(service):
                    self._services_map[service.__name__] = service
                    _services[service.__name__] = self.services[service]
                elif isinstance(service, str):
                    # ? What is the point of this?
                    self._services_map[service] = self.services[service]
                    _services[service] = self.services[service]
                else:
                    raise TypeError(
                        f"service {service} is not a string or a function."
                    )

            # Inform the memory of the services available for this node
            db = (
                self._memory.get("__nds", default={})
                if database is None
                else database
            )

            if not self.hide_services:
                # Advertise the services available for this node
                db[self.node_id]["__s"] = _services

            if database is None:
                self._memory["__nds"] = db

    def split_services_db(self, db: Dict[str, Any], dst) -> list[Any]:
        services = db.get("__srv", [])
        service_buffer, services = [
            x for x in services if x["__dst"] == dst
        ], [x for x in services if x["__dst"] != dst]
        if services:
            db["__srv"] = services
        else:
            db.pop("__srv")
        return service_buffer

    def _listen_service(self) -> None:
        """Listen to services."""
        # Listening and processing services might take some time
        # Therefore, to not block the memory, we first need to fetch and remove
        # all services directed to this node from the memory, all in a single
        # operation. Then, we can process the services
        service_buffer = []

        if "__srv" in self._memory.keys():
            # Fetch and remove all services directed to this node from the memory
            service_buffer = self._memory.process_lambda(
                self.split_services_db, self.node_id
            )

            if service_buffer:
                self.logger.debug(
                    f"Processing {len(service_buffer)} services for node {self.node_id}:{self.name}:\n\t"
                    + "\n\t".join([str(_) for _ in service_buffer])
                )

            for service in service_buffer:
                # Find the appropriate callback for the service
                # Get the first key in service that does not start with "__"
                callback = self._services_map.get(
                    next(
                        filter(
                            lambda x: not x.startswith("__"),
                            service.keys(),
                        )
                    ),
                    None,
                )

                if callback is None:
                    # service is not available
                    self.logger.warning(
                        f"Service {service} was called to this node from {service.get('__src')}, but the service is not available."
                    )
                    continue
                else:
                    self.logger.debug(
                        f"Executing service {service} for node {self.node_id}:{self.name} with callback {callback.__name__}."
                    )

                    try:
                        # Execute the service
                        response = callback(**service[callback.__name__])

                        # If the service has a response, then send the response back to the source node
                        if (
                            response is not None
                            and service.get("__ans", None) is not None
                        ):
                            self.call_service(
                                dest_node_id=service.get("__src"),
                                service=service.get("__ans"),
                                **response,
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Callback occured when running callback {service} with arguments {service[callback.__name__]}:\n{e}"
                        )

    def call_service(
        self,
        dest_node_id: Optional[str] = None,
        dest_node_name: Optional[str] = None,
        service: str = None,
        answer: Optional[str] = None,
        **kwargs: Any,
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
            self.logger.error(
                "Either dest_node_id or dest_node_name must be specified."
            )
            return

        if dest_node_id is None:
            dest_node_id = self.find_node_by_name(dest_node_name)

        if dest_node_id in self._memory.get(
            "__nds", {}
        ):  # Check if at least one node with the same name exists
            if not self.is_service_advertised(dest_node_id, service):
                # service is not available
                # No need to call the service
                self.logger.warning(
                    f"No service with name {service} has been advertised by "
                    + f"node {dest_node_id} to call. However, the node might "
                    + "be hiding its services. The call will be made anyway."
                )

            # service is available
            properties = {
                "__dst": dest_node_id,
                "__src": self.node_id,
                "__t": self._timestamp,
            }

            # Add the name of the answer service if any
            if answer is not None:
                if callable(answer):
                    properties["__ans"] = answer.__name__
                elif isinstance(answer, str):
                    properties["__ans"] = answer
                else:
                    self.logger.error(
                        f"Answer service {answer} is not a string or a function. Answer service will be ignored."
                    )

            # Replace any previous call to the same service that has not been executed yet
            self._memory["__srv"] = [
                _service
                for _service in self._memory.get("__srv", [])
                if not (
                    _service.get("__dst") == dest_node_id
                    and _service.get("__src") == self.node_id
                    and service in _service.keys()
                )
            ] + [{service: kwargs} | properties]

            self.logger.debug(
                f"Called service {service} on node {dest_node_id}.",
            )
        else:
            # service is not available
            self.logger.error(
                f"No node with name {dest_node_id} was found to call service {service}."
            )

    def find_nodes_by_name(self, name: str) -> List[str]:
        """Search for a node by name."""
        nodes = self._memory.get("__nds", default={})
        return [node for node in nodes.keys() if nodes[node]["__n"] == name]

    def find_node_by_name(self, name: str) -> Optional[str]:
        """Search for a node by name."""
        nodes = self.find_nodes_by_name(name)
        # Return the first node with the same name
        return nodes[0] if nodes else None

    def list_node_services(self, node_name: str) -> Dict[str, Any]:
        """List the services available for a node."""
        node_id = self.find_node_by_name(node_name)
        return self._memory.get("__nds", {}).get(node_id, {}).get("__s", {})

    def is_node_advertising_services(self, node_name: str) -> bool:
        """Check if a node is advertising services."""
        node_id = self.find_node_by_name(node_name)
        return (
            self._memory.get("__nds", {}).get(node_id, {}).get("__s", {}) != {}
        )

    def is_service_advertised(self, node_id: str, service: str) -> bool:
        """Check if an service is advertised by a node."""
        return (
            self._memory.get("__nds", {})
            .get(node_id, {})
            .get("__s", {})
            .get(service, {})
            != {}
        )

    # endregion

    # region Parameters: Parameter Server functions
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update node parameters."""
        db = self._memory.get("__nds", default={})

        if self.node_id not in db:
            # ! This case might happen if the server had to restart unexpectedly
            return

        db[self.node_id]["__p"] = parameters
        self._memory["__nds"] = db

    def get_parameters(self, node_id: str) -> Dict[str, Any]:
        """Get node parameters."""
        db = self._memory.get("__nds", default={})
        return db.get(node_id, {}).get("__p", {})

    # endregion
