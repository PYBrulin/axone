import json
import logging
import multiprocessing
import os
from typing import Any, Callable, Dict, Optional

from axone.axone_struct import AxoneStruct
from axone.custom_logger import CustomFormatter  # noqa
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

    The MainProcess should only call functions in an asynchronous way.
    The NodeProcess is responsible for interacting with the Nodes.
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

        # Services parameters
        self._services = kwargs.get("services", None)

        # Lists of publishers, subscribers and services
        self._publishers: Dict[str, Publisher] = {}
        self._subscriptions: Dict[str, Subscription] = {}

    # region Process functions

    @timeit_if_debug
    def _call_function(self, function_name, *args, **kwargs) -> Any:
        """Call a function on the node."""
        try:
            logging.debug(f"Calling function {function_name} with args={args}, kwargs={kwargs}")
            self._parent_conn.send((function_name, args, kwargs))
            return self._parent_conn.recv()
        except AttributeError:
            logging.error(f"Cannot call function {function_name} until the node has started.")
            exit(1)

    @timeit_if_debug
    def _call_function_async(self, function_name, *args, **kwargs) -> None:
        """Call a function on the node and exit without waiting for a return."""
        try:
            logging.debug(f"Calling function {function_name} with args={args}, kwargs={kwargs}")
            self._parent_conn.send((function_name, args, kwargs))
            # No return expected here
        except AttributeError:
            logging.error(f"Cannot call function {function_name} until the node has started.")
            exit(1)

    # endregion Process functions

    # region Common functions

    def list_nodes(self) -> list[str]:
        """
        List all the attributes in the centralized memory.
        This is really simple as the centralized memory only contains the nodes ID and names.
        """
        return self._call_function("_list_nodes")

    def find_node_by_name(self, name: str) -> Optional[str]:
        """Search a node by name"""
        node = self._call_function("_find_node_by_name", name=name)
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

    def get_node_topics(self, name: str) -> list[str]:
        """List the topics published by a node."""
        return self._call_function("_get_node_topics", name=name)

    # endregion Common functions

    # region Publisher functions
    @timeit_if_debug
    def publish_once(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
        method: str = "shared_memory",
    ) -> None:
        """Publish a message to a topic once."""
        return self._call_function_async("_publish_once", topic=topic, rate=rate, method=method)

    def publish_rate(
        self,
        topic: AxoneStruct,
        rate: float = -1.0,
        method: str = "shared_memory",
    ) -> None:
        """Register a publisher for a topic."""
        # Note: This is indeed calling the "_publish_once" function but with a
        # periodic rate which is used by the server during publication.
        return self._call_function_async("_publish_once", topic=topic, rate=rate, method=method)

    # endregion Publisher functions

    # region Subscriber functions

    def subscribe(self, topic_name: str, callback: Callable | None = None, method: str = "shared_memory") -> None:
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
        return self._call_function_async("_subscribe", topic_name=topic_name, callback=None, method=method)

    @timeit_if_debug
    def listen_once(self, topic: str, method: str = "shared_memory") -> dict:
        """Listen to a topic once."""

        # this function differs from the one in the Node class in that it will
        # try to return the latest AxoneStruct fetched by the listener server
        # from the child process.

        # Try to fetch latest data from subscription_queue
        while self._subscription_queue.qsize() > 0:
            _topic, _struct, _method = self._subscription_queue.get()
            # Add the received struct to the local subscriptions dict
            logging.debug(f"Adding fetched struct {_topic} to subscriptions")
            self.subscriptions[_topic] = _struct

        # Request an update for the topic for the next time
        self._call_function_async("_listen_once_async", topic=topic, method=method)

        return self.subscriptions.get(topic, AxoneStruct())

    @timeit_if_debug
    def _listen_once(self, topic: str) -> AxoneStruct:
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

    @timeit_if_debug
    def _listen_once_async(self, topic: str, method: str = "shared_memory") -> AxoneStruct:
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
            self.subscriptions[topic] = Subscription(topic, method=method)
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

        # Send the last struct to the parent_conn
        logging.debug(f"Sending fetched struct {topic} to subscription_queue")
        self._subscription_queue.put((topic, self.subscriptions[topic]._topic, method))

    # endregion Subscriber functions

    # region Services functions
    def call_service(
        self,
        dest_node_id: Optional[str] = None,
        dest_node_name: Optional[str] = None,
        service_name: Optional[str] = None,
        # answer: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Call a service."""
        return self._call_function(
            "_call_service",
            dest_node_id=dest_node_id,
            dest_node_name=dest_node_name,
            service_name=service_name,
            # answer=answer,
            **kwargs,
        )

    # endregion Services functions

    # region Parameters: Parameter Server functions
    # def update_parameters(self, parameters: Dict[str, Any]):
    #     return self._call_function("_update_parameters", parameters=parameters)
    # def get_parameters(self, node_id: str) -> Dict[str, Any]:
    #     return self.call_service("_get_parameters", node_id=node_id)
    # endregion

    def start(self):
        """Start the node."""
        # # Re-initialize the shared logger
        # global_log_level = logging.getLogger().getEffectiveLevel()
        # multiprocessing.log_to_stderr(global_log_level)
        # self.logger = multiprocessing.get_logger()
        # formatter = CustomFormatter()
        # for handler in self.logger.handlers:
        #     handler.setFormatter(formatter)

        # Initialize the communication pipes
        # Parent_conn is used to receive data from the process
        # Child_conn is used to send data to the process
        self._parent_conn, self._child_conn = multiprocessing.Pipe()
        self._subscription_queue = multiprocessing.Queue()

        # Initialize a Process to run the node
        self._executor = multiprocessing.Process(
            target=self.run,
            args=(
                self.name,
                self._child_conn,  # Send the child_conn to the process
                self._subscription_queue,  # Send the subscription_queue to the process
            ),
            kwargs=self.kwargs,
            name="NodeProcess",
        )
        self._executor.start()

        if self.services is not None:
            # Note: The services server is not contained in the node process
            # TODO: Is there any point in having the services server in the node process?
            # TODO: All callbacks are external to the node process.
            self.setup_service_server()
            self.service_server.start()

    def run(self, name, child_conn, subscription_queue, **kwargs) -> None:
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
        self._subscription_queue = subscription_queue

        # Check for required parameters
        if self.name == "":
            raise ValueError("Node name cannot be empty.")

        logging.info(f"Starting node process for : {self.name}")

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
        self._server_process(child_conn)

    def stop(self) -> None:
        """Stop the node."""

        # Close the pipes and the queue
        self._parent_conn.close()
        self._child_conn.close()
        self._subscription_queue.close()

        # Terminate the process
        self._executor.terminate()
        self._executor.join()

    def join(self) -> None:
        """Join the node."""
        self._executor.join()

    def _server_process(self, child_conn) -> None:
        while True:
            # Check if there's a task to be executed from the child_conn endpoint
            if child_conn.poll():
                task = child_conn.recv()
                function_name, args, kwargs = task
                # Map the function name to the actual function
                # Needed to avoid pickling the function itself
                # which is forbidden
                try:
                    function = getattr(self, f'{function_name}')
                    result = function(*args, **kwargs)
                    logging.debug(f"Result: {result}")
                    child_conn.send(result)
                except AttributeError:
                    logging.error(f"Function {function_name} possibly does not exist.", exc_info=True)
            else:
                # Handle the case where there's nothing to receive
                pass

            self._server_exec()
