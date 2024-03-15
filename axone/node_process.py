import logging
import multiprocessing
from typing import Any, Dict, List, Optional, Union

from .node import Node
from .shared_memory_dict import SharedMemoryDict


class NodeProcess(Node):
    """
    NodeProcess is a node that executes inside a process.
    Most of the functions are overrides of the Node class to allow
    communication between the process and the main thread.
    They are prefixed with an underscore to avoid name collisions.
    Communication is done through a Pipe between the main thread and the
    process.
    """

    def __init__(self, name: str, **kwargs):
        """Initialize the node."""
        super().__init__(name, **kwargs)

    def start(self):
        """Start the node."""
        # Re-initialize the shared logger
        multiprocessing.log_to_stderr(logging.DEBUG)
        self.logger = multiprocessing.get_logger()

        # Initialize the communication pipes
        self._parent_conn, self._child_conn = multiprocessing.Pipe()

        # Initialize a Process to run the node
        self._executor = multiprocessing.Process(target=self.run, args=(self._child_conn,), name="NodeProcess")
        self._executor.start()

    def _call_function(self, function_name, *args, **kwargs) -> Any:
        """Call a function on the node."""
        self.logger.debug(f"Calling function {function_name} with args={args}, kwargs={kwargs}")
        self._parent_conn.send((function_name, args, kwargs))
        return self._parent_conn.recv()

    def run(self, conn):
        """Run the node."""
        # Initialize the shared memory
        self._memory = SharedMemoryDict(name=self.memory_endpoint, size=self.memory_size)

        # Register node on the memory
        self._register_node()
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
                    self.logger.warning(f"Result: {result}")
                    conn.send(result)
                except AttributeError:
                    self.logger.error(f"Function {function_name} does not exist.")
            else:
                # Handle the case where there's nothing to receive
                pass

            self._server_exec()

    def stop(self):
        """Stop the node."""

        # Close the pipes
        self._parent_conn.close()
        self._child_conn.close()

        # Terminate the process
        self._executor.terminate()
        self._executor.join()

    def join(self):
        """Join the node."""
        self._executor.join()

    # region Publisher functions
    def publish_once(
        self,
        topic: str,
        message: dict,
        rate: Optional[Union[int, float]] = None,
    ) -> None:
        """Publish a message to a topic once."""
        return self._call_function("_publish_once", topic=topic, message=message, rate=rate)

    # endregion

    # region Subscriber functions
    def listen_once(
        self,
        topic: str,
    ) -> dict:
        """Listen to a topic once."""
        return self._call_function("_listen_once", topic=topic)

    # endregion

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

    def find_nodes_by_name(self, name: str) -> List[str]:
        """Search for nodes by name."""
        return self._call_function("_find_nodes_by_name", name=name)

    def find_node_by_name(self, name: str) -> str | None:
        nodes = self._call_function("_find_nodes_by_name", name=name)
        return nodes[0] if nodes else None

    def list_node_services(self, node_id: str) -> Dict[str, Any]:
        return self._call_function("_list_node_services", node_id=node_id)

    def is_node_advertising_services(self, node_name: str) -> bool:
        return self._call_function("_is_node_advertising_services", node_name=node_name)

    def is_service_advertised(self, node_id: str, service: str) -> bool:
        return self._call_function("_is_service_advertised", node_id=node_id, service=service)

    # endregion

    # region Parameters: Parameter Server functions
    def update_parameters(self, parameters: Dict[str, Any]):
        return self._call_function("_update_parameters", parameters=parameters)

    def get_parameters(self, node_id: str) -> Dict[str, Any]:
        return self.call_service("_get_parameters", node_id=node_id)

    # endregion
