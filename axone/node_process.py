import json
import logging
import multiprocessing
import os
from typing import Any, Callable, Dict, Optional

from axone.axone_struct import AxoneStruct
from axone.custom_logger import CustomFormatter
from axone.node import AxoneNode
from axone.publisher import Publisher
from axone.subscriber import Subscription
from axone.utils import generate_uuid, timeit_if_debug


class AxoneNodeProcess(AxoneNode):
    """
    NodeProcess is a node that executes inside a process.
    Most of the functions are overrides of the Node class to allow
    communication between the process and the main thread.
    They are prefixed with an underscore to avoid name collisions.
    Communication is done through a Pipe between the main thread and the
    process.
    """

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
        self.kwargs = kwargs

        # Lists of publishers, subscribers and services
        self._publishers: Dict[str, Publisher] = {}
        self._subscriptions: Dict[str, Subscription] = {}

    def start(self):
        """Start the node."""
        # Re-initialize the shared logger
        global_log_level = logging.getLogger().getEffectiveLevel()
        multiprocessing.log_to_stderr(global_log_level)
        self.logger = multiprocessing.get_logger()
        formatter = CustomFormatter()
        for handler in self.logger.handlers:
            handler.setFormatter(formatter)

        # Initialize the communication pipes
        self._parent_conn, self._child_conn = multiprocessing.Pipe()

        # Initialize a Process to run the node
        self._executor = multiprocessing.Process(
            target=self.run,
            args=(
                self.name,
                self._child_conn,
            ),
            kwargs=self.kwargs,
            name="NodeProcess",
        )
        self._executor.start()

    def _call_function(self, function_name, *args, **kwargs) -> Any:
        """Call a function on the node."""
        try:
            self.logger.debug(f"Calling function {function_name} with args={args}, kwargs={kwargs}")
            self._parent_conn.send((function_name, args, kwargs))
            return self._parent_conn.recv()
        except AttributeError:
            self.logger.error(f"Cannot call function {function_name} until the node has started.")
            exit(1)

    def _call_function_async(self, function_name, *args, **kwargs) -> None:
        """Call a function on the node and exit without waiting for a return."""
        try:
            self.logger.debug(f"Calling function {function_name} with args={args}, kwargs={kwargs}")
            self._parent_conn.send((function_name, args, kwargs))
            # No return expected here
        except AttributeError:
            self.logger.error(f"Cannot call function {function_name} until the node has started.")
            exit(1)

    def run(self, name, conn, **kwargs) -> None:
        """Run the node."""
        # Initialize the node

        # Node parameters (those are accessible from the process)
        self.name = name
        self.node_id = generate_uuid(self.name)  # Generate a unique node id

        # Lists of subscribers
        # Note: We indeed have to initialize the subscribers here a second times
        # because the previous initialization is not accessible from the process.
        # Due to this limitation, we need to periodically check if there are new
        # subscribers to add.
        self._subscriptions: Dict[str, Subscription] = {}

        # Check for required parameters
        if self.name == "":
            raise ValueError("Node name cannot be empty.")

        print("=" * 50)
        print(f"Node name: {self.name}")
        print(f"Node id: {self.node_id}")
        print(f"Node parameters: {kwargs}")
        print("=" * 50)

        # Create the centralized node
        self.centralized_node = self.CentralizedNode(self.name, self.node_id, **kwargs)
        self.centralized_node.advertise()

        # services parameters
        self.service_server = None
        self._services = kwargs.get("services", None)
        # self._hide_services = kwargs.get("hide_services", False)
        self.setup_service_server()

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

        # Run the server process
        self._server_process(conn)

    def _server_process(self, conn) -> None:
        while True:
            # Check if there's a task to be executed
            if conn.poll():
                task = conn.recv()
                function_name, args, kwargs = task
                # Map the function name to the actual function
                # Needed to avoid pickling the function itself
                # which is forbidden
                try:
                    function = getattr(self, f'{function_name}')
                    result = function(*args, **kwargs)
                    self.logger.debug(f"Result: {result}")
                    conn.send(result)
                except AttributeError:
                    self.logger.error(f"Function {function_name} possibly does not exist.", exc_info=True)
            else:
                # Handle the case where there's nothing to receive
                pass

            self._server_exec()

    def stop(self) -> None:
        """Stop the node."""

        # Close the pipes
        self._parent_conn.close()
        self._child_conn.close()

        # Terminate the process
        self._executor.terminate()
        self._executor.join()

    def join(self) -> None:
        """Join the node."""
        self._executor.join()

    # region Publisher functions
    @timeit_if_debug
    def publish_once(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
    ) -> None:
        """Publish a message to a topic once."""
        return self._call_function_async("_publish_once", topic=topic, rate=rate)

    def publish_rate(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
    ) -> None:
        """Register a publisher for a topic."""
        # Note: This is indeed calling the "_publish_once" function but with a
        # periodic rate which is used by the server during publication.
        return self._call_function_async("_publish_once", topic=topic, rate=rate)

    # endregion Publisher functions

    # region Subscriber functions

    def subscribe(self, topic_name: str, callback: Callable | None = None) -> None:
        """Subscribe to a topic."""

        # The objective here is that the NodeProces will subscribe to the
        # requested topics and send the collected AxoneStruct to the main process
        # through the pipe. The main process will then be able to access the
        # AxoneStruct as if it was subscribed to the topic itself.
        #
        # This should theoretically be done is several steps:
        # 1. The MainProcess receives a subscribe request through this function
        #    and was also provided with a callback function from the user.
        # 2. The MainProcess sends a subscribe request to the NodeProcess
        #    but without a callback function as this is not authorized in the
        #    pipe communication.
        # 3. The NodeProcess subscribes periodically to the topic at the appropriate
        #    rate and when a structure is received, it sends it to the MainProcess.
        # 4. The MainProcess now has to poll the pipe to check if there's a new
        #    structure to be received. When a structure is received, it can be
        #    passed to the callback function provided by the user.
        #
        # The fourth step is the most inconvenient as it requires to have another loop
        # running in the main process to check for new structures. This is not ideal.
        #
        # For these reasons, the subscribe() method shall be handled differently in the
        # NodeProcess variant. The subscribe method will still be available but will
        # not accept a callback function. Instead, the user will have to use the
        # listen_once to get the struct fetched by the NodeProcess.

        if callback is not None:
            logging.error(
                "Subscribe() method cannot accept a callback in the NodeProcess variant. Use listen_once periodically instead."
            )
        return self._call_function_async("_subscribe", topic_name=topic_name, callback=None)

    @timeit_if_debug
    def listen_once(
        self,
        topic: str,
    ) -> dict:
        """Listen to a topic once."""
        return self._call_function("_listen_once_async", topic=topic)

    @timeit_if_debug
    def _listen_once_async(self, topic: str) -> AxoneStruct:
        """Listen to a topic once."""
        # This variant of the listen_once function is used in the NodeProcess variant
        # to get the AxoneStruct from the shared memory. But, instead of fetching
        # and then returning the AxoneStruct, it will instead return a struct that
        # was fetched by the listener server at a previous iteration.
        # This is because the listener server is running in a separate process
        # and the AxoneStruct cannot be pickled and sent back to the main process.

        # TODO: Regarding the default rate we are setting here, maybe the subscribe
        # function should be called with a rate argument in the NodeProcess variant.

        if topic not in list(self.subscriptions):
            # Request a subscription to the topic and go fetch the struct now
            # So that the client gets an answer now (although it will be slow)
            # Create a new subscription
            self.subscriptions[topic] = Subscription(topic)
            logging.warning(f"Registering subscription {topic} for node {self.node_id}:{self.name}.")
            # Fetch the struct now
            # This is a blocking call
            self.subscriptions[topic].subscribe()
            # Force the rate to 1.0 to force the server to fetch the struct
            self.subscriptions[topic].rate = 1.0
        else:
            if self.subscriptions[topic].rate < 0:
                # If the rate is negative, it means the subscription is not
                # fetched periodically. So set the rate at 1.0 to force the server
                # to fetch the struct for the next iteration.
                self.subscriptions[topic].rate = 1.0
                logging.warning(f"Setting rate to {self.subscriptions[topic].rate} for subscription to {topic}")

        # return the last struct fetched diretcly from the subscriptions
        return self.subscriptions[topic]._topic

    # endregion Subscriber functions

    # region Services - Request/Response functions
    def call_service(
        self,
        dest_node_id: Optional[str] = None,
        dest_node_name: Optional[str] = None,
        service: Optional[str] = None,
        answer: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Call a service."""
        return self._call_function(
            "_call_service",
            dest_node_id=dest_node_id,
            dest_node_name=dest_node_name,
            service=service,
            answer=answer,
            **kwargs,
        )

    # endregion

    def list_nodes(self) -> list[str]:
        """
        List all the attributes in the centralized memory.
        This is really simple as the centralized memory only contains the nodes ID and names.
        """
        return self._call_function("_list_nodes")

    def find_node_by_name(self, name: str) -> Optional[str]:
        """Search a node by name"""
        node = self._call_function("_find_nodes_by_name", name=name)
        return node

    def get_node_configuration(self, name: str) -> Any:
        """Get the configuration of a node."""
        return self._call_function("_get_node_configuration", name=name)

    def list_node_services(self, name: str) -> Any:
        """List the services available for a node."""
        return self._call_function("_list_node_services", name=name)

    def get_node_services_server_port(self, name: str) -> Any:
        """List the services available for a node."""
        return self._call_function("_get_node_services_server_port", name=name)

    def is_node_advertising_services(self, name: str) -> bool:
        """Check if a node is advertising services."""
        return self._call_function("_is_node_advertising_services", name=name)

    # region Parameters: Parameter Server functions
    def update_parameters(self, parameters: Dict[str, Any]):
        return self._call_function("_update_parameters", parameters=parameters)

    def get_parameters(self, node_id: str) -> Dict[str, Any]:
        return self.call_service("_get_parameters", node_id=node_id)

    # endregion
